import json
import logging
import os
from typing import Dict, Any
import anthropic
from dotenv import load_dotenv
from app.utils.utils import formatar_valor_utils

load_dotenv()
logger = logging.getLogger(__name__)

class KPIInterpreter:
    def __init__(self, kpi_descriptions: Dict[str, Any]):
        """
        kpi_descriptions: dicionário que mapeia cada kpi_name para suas informações
        (description, formula, etc.).
        """
        self.kpi_descriptions = kpi_descriptions
        # Inicializa o cliente da Anthropic usando a variável de ambiente
        self.anthropic_api_key = "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"
        self.client = anthropic.Client(api_key=self.anthropic_api_key)

        # [NOVO] Cria um dicionário para cachear as interpretações
        self.cache = {}

    def _convert_result_to_float(self, resultado_valor):
        """
        Tenta converter o valor do resultado para float, tratando strings
        com símbolos de R$, %, etc.
        """
        if isinstance(resultado_valor, (int, float)):
            return float(resultado_valor)
        elif isinstance(resultado_valor, str):
            try:
                valor_limpo = ''.join(c for c in resultado_valor if c.isdigit() or c in ',.%-')
                if '%' in valor_limpo:
                    valor_limpo = valor_limpo.replace('%', '')
                valor_limpo = valor_limpo.replace(',', '.')
                return float(valor_limpo)
            except ValueError:
                return None
        return None

    def _validate_inputs(self, kpi_name: str, kpi_values: Dict[str, Any]) -> tuple:
        """
        Valida se o kpi_name e kpi_values são coerentes e converte o 'resultado' em float.
        """
        if not kpi_name or not isinstance(kpi_values, dict):
            return False, "Erro: Parâmetros inválidos."
        
        kpi_info = self.kpi_descriptions.get(kpi_name)
        if not kpi_info:
            return False, f"Erro: KPI '{kpi_name}' não encontrado."
        
        resultado_val = kpi_values.get('resultado')
        if resultado_val is None:
            return False, "Erro: Resultado não fornecido."
        
        resultado_num = self._convert_result_to_float(resultado_val)
        if resultado_num is None:
            return False, "Erro: Valor do resultado inválido."
        
        return True, resultado_num

    def _prepare_system_prompt(self):
        """
        Prompt de sistema, instruindo a IA a manter linguagem humana e evitar exageros.
        """
        return (
            "Você é um(a) analista de negócios sênior da Eshows, especializado em análise de crescimento e rentabilidade. "
            "Sua linguagem deve soar natural, sem palavras exageradas (como 'extremamente'). "
            "Use dados consolidados para suas análises e evite contradições se houver divergência no JSON."
        )

    def _prepare_human_prompt(
        self,
        kpi_name: str,
        description: str,
        formula: str,
        periodo: str,
        resultado_num: float,
        status: str,
        all_indicators: Dict[str, Any],
        strategy_info: Dict[str, Any] = None
    ) -> str:
        """
        Monta o prompt que será enviado ao modelo, incluindo uma instrução
        para ignorar dados conflitantes e priorizar históricos confiáveis.
        """

        indicators_json = json.dumps(all_indicators, indent=2, ensure_ascii=False)
        logger.debug("### JSON de Indicadores Enviado ao LLM:\n%s", indicators_json)

        strategy_context = ""
        if strategy_info:
            estrat = strategy_info.get('estrategia', 'Estratégia não definida')
            pilares = strategy_info.get('pilares', 'Pilares não definidos')
            logger.debug("### Conteúdo do Strategy Info:\n%s", json.dumps(strategy_info, indent=2, ensure_ascii=False))

            strategy_context = f"""
[CONTEXTO ESTRATÉGICO]
Estratégia (Doc): {estrat}
Pilares (Doc): {pilares}
"""
        else:
            logger.debug("### Nenhuma estratégia definida no 'strategy_info'.")

        data_priority_note = (
            "Caso existam divergências entre o KPI principal e valores brutos conflitantes, "
            "priorize os valores consolidados, como 'historical_lucro_liquido' e 'historical_faturamento_eshows'. "
            "Ignore dados duplicados de uma mesma métrica."
        )

        extra_instructions = (
            "Observação IMPORTANTÍSSIMA:\n"
            "- Sempre que citar qualquer número (KPI ou valor) do JSON, informe o período a que se refere, "
            "usando termos claros (por exemplo: 'Ano Completo de 2024', '1º Trimestre de 2023', '2º Semestre de 2025', etc.).\n"
            "- Explique como chegou ao valor em relação ao período.\n"
            "- As Recomendações (item 4) devem ser embasadas na estratégia e no documento de estratégia fornecido, "
            "mostrando claramente como cada sugestão se conecta aos pilares e objetivos estratégicos.\n"
            "- IMPORTANTE: Considere apenas dados históricos até o último mês do período selecionado no filtro. Nunca utilize dados de meses futuros, mesmo que estejam disponíveis no JSON. O último mês analisado deve ser exatamente o último mês do período escolhido pelo usuário.\n"
        )

        # INSTRUÇÃO ADICIONAL PARA IA:
        # Ao interpretar o resultado, utilize apenas dados históricos até o último mês do período selecionado no dropdown. Nunca utilize dados futuros. Por exemplo, se o período for 1º Trimestre, a análise deve considerar até março, mesmo que o mês atual seja posterior.

        return f"""
Faça uma análise aprofundada do seguinte KPI:

[CONTEXTO ATUAIS DO NEGóCIO]
{indicators_json}

{strategy_context}
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

Por favor, formate sua resposta utilizando Markdown, seguindo estes padrões:
- Utilize "## Título" para o título principal (no lugar de '#').
- Utilize "## Subtítulo" para seções como Diagnóstico Situacional, Análise de Correlações e Causas, Projeções e Cenários, Recomendações Acionáveis e Considerações Estratégicas.

[ESTRUTURA DE ANÁLISE REQUERIDA]

1. **Diagnóstico Situacional (2-3 parágrafos):**
   - Analise o valor atual do {kpi_name} considerando a distância da meta, a comparação com os dados atuais e a tendência histórica.
   - Quantifique o impacto financeiro dessa performance e identifique os principais fatores contribuintes com base no JSON.

2. **Análise de Correlações e Causas (2-3 parágrafos):**
   - Selecione e analise pelo menos 3 KPIs do JSON que tenham correlação significativa com o {kpi_name}.
   - Explique as relações causais, destaque padrões ou anomalias e, se possível, quantifique as correlações.

3. **Projeções e Cenários (1-2 parágrafos):**
   - Projete a tendência do {kpi_name} para os próximos 3 meses, considerando o cenário atual.
   - Estime possíveis riscos e oportunidades baseados nessa projeção.

4. **Recomendações Acionáveis (2-3 parágrafos):**
   - Forneça 3 recomendações prioritárias, com ações específicas e justificativas baseadas no diagnóstico, 
     explicitando como essas ações se conectam aos pilares e objetivos estratégicos do doc de estratégia.
   - Não é necessário indicar prazos, custos ou projeções de receita.

5. **Considerações Estratégicas (1-2 parágrafos):**
   - Avalie como o desempenho do {kpi_name} impacta os pilares estratégicos da empresa.
   - Sugira ajustes estratégicos e identifique possíveis gatilhos para revisão de metas.

DIRETRIZES:
- Utilize linguagem executiva e objetiva, mas de tom natural, sem exageros.
- Fundamente todas as análises em dados concretos do JSON, sempre mencionando os períodos dos dados.
- Seja específico e evite generalidades excessivas.
- Se houver conflitos de dados, priorize as séries históricas consolidadas.
- Inicie sua análise diretamente, sem preâmbulos redundantes.
""".strip()

    def _fallback_gpt(self, kpi_name: str, kpi_values: Dict[str, Any],
                      strategy_info: Dict[str, Any]) -> str:
        """
        Retorno simples para quando a chamada à API da Anthropic falhar.
        """
        return (
            f"Erro: Falha na chamada à API do Claude. Não foi possível obter a interpretação para o KPI '{kpi_name}'."
        )

    def generate_kpi_interpretation_claude(
        self,
        kpi_name: str,
        kpi_values: Dict[str, Any],
        strategy_info: Dict[str, Any],
        all_indicators: Dict[str, Any]
    ) -> str:
        """
        Gera o texto de interpretação do KPI usando o modelo da Anthropic,
        seguindo as diretrizes de prompt definidas nas funções internas.
        """
        # Valida as entradas
        is_valid, resultado_num = self._validate_inputs(kpi_name, kpi_values)
        if not is_valid:
            return resultado_num  # Retorna a mensagem de erro

        # Obtém as informações do KPI
        kpi_info = self.kpi_descriptions.get(kpi_name, {})
        description = kpi_info.get("description", "Descrição não disponível.")
        formula = kpi_info.get("formula", "Fórmula não disponível.")
        periodo = kpi_values.get('periodo', 'Período não informado')
        status = kpi_values.get('status', 'Status não informado')

        # [NOVO] Monta uma chave de cache com dados relevantes
        cache_key = (kpi_name, periodo, status, round(resultado_num, 4))

        # [NOVO] Se a análise desse KPI já foi feita e não houve alteração nos valores, retorna do cache
        if cache_key in self.cache:
            logger.info(f"Retornando análise de cache para {cache_key}")
            return self.cache[cache_key]

        # Monta o prompt final
        human_prompt = self._prepare_human_prompt(
            kpi_name=kpi_name,
            description=description,
            formula=formula,
            periodo=periodo,
            resultado_num=resultado_num,
            status=status,
            all_indicators=all_indicators,
            strategy_info=strategy_info
        )

        # Chamada ao modelo
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Mantendo o modelo que você tinha
                max_tokens=1200,                    # Mantendo a param original
                temperature=0.4,
                system=self._prepare_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": human_prompt
                    }
                ]
            )

            # A forma de extrair a resposta pode mudar se a API do Anthropic alterar.
            # Se você já obtinha a resposta no original assim, mantenha:
            interpretation = response.content[0].text
            if not interpretation:
                return "Erro: Claude não retornou conteúdo."

            # [NOVO] Salva no cache antes de retornar
            self.cache[cache_key] = interpretation.strip()
            return interpretation.strip()

        except Exception as e:
            logger.error(f"Erro ao chamar Anthropic: {str(e)}")
            return self._fallback_gpt(kpi_name, kpi_values, strategy_info)

    def interpret_with_openai(self, prompt: str) -> str:
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


