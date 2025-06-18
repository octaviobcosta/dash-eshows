import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
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
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if self.anthropic_api_key:
            self.client = anthropic.Client(api_key=self.anthropic_api_key)
        else:
            self.client = None
            logger.warning("ANTHROPIC_API_KEY não configurada. Interpretações de KPI não estarão disponíveis.")

        # Cache melhorado com TTL
        self.cache = {}
        self.cache_ttl = timedelta(hours=2)  # Cache válido por 2 horas
        
        # Métricas de performance
        self.metrics = {
            "total_calls": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "total_tokens": 0,
            "avg_response_time": 0
        }

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
            "Você é um(a) analista de negócios sênior da Eshows, especializado em análise de crescimento e rentabilidade "
            "no setor de entretenimento e shows. Sua expertise inclui:\n"
            "- Análise profunda de métricas financeiras e operacionais\n"
            "- Identificação de tendências e padrões no mercado de eventos\n"
            "- Recomendações estratégicas baseadas em dados\n\n"
            "DIRETRIZES DE COMUNICAÇÃO:\n"
            "- Use linguagem executiva natural, sem exageros (evite 'extremamente', 'drasticamente')\n"
            "- Seja preciso com números: sempre formate valores monetários com R$ e percentuais com %\n"
            "- Contextualize todos os dados com seus períodos específicos\n"
            "- Priorize insights acionáveis sobre descrições genéricas\n"
            "- Use dados consolidados e ignore duplicações ou conflitos no JSON"
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
            "OBSERVAÇÕES CRÍTICAS:\n"
            "1. PERÍODOS: Sempre cite o período específico ao mencionar números (ex: '1º Trimestre 2024', 'Jan-Jun 2023')\n"
            "2. CÁLCULOS: Mostre brevemente como chegou aos valores derivados\n"
            "3. ESTRATÉGIA: Conecte explicitamente recomendações aos pilares estratégicos\n"
            "4. TEMPORALIDADE: Use apenas dados até o último mês do período filtrado\n"
            "5. QUANTIFICAÇÃO: Prefira números absolutos e relativos (ex: 'R$ 2,3M, alta de 15%')\n"
            "6. BENCHMARKS: Compare com médias do setor quando relevante\n\n"
            "EXEMPLO DE BOA ANÁLISE:\n"
            "'O NRR de 89% no 1º Trimestre 2024 indica retenção abaixo da meta de 95%, "
            "representando uma perda de R$ 450 mil em receita recorrente. Isso correlaciona "
            "com o aumento de 23% no churn (de 8% para 10,2%) no mesmo período.'"
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

## 1. Diagnóstico Situacional
**Objetivo**: Contextualizar o KPI atual com precisão quantitativa
- Valor atual vs Meta: Quantifique gap e impacto financeiro
- Tendência: Compare com períodos anteriores (use dados do JSON)
- Fatores críticos: Identifique 2-3 drivers principais da performance

## 2. Análise de Correlações e Causas
**Objetivo**: Identificar relações causa-efeito com outros KPIs
- Correlações primárias: 3 KPIs mais impactados/impactantes
- Quantificação: Use números para mostrar a força das relações
- Insights: Padrões não óbvios ou anomalias detectadas

## 3. Projeções e Cenários
**Objetivo**: Antecipar tendências com base em dados
- Projeção 3 meses: Baseada na tendência atual
- Cenários: Otimista/Realista/Pessimista com probabilidades
- Riscos principais: Top 2 riscos quantificados

## 4. Recomendações Acionáveis
**Objetivo**: Ações específicas conectadas à estratégia
- Ação 1: [O quê] + [Como] + [Impacto esperado] + [Pilar estratégico]
- Ação 2: [O quê] + [Como] + [Impacto esperado] + [Pilar estratégico]
- Ação 3: [O quê] + [Como] + [Impacto esperado] + [Pilar estratégico]

## 5. Considerações Estratégicas
**Objetivo**: Visão de longo prazo e alinhamento
- Impacto nos pilares: Como afeta cada pilar estratégico
- Gatilhos de revisão: Condições para reavaliar metas
- Oportunidades emergentes: Baseadas nos dados analisados

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

        # Monta uma chave de cache mais completa
        cache_key = (
            kpi_name, 
            periodo, 
            status, 
            round(resultado_num, 4),
            # Adiciona hash dos indicadores principais para invalida cache se dados mudarem
            hash(json.dumps(sorted(all_indicators.items()), default=str)[:1000])
        )

        # Verifica cache com TTL
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                logger.info(f"Cache hit para {kpi_name} - {periodo}")
                self.metrics["cache_hits"] += 1
                self.metrics["total_calls"] += 1
                return cached_data

        # Pré-processa indicadores para remover ruído
        cleaned_indicators = self._preprocess_indicators(all_indicators)
        
        # Monta o prompt final
        human_prompt = self._prepare_human_prompt(
            kpi_name=kpi_name,
            description=description,
            formula=formula,
            periodo=periodo,
            resultado_num=resultado_num,
            status=status,
            all_indicators=cleaned_indicators,  # Usa indicadores limpos
            strategy_info=strategy_info
        )

        # Atualiza métricas
        self.metrics["total_calls"] += 1
        self.metrics["api_calls"] += 1
        
        # Chamada ao modelo com melhorias
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2500,  # Aumentado para análises mais detalhadas
                    temperature=0.3,  # Reduzido para mais consistência
                    top_p=0.95,      # Adiciona diversidade controlada
                    system=self._prepare_system_prompt(),
                    messages=[
                        {
                            "role": "user",
                            "content": human_prompt
                        }
                    ]
                )
                
                # Calcula tempo de resposta
                response_time = time.time() - start_time
                self._update_avg_response_time(response_time)
                
                # Extrai resposta
                interpretation = response.content[0].text
                if not interpretation:
                    return "Erro: Claude não retornou conteúdo."
                
                # Log de métricas de uso (se disponível)
                if hasattr(response, 'usage'):
                    self.metrics["total_tokens"] += response.usage.total_tokens
                    logger.info(f"Tokens usados: {response.usage.total_tokens} | Tempo: {response_time:.2f}s")
                
                # Salva no cache com timestamp
                self.cache[cache_key] = (interpretation.strip(), datetime.now())
                
                # Limpa cache antigo periodicamente
                if len(self.cache) > 100:
                    self._clean_old_cache()
                
                return interpretation.strip()
                
            except anthropic.RateLimitError as e:
                logger.warning(f"Rate limit atingido. Tentativa {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Backoff exponencial
                    continue
                    
            except Exception as e:
                logger.error(f"Erro ao chamar Anthropic (tentativa {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
        
        # Se todas as tentativas falharam, tenta fallback
        return self._fallback_gpt_improved(kpi_name, kpi_values, strategy_info, all_indicators)

    def _update_avg_response_time(self, new_time: float):
        """Atualiza a média de tempo de resposta."""
        total_api_calls = self.metrics["api_calls"]
        if total_api_calls == 1:
            self.metrics["avg_response_time"] = new_time
        else:
            # Média móvel
            self.metrics["avg_response_time"] = (
                (self.metrics["avg_response_time"] * (total_api_calls - 1) + new_time) / total_api_calls
            )
    
    def _clean_old_cache(self):
        """Remove entradas antigas do cache."""
        current_time = datetime.now()
        keys_to_remove = []
        
        for key, (data, cached_time) in self.cache.items():
            if current_time - cached_time > self.cache_ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logger.info(f"Limpou {len(keys_to_remove)} entradas antigas do cache")
    
    def _preprocess_indicators(self, all_indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pré-processa os indicadores para remover ruído e destacar dados relevantes.
        """
        # Remove dados nulos ou vazios
        cleaned = {}
        for key, value in all_indicators.items():
            if value is not None and value != "" and value != {}:
                # Converte valores numéricos string para números
                if isinstance(value, str) and value.replace('.', '').replace(',', '').replace('-', '').isdigit():
                    try:
                        cleaned[key] = float(value.replace(',', '.'))
                    except:
                        cleaned[key] = value
                else:
                    cleaned[key] = value
        
        return cleaned
    
    def _fallback_gpt_improved(self, kpi_name: str, kpi_values: Dict[str, Any],
                               strategy_info: Dict[str, Any], all_indicators: Dict[str, Any]) -> str:
        """
        Fallback melhorado usando GPT-4 quando Claude falha.
        """
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            return f"Erro: Não foi possível gerar análise para o KPI '{kpi_name}'. APIs indisponíveis."
        
        try:
            import openai
            openai.api_key = openai_key
            
            # Usa o mesmo prompt preparado
            human_prompt = self._prepare_human_prompt(
                kpi_name=kpi_name,
                description=self.kpi_descriptions.get(kpi_name, {}).get("description", ""),
                formula=self.kpi_descriptions.get(kpi_name, {}).get("formula", ""),
                periodo=kpi_values.get('periodo', 'Período não informado'),
                resultado_num=kpi_values.get('resultado', 0),
                status=kpi_values.get('status', 'Status não informado'),
                all_indicators=all_indicators,
                strategy_info=strategy_info
            )
            
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": self._prepare_system_prompt()},
                    {"role": "user", "content": human_prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro no fallback GPT: {str(e)}")
            return f"Erro: Não foi possível gerar análise para o KPI '{kpi_name}'."
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorna um resumo das métricas de performance."""
        return {
            "total_calls": self.metrics["total_calls"],
            "cache_hits": self.metrics["cache_hits"],
            "cache_hit_rate": (self.metrics["cache_hits"] / self.metrics["total_calls"] * 100) if self.metrics["total_calls"] > 0 else 0,
            "api_calls": self.metrics["api_calls"],
            "avg_response_time": round(self.metrics["avg_response_time"], 2),
            "total_tokens": self.metrics["total_tokens"],
            "cache_size": len(self.cache)
        }
    
    def interpret_with_openai(self, prompt: str) -> str:
        """Mantido para compatibilidade."""
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content


