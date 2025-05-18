from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import anthropic
from dotenv import load_dotenv

from .utils import formatar_valor_utils

load_dotenv()
logger = logging.getLogger(__name__)


class KPIInterpreter:
    """
    Gera análises em linguagem executiva para um KPI usando o modelo Claude.
    Mantém cache de resultados e opera em modo offline se não houver chave.
    """

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def __init__(self, kpi_descriptions: Dict[str, Any]):
        self.kpi_descriptions = kpi_descriptions

        # chave segura via .env / GitHub Secrets
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

        # cria client se possível (SDK novo ou antigo)
        if self.anthropic_api_key:
            if hasattr(anthropic, "Anthropic"):
                self.client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            else:  # compat antes de 0.45
                self.client = anthropic.Client(api_key=self.anthropic_api_key)
        else:
            self.client = None
            logger.warning("ANTHROPIC_API_KEY não definida – modo offline.")

        # cache: (kpi, periodo, status, resultado arredondado)
        self.cache: Dict[tuple, str] = {}

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    @staticmethod
    def _convert_result_to_float(value) -> float | None:
        """Normaliza diferentes formatos numéricos para float."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            txt = "".join(c for c in value if c.isdigit() or c in ",.-")
            txt = txt.replace(",", ".")
            try:
                return float(txt)
            except ValueError:
                return None
        return None

    def _validate_inputs(self, kpi_name: str, kpi_values: Dict[str, Any]):
        if not kpi_name or not isinstance(kpi_values, dict):
            return False, "Erro: parâmetros inválidos."

        if kpi_name not in self.kpi_descriptions:
            return False, f"Erro: KPI '{kpi_name}' não encontrado."

        resultado_val = kpi_values.get("resultado")
        resultado_num = self._convert_result_to_float(resultado_val)
        if resultado_num is None:
            return False, "Erro: valor do resultado inválido."

        return True, resultado_num

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------
    @staticmethod
    def _system_prompt() -> str:
        return (
            "Você é analista de negócios sênior da Eshows, especializado em crescimento "
            "e rentabilidade. Use linguagem natural e objetiva, sem superlativos, e "
            "baseie‑se sempre em dados consolidados."
        )

    def _human_prompt(
        self,
        *,
        kpi_name: str,
        description: str,
        formula: str,
        periodo: str,
        resultado_num: float,
        status: str,
        all_indicators: Dict[str, Any],
        strategy_info: Dict[str, Any] | None,
    ) -> str:
        indicators_json = json.dumps(all_indicators, indent=2, ensure_ascii=False)

        strategy_block = ""
        if strategy_info:
            strategy_block = (
                "\n[CONTEXTO ESTRATÉGICO]\n"
                f"Estratégia (Doc): {strategy_info.get('estrategia', '–')}\n"
                f"Pilares (Doc): {strategy_info.get('pilares', '–')}\n"
            )

        data_priority_note = (
            "Caso existam divergências entre o KPI principal e valores brutos, "
            "priorize as séries históricas consolidadas como 'historical_lucro_liquido'."
        )

        extra_instructions = (
            "Observação IMPORTANTÍSSIMA:\n"
            "- Sempre mencione o período a que cada número se refere.\n"
            "- Recomendações devem apontar como se conectam aos pilares estratégicos.\n"
            "- Considere apenas dados históricos até o último mês do período filtrado.\n"
        )

        return f"""
Faça uma análise aprofundada do seguinte KPI:

[CONTEXTO ATUAL DO NEGÓCIO]
{indicators_json}

{strategy_block}
[NOTA IMPORTANTE SOBRE DADOS]
{data_priority_note}

[KPI PRINCIPAL]
- Nome: {kpi_name}
- Valor: {formatar_valor_utils(resultado_num, 'percentual')}
- Status: {status}
- Período: {periodo}

[Sobre este KPI]
- Descrição: {description}
- Fórmula: {formula}

{extra_instructions}

Por favor, formate sua resposta em Markdown seguindo esta estrutura:

1. ## Diagnóstico Situacional  
2. ## Análise de Correlações e Causas  
3. ## Projeções e Cenários  
4. ## Recomendações Acionáveis  
5. ## Considerações Estratégicas
""".strip()

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------
    @staticmethod
    def _fallback(kpi_name: str) -> str:
        return f"Interpretação indisponível: sem acesso à API para o KPI '{kpi_name}'."

    # ------------------------------------------------------------------
    # Método público
    # ------------------------------------------------------------------
    def generate_kpi_interpretation_claude(
        self,
        kpi_name: str,
        kpi_values: Dict[str, Any],
        strategy_info: Dict[str, Any],
        all_indicators: Dict[str, Any],
    ) -> str:
        # validação
        ok, result_or_msg = self._validate_inputs(kpi_name, kpi_values)
        if not ok:
            return result_or_msg

        resultado_num: float = result_or_msg
        periodo = kpi_values.get("periodo", "Período não informado")
        status = kpi_values.get("status", "Status não informado")

        cache_key = (kpi_name, periodo, status, round(resultado_num, 4))
        if cache_key in self.cache:
            return self.cache[cache_key]

        if not self.client:
            return self._fallback(kpi_name)

        prompt = self._human_prompt(
            kpi_name=kpi_name,
            description=self.kpi_descriptions[kpi_name]["description"],
            formula=self.kpi_descriptions[kpi_name]["formula"],
            periodo=periodo,
            resultado_num=resultado_num,
            status=status,
            all_indicators=all_indicators,
            strategy_info=strategy_info,
        )

        try:
            res = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1200,
                temperature=0.4,
                system=self._system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )
            text = res.content[0].text.strip() if res.content else ""
            if not text:
                text = self._fallback(kpi_name)
        except Exception as exc:
            logger.error("Erro na API Anthropic: %s", exc)
            text = self._fallback(kpi_name)

        self.cache[cache_key] = text
        return text

    # ------------------------------------------------------------------
    # OpenAI extra (opcional)
    # ------------------------------------------------------------------
    @staticmethod
    def interpret_with_openai(prompt: str) -> str:
        import openai

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return "OPENAI_API_KEY não definida."
        openai.api_key = api_key

        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
