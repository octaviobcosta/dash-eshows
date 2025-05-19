"""
Mapeia as colunas devolvidas pelo Supabase → nomes padronizados do dashboard
e define quais colunas estão em centavos (para dividir por 100).

• Se surgir coluna nova, adicione o alias em MAPPING
• Se for valor em centavos, inclua no CENTS_MAPPING
"""
from __future__ import annotations

import logging
from typing import Dict, List
import pandas as pd

logger = logging.getLogger("column_mapping")
logger.info("column_mapping importado.")

# ────────────────────────────────────────────────────────────
# 1) BASEESHOWS  –  eventos / contratos
# ────────────────────────────────────────────────────────────
_BASEESHOWS: Dict[str, str] = {
    # Originais (alguns exemplos – adicione todos que existirem no banco)
    "p_ID": "Id do Show",
    "c_ID": "Id da Casa",
    "Casa": "Casa",
    "Cidade": "Cidade",
    "UF": "Estado",
    "Data": "Data do Show",
    "Data_Pagamento": "Data de Pagamento",
    "Artista": "Nome do Artista",
    "Valor_Bruto": "Valor Total do Show",
    "Valor_Total": "Valor Total do Show",
    "Valor_Liquido": "Valor Artista",
    "Comissao_Eshows_B2B": "Comissão B2B",
    "Comissao_Eshows_B2C": "Comissão B2C",
    "Taxa_Adiantamento": "Antecipação de Cachês",
    "Curadoria": "Curadoria",
    "SAAS_Percentual": "SaaS Percentual",
    "SAAS_Mensalidade": "SaaS Mensalidade",
    "Taxa_Emissao_NF": "Notas Fiscais",
    "GRUPO_CLIENTES": "Grupo",
    "NOTA": "Avaliação",
    "Mes": "Mês",
    "Dia": "Dia do Show",
    # Minúsculas / variações comuns
    "p_id": "Id do Show",
    "c_id": "Id da Casa",
    "casa": "Casa",
    "cidade": "Cidade",
    "uf": "Estado",
    "data": "Data do Show",
    "data_pagamento": "Data de Pagamento",
    "artista": "Nome do Artista",
    "valor_bruto": "Valor Total do Show",
    "valor_total": "Valor Total do Show",
    "valor_liquido": "Valor Artista",
    "comissao_eshows_b2b": "Comissão B2B",
    "comissao_eshows_b2c": "Comissão B2C",
    "taxa_adiantamento": "Antecipação de Cachês",
    "curadoria": "Curadoria",
    "saas_percentual": "SaaS Percentual",
    "saas_mensalidade": "SaaS Mensalidade",
    "taxa_emissao_nf": "Notas Fiscais",
    "grupo_clientes": "Grupo",
    "nota": "Avaliação",
    "mes": "Mês",
    "dia": "Dia do Show",
    # Variações com espaços ou camelCase
    "Valor Bruto": "Valor Total do Show",
    "ValorTotaldoShow": "Valor Total do Show",
    "Valor_Total_do_Show": "Valor Total do Show",
    "valor_total_do_show": "Valor Total do Show",
    "Valor Liquido": "Valor Artista",
}

# ────────────────────────────────────────────────────────────
# 2) BASE2  –  financeiro mensal
# ────────────────────────────────────────────────────────────
_BASE2: Dict[str, str] = {
    "Mes Ref": "Mês", "mes ref": "Mês", "mes_ref": "Mês", "mes": "Mês",
    "Ano": "Ano", "ano": "Ano",
    "Custos": "Custos", "custos": "Custos",
    "Imposto": "Imposto", "imposto": "Imposto",
    "Ocupacao": "Ocupação", "Ocupação": "Ocupação", "ocupação": "Ocupação",
    # (adicione outros centros de custo conforme existirem)
}

# ────────────────────────────────────────────────────────────
# 3) BOLETOCASAS / BOLETOARTISTAS
# ────────────────────────────────────────────────────────────
_CASAS: Dict[str, str] = {
    "Casa": "Casa",
    "Valor": "Valor",
    "Valor_Real": "Valor Real",
    "Status": "Status",
    "Data_Vencimento": "Data Vencimento",
    "data_vencimento": "Data Vencimento",
}

_ARTISTAS: Dict[str, str] = {
    "Artista": "Nome do Artista",
    "Valor_Bruto": "Valor Bruto",
    "Status": "Status",
    "Data_Vencimento": "Data Vencimento",
}

# ────────────────────────────────────────────────────────────
# 4) PESSOAS
# ────────────────────────────────────────────────────────────
_PESSOAS: Dict[str, str] = {
    # ─────────────────────────── Datas completas ──────────────────────────
    "DataInicio":  "DataInicio",
    "Data_Inicio": "DataInicio",
    "Data_inicio": "DataInicio",
    "Data Início": "DataInicio",
    "data_inicio": "DataInicio",
    "data_início": "DataInicio",
    "datainicio":  "DataInicio",
    "DataInício":  "DataInicio",

    "DataFinal":   "DataFinal",
    "Data_Fim":    "DataFinal",
    "Data Fim":    "DataFinal",
    "Data_Saida":  "DataFinal",
    "Data_Saída":  "DataFinal",
    "Data Saida":  "DataFinal",
    "Data Saída":  "DataFinal",
    "data_saida":  "DataFinal",
    "data_saída":  "DataFinal",
    "data_fim":    "DataFinal",
    "datafinal":   "DataFinal",
    "DataFim":     "DataFinal",

    # ───────────────────────── Ano / Mês individuais ──────────────────────
    "AnoInicio":   "AnoInicio",
    "ano_inicio":  "AnoInicio",
    "Ano Inicio":  "AnoInicio",
    "MesInicio":   "MesInicio",
    "mes_inicio":  "MesInicio",
    "Mes Inicio":  "MesInicio",
    "AnoFinal":    "AnoFinal",
    "ano_final":   "AnoFinal",
    "Ano Final":   "AnoFinal",
    "MesFinal":    "MesFinal",
    "mes_final":   "MesFinal",
    "Mes Final":   "MesFinal",

    # ───────────────────────────── Salário ────────────────────────────────
    "Salario":       "Salario",
    "salario":       "Salario",
    "Valor_Salario": "Salario",
    "Valor Salario": "Salario",
    "valor_salario": "Salario",

    # ───────────────────────────── Outros ─────────────────────────────────
    "Nome":  "Nome",
    "nome":  "Nome",
    "Cargo": "Cargo",
    "cargo": "Cargo",
}

# ────────────────────────────────────────────────────────────
# 5) METAS  –  (somente se houver renomes necessários)
# ────────────────────────────────────────────────────────────
_METAS: Dict[str, str] = {}

# ────────────────────────────────────────────────────────────
# 6) CUSTOSABERTOS  –  nova tabela (custos em aberto)
# ────────────────────────────────────────────────────────────
_CUSTOSABERTOS: Dict[str, str] = {
    # snake_case originais
    "id_custo":          "Id Custo",
    "grupo_geral":       "Grupo Geral",
    "nivel_1":           "Nivel 1",
    "nivel_2":           "Nivel 2",
    "fornecedor":        "Fornecedor",
    "valor":             "Valor",
    "pagamento":         "Pagamento",
    "data_competencia":  "Data Competencia",
    "data_vencimento":   "Data Vencimento",
    # variações Title Case / camel / espaços (se surgirem)
    "Id_Custo":          "Id Custo",
    "Grupo Geral":       "Grupo Geral",
    "Nivel 1":           "Nivel 1",
    "Nivel 2":           "Nivel 2",
    "Valor":             "Valor",
    "Data Competencia":  "Data Competencia",
    "Data Vencimento":   "Data Vencimento",
}

# 7) NPSARTISTAS – NOVO
_NPSARTISTAS: Dict[str, str] = {
    "id":                 "Id",
    "data":               "Data",
    "nps_eshows":         "NPS Eshows",
    "csat_eshows":        "CSAT Eshows",
    "operador_1":         "Operador 1",
    "operador_2":         "Operador 2",
    "csat_operador_1":    "CSAT Operador 1",
    "csat_operador_2":    "CSAT Operador 2",
    # variações TitleCase (caso venha direto do Excel)
    "ID":                 "Id",
    "Data":               "Data",
    "NPS Eshows":         "NPS Eshows",
    "CSAT Eshows":        "CSAT Eshows",
    "Operador_1":         "Operador 1",
    "Operador_2":         "Operador 2",
    "CSAT Operador_1":    "CSAT Operador 1",
    "CSAT Operador_2":    "CSAT Operador 2",
}

# ────────────────────────────────────────────────────────────
# Dicionário principal
# ────────────────────────────────────────────────────────────
MAPPING: Dict[str, Dict[str, str]] = {
    "baseeshows":     _BASEESHOWS,
    "base2":          _BASE2,
    "boletocasas":    _CASAS,
    "boletoartistas": _ARTISTAS,
    "pessoas":        _PESSOAS,
    "metas":          _METAS,
    "custosabertos":  _CUSTOSABERTOS,
    "npsartistas":    _NPSARTISTAS,    # ← NOVO
}

# ────────────────────────────────────────────────────────────
# Colunas em centavos (dividir por 100)
# ────────────────────────────────────────────────────────────
# Colunas que vêm em centavos
CENTS_MAPPING: Dict[str, List[str]] = {
    "baseeshows": [
        "Valor_Bruto", "Valor Total do Show", "Valor_Total", "Valor Artista",
        "Valor_Liquido", "Comissao_Eshows_B2B", "Comissão B2B",
        "Comissao_Eshows_B2C", "Comissão B2C", "Taxa_Adiantamento",
        "Antecipação de Cachês", "Curadoria", "SAAS_Percentual",
        "SaaS Percentual", "SAAS_Mensalidade", "SaaS Mensalidade",
        "Taxa_Emissao_NF", "Notas Fiscais",
    ],
    "base2": [                 # ← **lista completa**
        "Custos", "Imposto", "Ocupação", "Equipe", "Terceiros", "Op. Shows",
        "D.Cliente", "Softwares", "Mkt", "D.Finan",
        "C. Comercial", "C. Tecnologia", "C. Geral", "C. Recursos Humanos",
        "C. Customer Success", "C. Operações", "C. Novos Produtos",
        "C. Contabilidade", "C. Marketing",
        "Custo Farm", "Custo Hunt",
        "Comercial", "Tech", "Geral", "Financas", "Control",
        "Juridico", "C.Sucess", "Operações", "RH",
    ],
    "boletocasas": [
        "Valor",            # já existia
        "Valor_Real",       # nome original
        "Valor Real",       # <- adicionar
    ],
    "boletoartistas": [
        "Valor_Bruto",      # nome original
        "Valor Bruto",      # <- adicionar
    ],
    "custosabertos": [
        "valor", "Valor",   # ← NOVO
    ],
}

# ────────────────────────────────────────────────────────────
# 7) SUPPLIER → SETOR  (mapeamento solicitado)
# ────────────────────────────────────────────────────────────
SUPPLIER_TO_SETOR: Dict[str, str] = {
    # — Equipe —
    "Kaio Geglio": "Tecnologia",
    "João Vitor Bueno": "Operações",
    "Octavio Costa": "Executivo",
    "Thiago de Mello": "Comercial",
    "Daniel Kumanaya": "Tecnologia",
    "FABLAB INOVACAO E SOLUCOES": "Operações",
    "Fabio Pereira": "Produto",
    "Gabriel Cunha": "Financeiro",
    "Laiz Iervolino": "Operações",
    "TEMPUS FUGIT PARTICIPACOES LTDA": "Geral",
    "Felipe Freitas": "Jurídico e Pessoas",
    "Giovanne Mascaro": "Produto",
    "Giovanna Lemos Conversano": "Operações",
    "Roberta Garcia": "Operações",
    "Sabrina Clemente": "Tecnologia",
    "Tiago Silveira Pompeo de Pina": "Comercial",
    "Gustavo dos Santos Gomes": "Tecnologia",
    "Alekine Nepomuceno": "Operações",
    "Henrique de Melo Silva": "Financeiro",
    "Vitor Bolzan Coelho": "Comercial",
    "Bárbara Fidêncio": "Operações",
    "Nicolas Caichiolo Santos": "Operações",
    "Paulo Gomes": "Operações",
    "RECEITA FEDERAL": "Geral",
    "Lucas Trajano da Silva": "Operações",
    "Vinícius Gabriel": "Tecnologia",
    "Evair Moreno Roberto": "Operações",
    "Guilherme Fernandes Leite": "Financeiro",
    "Italo Kendy Morino Edagi": "Jurídico e Pessoas",
    "Kauã Pereira Mendonça e silva": "Tecnologia",
    "Lucas Vicente Sousa Barbosa": "Tecnologia",
    "Priscila Anacleto": "Executivo",
    "GymPass": "Jurídico e Pessoas",
    "Luisa Fonseca Resende Camerini": "Marketing",
    "FGTS": "Operações",
    "Flash Tecnologia e Instituição de Pagamento LTDA": "Geral",
    "AWS": "Tecnologia",
    "HUBSPOT": "Comercial",
    "INOVABLUE SISTEMAS E SUPORTE LTDA": "Geral",
    "TRANSFEERA INSTITUIÇÃO DE PAGAMENTOS S.A": "Financeiro",
    "GOOGLE GSUITE": "Geral",
    "Picchat": "Operações",
    "KAMINO INSTITUICAO DE PAGAMENTO LTDA": "Financeiro",
    "TELEFONICA BRASIL S/A": "Operações",
    "MONDAYCOM": "Operações",
    "Lexio Tecnologia Ltda": "Jurídico e Pessoas",
    "ADOBE": "Marketing",
    "LINKEDIN": "Jurídico e Pessoas",
    "DOCKER, INC.": "Tecnologia",
    "REPLIT, INC.": "Tecnologia",
    "Paulo Cunha": "Investidor Externo",
    "Marcia Costa": "Investidor Externo",
    "Suellen Nerone": "Investidor Externo",
    "Maria Claudia Gomes": "Investidor Externo",
    "Karine Nerone": "Investidor Externo",
    "ASAAS": "Financeiro",
    "ITAU": "Financeiro",
    "PREFEITURA DE SÃO PAULO": "Geral",
    "CSLL": "Operações",
    "MACRO CONTABILIDADE E CONSULTORIA LTDA": "Geral",
    "MY MUSIC": "Operações",
    "Priscila Anacleto Rodrigues": "Executivo",
    "Fábio Pereira": "Produto",
    "GOOGLE AD": "Marketing",
    # fornecedores sem classificação ficam de fora → resultarão em NaN
}

# ────────────────────────────────────────────────────────────
# 8) COLUNAS PERCENTUAIS — dividir por 100 na carga
# ────────────────────────────────────────────────────────────
PERCENT_COLS = [
    "InadimplenciaReal", "Lucratividade", "NRR", "Perdas_Operacionais",
    "Nivel_Servico", "Churn", "TurnOver", "Ef_Atendimento",
    "Estabilidade", "Crescimento_Sustentavel", "Conformidade_Juridica",
    "NPS_Equipe", "NPS_Contratante", "NPS_Artistas",
]


# ────────────────────────────────────────────────────────────
# Funções utilitárias
# ────────────────────────────────────────────────────────────
def rename_columns(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """
    Aplica o mapping da tabela sobre as colunas do DataFrame.
    """
    mapping = MAPPING.get(table.lower(), {})
    if not mapping:
        return df
    df2 = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    # remove colunas duplicadas após rename
    if df2.columns.duplicated().any():
        df2 = df2.loc[:, ~df2.columns.duplicated(keep="first")]
    return df2


def divide_cents(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """
    Converte de centavos para reais as colunas listadas em CENTS_MAPPING.
    """
    cols = [c for c in CENTS_MAPPING.get(table.lower(), []) if c in df.columns]
    if not cols:
        return df
    df2 = df.copy()
    for col in cols:
        df2[col] = pd.to_numeric(df2[col], errors="coerce").fillna(0) / 100.0
    return df2


