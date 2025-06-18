"""
Glossário Detalhado de KPIs - Dashboard eShows
==============================================
Este módulo contém definições precisas de todos os KPIs utilizados no dashboard,
incluindo contexto de negócio, fórmulas e interpretações específicas do setor.
"""

from datetime import datetime, timedelta

# Definições financeiras fundamentais
FINANCIAL_CONCEPTS = {
    "GMV": {
        "nome_completo": "Gross Merchandise Value (Volume Bruto de Mercadorias)",
        "definição": "Volume total transacionado pela plataforma, incluindo todos os valores de ingressos vendidos",
        "contexto": "NO SETOR DE SHOWS: GMV inclui o valor total dos ingressos vendidos, independente de quando o show acontece",
        "importante": "GMV NÃO É RECEITA. É apenas o volume financeiro que passa pela plataforma",
        "exemplo": "Se vendemos R$ 1M em ingressos, o GMV é R$ 1M, mas nossa receita é apenas a comissão"
    },
    "FATURAMENTO": {
        "nome_completo": "Faturamento / Receita Líquida",
        "definição": "Receita efetiva da empresa após impostos, considerando apenas nossa parte (comissões e taxas)",
        "contexto": "É O QUE REALMENTE ENTRA NO CAIXA DA ESHOWS como receita operacional",
        "importante": "Faturamento = Receita Real. Este é o valor que pagamos impostos e calculamos lucro",
        "exemplo": "Se o GMV é R$ 1M e nossa taxa é 10%, o faturamento é R$ 100 mil"
    },
    "RECEITA_BRUTA": {
        "nome_completo": "Receita Bruta Operacional",
        "definição": "Faturamento antes da dedução de impostos diretos sobre vendas",
        "contexto": "Base para cálculo de impostos como ISS, PIS, COFINS",
        "importante": "Receita Bruta ≠ GMV. É nossa parte antes dos impostos",
        "exemplo": "Comissões + taxas de serviço antes de impostos"
    }
}

# Glossário completo de KPIs
KPI_DETAILED_GLOSSARY = {
    "GMV": {
        "nome_display": "GMV - Volume Transacionado",
        "categoria": "Volume",
        "definição": "Valor total de ingressos vendidos através da plataforma",
        "fórmula": "Σ(Valor de todos os ingressos vendidos no período)",
        "unidade": "R$",
        "interpretação": {
            "positiva": "GMV crescente indica aumento no volume de negócios e market share",
            "negativa": "GMV decrescente pode indicar perda de clientes ou redução no tamanho dos eventos",
            "cuidados": "GMV alto não significa lucratividade. Analise sempre com Take Rate e Margem"
        },
        "benchmarks": {
            "excelente": "> R$ 50M/ano",
            "bom": "R$ 20-50M/ano",
            "regular": "R$ 10-20M/ano",
            "preocupante": "< R$ 10M/ano"
        },
        "correlações": ["Take Rate", "Número de Shows", "Ticket Médio"],
        "periodicidade_ideal": "Mensal com análise YoY",
        "valores_anômalos": "Ignore valores zero ou acima de R$ 100M/mês"
    },
    
    "FATURAMENTO_ESHOWS": {
        "nome_display": "Faturamento eShows",
        "categoria": "Receita",
        "definição": "Receita líquida real da empresa (comissões + taxas - impostos)",
        "fórmula": "(GMV × Take Rate) - Impostos diretos",
        "unidade": "R$",
        "interpretação": {
            "positiva": "Crescimento sustentável indica modelo de negócio saudável",
            "negativa": "Queda pode indicar pressão em margens ou perda de volume",
            "cuidados": "Esta é a métrica mais importante para saúde financeira"
        },
        "benchmarks": {
            "excelente": "> 15% do GMV",
            "bom": "10-15% do GMV",
            "regular": "7-10% do GMV",
            "preocupante": "< 7% do GMV"
        },
        "correlações": ["GMV", "Take Rate", "Mix de Produtos", "Eficiência Fiscal"],
        "periodicidade_ideal": "Mensal com análise de tendência trimestral",
        "valores_anômalos": "Desconsidere valores negativos ou > 20% do GMV"
    },
    
    "NRR": {
        "nome_display": "Net Revenue Retention",
        "categoria": "Retenção",
        "definição": "Percentual de receita retida de clientes existentes, incluindo upsell e churn",
        "fórmula": "((Receita Recorrente Atual - Churn + Expansão) / Receita Recorrente Período Anterior) × 100",
        "unidade": "%",
        "interpretação": {
            "positiva": "NRR > 100% indica crescimento orgânico com base atual",
            "negativa": "NRR < 100% indica perda líquida de receita na base",
            "cuidados": "No setor de eventos, sazonalidade afeta muito este KPI"
        },
        "benchmarks": {
            "excelente": "> 120%",
            "bom": "100-120%",
            "regular": "80-100%",
            "preocupante": "< 80%"
        },
        "correlações": ["Churn", "Ticket Médio", "Frequência de Compra", "NPS"],
        "periodicidade_ideal": "Trimestral ou anual (evitar mensal por sazonalidade)",
        "valores_anômalos": "Ignore valores < 0% ou > 200%"
    },
    
    "CHURN": {
        "nome_display": "Taxa de Churn",
        "categoria": "Retenção",
        "definição": "Percentual de clientes ou receita perdida no período",
        "fórmula": "(Clientes Perdidos / Total de Clientes Início do Período) × 100",
        "unidade": "%",
        "interpretação": {
            "positiva": "Churn baixo indica boa retenção e satisfação",
            "negativa": "Churn alto sinaliza problemas de produto ou atendimento",
            "cuidados": "Diferencie churn voluntário (cliente saiu) de involuntário (pagamento falhou)"
        },
        "benchmarks": {
            "excelente": "< 5% mensal",
            "bom": "5-10% mensal",
            "regular": "10-15% mensal",
            "preocupante": "> 15% mensal"
        },
        "correlações": ["NPS", "CAC", "LTV", "Tempo de Resposta Suporte"],
        "periodicidade_ideal": "Mensal com análise de coorte",
        "valores_anômalos": "Questione valores zero ou > 30% mensal"
    },
    
    "CMGR": {
        "nome_display": "Compound Monthly Growth Rate",
        "categoria": "Crescimento",
        "definição": "Taxa de crescimento mensal composta, mostra crescimento sustentável",
        "fórmula": "((Valor Final / Valor Inicial)^(1/número de meses) - 1) × 100",
        "unidade": "%",
        "interpretação": {
            "positiva": "CMGR positivo e estável indica crescimento saudável",
            "negativa": "CMGR negativo ou muito volátil indica instabilidade",
            "cuidados": "Sensível a sazonalidade - analise períodos comparáveis"
        },
        "benchmarks": {
            "excelente": "> 10% mensal",
            "bom": "5-10% mensal",
            "regular": "2-5% mensal",
            "preocupante": "< 2% mensal"
        },
        "correlações": ["GMV", "Número de Novos Clientes", "Market Share"],
        "periodicidade_ideal": "Trimestral ou semestral",
        "valores_anômalos": "Suspeite de valores > 30% ou < -20% mensal"
    },
    
    "TAKE_RATE": {
        "nome_display": "Take Rate",
        "categoria": "Monetização",
        "definição": "Percentual do GMV que se converte em receita para a eShows",
        "fórmula": "(Faturamento / GMV) × 100",
        "unidade": "%",
        "interpretação": {
            "positiva": "Take rate estável ou crescente indica poder de precificação",
            "negativa": "Take rate em queda pode indicar pressão competitiva",
            "cuidados": "Balance take rate com volume - muito alto pode reduzir GMV"
        },
        "benchmarks": {
            "excelente": "> 15%",
            "bom": "10-15%",
            "regular": "7-10%",
            "preocupante": "< 7%"
        },
        "correlações": ["GMV", "Mix de Clientes", "Tipo de Evento"],
        "periodicidade_ideal": "Mensal com análise por segmento",
        "valores_anômalos": "Ignore valores > 30% ou < 3%"
    },
    
    "CAC": {
        "nome_display": "Custo de Aquisição de Cliente",
        "categoria": "Eficiência",
        "definição": "Custo total para adquirir um novo cliente",
        "fórmula": "Total de Gastos em Vendas e Marketing / Número de Novos Clientes",
        "unidade": "R$",
        "interpretação": {
            "positiva": "CAC baixo e estável indica eficiência em aquisição",
            "negativa": "CAC crescente pode indicar saturação de mercado",
            "cuidados": "Compare sempre com LTV para garantir sustentabilidade"
        },
        "benchmarks": {
            "excelente": "< R$ 100",
            "bom": "R$ 100-300",
            "regular": "R$ 300-500",
            "preocupante": "> R$ 500"
        },
        "correlações": ["LTV", "Payback Period", "Canais de Aquisição"],
        "periodicidade_ideal": "Trimestral com análise por canal",
        "valores_anômalos": "Questione valores < R$ 20 ou > R$ 1000"
    },
    
    "LTV": {
        "nome_display": "Lifetime Value",
        "categoria": "Valor do Cliente",
        "definição": "Valor total que um cliente gera durante todo seu relacionamento",
        "fórmula": "(Ticket Médio × Frequência Anual × Anos de Retenção) × Margem",
        "unidade": "R$",
        "interpretação": {
            "positiva": "LTV alto justifica investimentos em retenção",
            "negativa": "LTV baixo indica necessidade de aumentar engajamento",
            "cuidados": "No setor de eventos, considere sazonalidade e ciclos"
        },
        "benchmarks": {
            "excelente": "> R$ 2000",
            "bom": "R$ 1000-2000",
            "regular": "R$ 500-1000",
            "preocupante": "< R$ 500"
        },
        "correlações": ["CAC", "Churn", "Ticket Médio", "Cross-sell"],
        "periodicidade_ideal": "Semestral com análise de coorte",
        "valores_anômalos": "Suspeite de valores > R$ 10.000"
    },
    
    "EBITDA": {
        "nome_display": "EBITDA",
        "categoria": "Lucratividade",
        "definição": "Lucro antes de juros, impostos, depreciação e amortização",
        "fórmula": "Lucro Operacional + Depreciação + Amortização",
        "unidade": "R$",
        "interpretação": {
            "positiva": "EBITDA positivo e crescente indica operação saudável",
            "negativa": "EBITDA negativo requer atenção ao modelo de negócio",
            "cuidados": "Não ignora estrutura de capital - complemente com análise de fluxo de caixa"
        },
        "benchmarks": {
            "excelente": "> 20% do faturamento",
            "bom": "10-20% do faturamento",
            "regular": "0-10% do faturamento",
            "preocupante": "< 0%"
        },
        "correlações": ["Margem Operacional", "Eficiência Operacional", "Escala"],
        "periodicidade_ideal": "Trimestral com análise YoY",
        "valores_anômalos": "Verifique valores > 40% da receita"
    }
}

# Regras de validação temporal
TEMPORAL_RULES = {
    "data_corte": {
        "regra": "Usar dados até o último dia do mês anterior se após dia 10 do mês corrente",
        "explicação": "Dados do mês corrente são incompletos e não devem ser usados para análise",
        "exemplo": "Em 15 de junho, analisar até 31 de maio"
    },
    "comparação_períodos": {
        "regra": "Comparar sempre períodos completos e equivalentes",
        "explicação": "Evita distorções por períodos incompletos",
        "exemplo": "Q1 2024 vs Q1 2023, não Q1 2024 vs Q1 parcial 2023"
    },
    "sazonalidade": {
        "regra": "Considerar sazonalidade do setor de eventos",
        "explicação": "Dezembro/Janeiro são fracos, Maio/Setembro são fortes",
        "ajuste": "Usar médias móveis ou comparação YoY"
    }
}

# Valores a serem filtrados
ANOMALY_FILTERS = {
    "percentuais": {
        "ignorar_se_igual": [0, 100, -100],
        "suspeitar_se_maior": 200,
        "suspeitar_se_menor": -50
    },
    "valores_absolutos": {
        "gmv_mensal_max": 100_000_000,  # R$ 100M
        "faturamento_mensal_max": 20_000_000,  # R$ 20M
        "valores_negativos": ["GMV", "Faturamento", "LTV", "CAC"]
    },
    "consistência": {
        "take_rate_range": (3, 30),  # Entre 3% e 30%
        "churn_range": (0, 30),  # Entre 0% e 30%
        "nrr_range": (50, 200)  # Entre 50% e 200%
    }
}

def get_kpi_context(kpi_name: str) -> dict:
    """Retorna contexto completo de um KPI específico."""
    return KPI_DETAILED_GLOSSARY.get(kpi_name.upper(), {})

def get_financial_concept(concept: str) -> dict:
    """Retorna definição de conceito financeiro."""
    return FINANCIAL_CONCEPTS.get(concept.upper(), {})

def is_value_anomalous(kpi_name: str, value: float) -> bool:
    """Verifica se um valor é anômalo para determinado KPI."""
    if kpi_name in KPI_DETAILED_GLOSSARY:
        kpi_info = KPI_DETAILED_GLOSSARY[kpi_name]
        
        # Verifica valores específicos a ignorar
        if value in ANOMALY_FILTERS["percentuais"]["ignorar_se_igual"]:
            return True
            
        # Verifica ranges específicos do KPI
        if "valores_anômalos" in kpi_info:
            # Implementar lógica específica baseada na descrição
            pass
            
    return False

def get_analysis_cutoff_date():
    """
    Retorna a data limite para análise considerando fechamento mensal.
    Se estamos antes do dia 10, usa 2 meses atrás. Senão, usa mês anterior.
    """
    today = datetime.now()
    
    if today.day <= 10:
        # Estamos no início do mês, dados do mês anterior ainda não fecharam
        # Voltar para o primeiro dia do mês atual
        first_day_current = today.replace(day=1)
        # Voltar um mês
        last_day_two_months_ago = first_day_current - timedelta(days=1)
        # Voltar para o último dia do mês retrasado
        return last_day_two_months_ago.replace(day=1) - timedelta(days=1)
    else:
        # Após dia 10, mês anterior já fechou
        first_day_current = today.replace(day=1)
        return first_day_current - timedelta(days=1)

def get_temporal_context() -> str:
    """Retorna explicação sobre o período válido para análise."""
    cutoff = get_analysis_cutoff_date()
    today = datetime.now()
    
    return f"""
[CONTEXTO TEMPORAL]
Data de corte para análise: {cutoff.strftime('%d/%m/%Y')}
Hoje: {today.strftime('%d/%m/%Y')}
Razão: {TEMPORAL_RULES['data_corte']['explicação']}"""