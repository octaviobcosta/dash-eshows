import os
import sys
import json
import numbers
import calendar
import logging
import re
import math
import unicodedata
import ast
import textwrap
from datetime import datetime, timedelta
import gc

import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta

# =================================================================================
# IMPORTAÇÃO DE FUNÇÕES DE CARREGAMENTO (modulobase) E FORMATAÇÃO (utils)
# =================================================================================
from .modulobase import (
    carregar_base_eshows,
    carregar_eshows_excluidos,  # p/ exportar as linhas excluídas
    carregar_base2,
    carregar_ocorrencias,
    carregar_base_inad,
    carregar_pessoas,
    carregar_npsartistas
)

logger = logging.getLogger(__name__)

# =================================================================================
# CARREGAMENTO DAS BASES GERAIS (removido uso de variáveis globais duplicadas)
# =================================================================================
# Utilize carregar_base_eshows(), carregar_base2(), carregar_ocorrencias() etc. sempre que precisar dos dados.

# Load global DataFrames for util functions
try:
    df_eshows = carregar_base_eshows()
    df_base2 = carregar_base2()
    df_ocorrencias = carregar_ocorrencias()
    df_inad = carregar_base_inad()
    df_pessoas = carregar_pessoas()
    df_npsartistas = carregar_npsartistas()
except Exception:
    df_eshows = df_base2 = df_ocorrencias = df_inad = df_pessoas = df_npsartistas = None

def ensure_grupo_col(df):
    """
    Garante que o DataFrame tenha a coluna 'Grupo'.
    · Se já existe, devolve inalterado.
    · Se encontrar outra coluna cujo nome contenha 'grupo', renomeia para 'Grupo'.
    · Caso contrário, cria a coluna vazia.
    """
    if df is None or df.empty:
        return df
    if 'Grupo' in df.columns:
        return df
    possiveis = [c for c in df.columns if 'grupo' in c.lower()]
    if possiveis:
        df = df.rename(columns={possiveis[0]: 'Grupo'})
    else:
        df['Grupo'] = None
    return df

# ===============================
# Mapeamento de Bases dos KPIs
# ===============================
kpi_bases_mapping = {
    "CMGR": ["eshows"],
    "Lucratividade": ["eshows", "base2"],
    "Net Revenue Retention": ["eshows"],
    "EBITDA": ["eshows", "base2"],
    "Receita por Colaborador": ["eshows", "pessoas"],
    "Inadimplência": ["eshows", "inad"],
    "Estabilidade": ["base2"],
    "Nível de Serviço": ["eshows", "ocorrencias"],
    "Churn %": ["eshows"],
    "Turn Over": ["pessoas"],
    "Palcos Vazios": ["ocorrencias"],
    "Perdas Operacionais": ["eshows", "base2"],
    "Crescimento Sustentável": ["eshows", "base2"],
    "Perfis Completos": ["base2"],
    "Take Rate": ["eshows"],
    "Autonomia do Usuário": ["base2"],
    "NPS Artistas": ["npsartistas"],
    "NPS Equipe": ["base2"],
    "Conformidade Jurídica": ["base2"],
    "Eficiência de Atendimento": ["base2"],
    "Inadimplência Real": ["eshows", "inad"],
    "Sucesso da Implantação": ["eshows", "base2"],
    "Roll 6M Growth": ["eshows"],
    "Eficiência Comercial": ["eshows", "base2"],

}

# =================================================================================
# FUNÇÕES AUXILIARES base2 / Ocorrências etc.
# =================================================================================
def filtrar_base2(df_b2, ano, periodo, mes, custom_range=None):
    """
    Exemplo: Filtra df_base2 para pegar Custos no período (coluna 'Custos').
    Se custom_range for fornecido e a coluna 'Data' existir, ele terá prioridade.
    """
    if df_b2 is None or df_b2.empty:
        return None # Mantido como None para consistência com chamadas anteriores que podem esperar None
    
    df_temp = df_b2.copy()

    # Filtro primário por custom_range se aplicável e 'Data' existir
    if custom_range and isinstance(custom_range, tuple) and len(custom_range) == 2 and 'Data' in df_temp.columns:
        start_cr, end_cr = custom_range
        if start_cr and end_cr:
            try:
                df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce')
                mask_cr = (df_temp['Data'] >= pd.to_datetime(start_cr)) & (df_temp['Data'] <= pd.to_datetime(end_cr))
                df_temp = df_temp[mask_cr]
                if df_temp.empty: # Se o filtro por custom_range zerar o DF, não há o que somar
                    return 0.0
            except Exception as e:
                logger.debug("Erro ao aplicar custom_range em filtrar_base2: %s", e)
                # Decide se retorna None/0.0 ou continua para filtro por ano/mês
                # Por ora, continua, mas o resultado pode ser inesperado se o custom_range era mandatório.

    # Lógica original de filtro por Ano/Mês (aplicada ao df_temp já potencialmente filtrado por custom_range)
    if ("Ano" not in df_temp.columns) or ("Mês" not in df_temp.columns) or ("Custos" not in df_temp.columns):
        # Se após o filtro de custom_range (ou se não houve) as colunas essenciais não existem, retorna None ou 0.
        # Retornando 0 para manter a consistência do tipo de retorno se 'Custos' não existir.
        return 0.0 

    df_temp["Ano"] = pd.to_numeric(df_temp["Ano"], errors='coerce')
    df_temp["Mês"] = pd.to_numeric(df_temp["Mês"], errors='coerce')
    df_temp["Custos"] = pd.to_numeric(df_temp["Custos"], errors='coerce').fillna(0)

    # A função filtrar_periodo_principal será chamada com o custom_range já aplicado (se foi o caso)
    # ou com o df_temp original se custom_range não foi aplicado ou não era aplicável.
    # Se custom_range foi aplicado, o filtro por ano/periodo/mes pode ser redundante ou refinar mais.
    # Se custom_range FOI usado, passar None para custom_range em filtrar_periodo_principal
    # para que ele use a lógica de ano/periodo/mes sobre o dataframe já filtrado pelo custom_range de datas.
    df_filtrado = filtrar_periodo_principal(df_temp, ano, periodo, mes, None) 
    if df_filtrado.empty:
        return 0.0

    soma_ = df_filtrado["Custos"].sum()
    return float(soma_)

def filtrar_base2_comparacao(df_b2, ano, periodo, mes, comparar_opcao, custom_range_comparacao=None):
    """
    Filtra df_base2 p/ comparação, usando as mesmas regras do app.
    """
    if df_b2 is None or df_b2.empty:
        return 0 # Retornando 0 para manter consistência de tipo se não há o que somar

    df_temp = df_b2.copy()
    # Passa custom_range_comparacao para filtrar_periodo_comparacao
    df_comp = filtrar_periodo_comparacao(df_temp, ano, periodo, mes, comparar_opcao, custom_range_comparacao)
    if df_comp.empty:
        return 0
    if "Custos" in df_comp.columns:
        df_comp["Custos"] = pd.to_numeric(df_comp["Custos"], errors='coerce').fillna(0)
        return df_comp["Custos"].sum()
    return 0

def filtrar_base2_op_shows(df_b2, ano, periodo, mes):
    """Filtra df_base2 para pegar 'Op. Shows' (erros operacionais) no período."""
    if df_b2 is None or df_b2.empty:
        return 0
    if ("Ano" not in df_b2.columns) or ("Mês" not in df_b2.columns):
        return 0

    df_filtrado = filtrar_periodo_principal(df_b2, ano, periodo, mes, None)
    if df_filtrado.empty:
        return 0
    if "Op. Shows" not in df_filtrado.columns:
        return 0

    df_filtrado["Op. Shows"] = pd.to_numeric(df_filtrado["Op. Shows"], errors='coerce').fillna(0)
    return df_filtrado["Op. Shows"].sum()

def filtrar_base2_op_shows_compare(df_b2, ano, periodo, mes, comparar_opcao):
    if df_b2 is None or df_b2.empty:
        return 0
    df_comp = filtrar_periodo_comparacao(df_b2, ano, periodo, mes, comparar_opcao, None)
    if df_comp.empty or ("Op. Shows" not in df_comp.columns):
        return 0
    df_comp["Op. Shows"] = pd.to_numeric(df_comp["Op. Shows"], errors='coerce').fillna(0)
    return df_comp["Op. Shows"].sum()

# =================================================================================
# FUNÇÕES DE CÁLCULO DE PERÍODO
# =================================================================================


def _is_valid_range(rng):
    """True se rng for (start, end) válido."""
    return (
        isinstance(rng, (list, tuple))
        and len(rng) == 2
        and rng[0] not in (None, "", pd.NaT)
        and rng[1] not in (None, "", pd.NaT)
    )


def get_period_start(ano: int, periodo: str, mes: int | None, custom_range=None):
    """
    Retorna a data inicial do intervalo a partir da combinação
    (ano, periodo, mes).  
    • Se `custom_range` for (start, end) válido – e start não for None –
      ele tem prioridade, mesmo que `periodo` não seja 'custom-range'.  
    • Tratei explicitamente casos em que `custom_range` chega como
      DataFrame/Series (evita "truth value of DataFrame is ambiguous").
    """
    if _is_valid_range(custom_range):
        start_d, _ = custom_range
        if start_d not in (None, "", pd.NaT):
            return pd.to_datetime(start_d, errors="coerce")
        # << FALLBACK SE custom_range é inválido mas periodo é 'custom-range' >>
        elif periodo == "custom-range":
            logger.debug(
                "[get_period_start] Aviso: 'custom-range' selecionado mas data inicial inválida. Usando início do ano."
            )
            return datetime(ano, 1, 1)  # Fallback

    # ------------------------------------------------------------------
    # Demais opções de período
    # ------------------------------------------------------------------
    periodo = (periodo or "").strip()

    if periodo == "custom-range" and _is_valid_range(custom_range):
        start_d, _ = custom_range
        return pd.to_datetime(start_d, errors="coerce")

    if periodo == "Mês Aberto" and mes:
        return datetime(ano, mes, 1)

    if periodo == "Ano Completo":
        return datetime(ano, 1, 1)

    if periodo == "YTD":
        return datetime(ano, 1, 1)

    tri_start = {
        "1° Trimestre": (1, 1),
        "2° Trimestre": (4, 1),
        "3° Trimestre": (7, 1),
        "4° Trimestre": (10, 1),
    }
    if periodo in tri_start:
        mm, dd = tri_start[periodo]
        return datetime(ano, mm, dd)

    # fallback seguro final (se nenhuma outra condição bateu)
    return datetime(ano, 1, 1)

# =====================================================================
# AJUSTE FINAL  –  get_period_end
# =====================================================================
def get_period_end(ano: int, periodo: str, mes: int | None, custom_range=None):
    """
    Retorna a data final do intervalo.

    • Para 'custom-range' → devolve a data do próprio range.
    • Para 'YTD' → encerra sempre no mês fechado:
        ‣ Se `mes` for None  ➜ mês corrente – 1
        ‣ Se `mes` ≥ mês corrente ➜ mês corrente – 1
        ‣ Caso contrário (usuário escolheu Jan–Abr manualmente) ➜ usa o mês dado.
    • Mantém regras originais p/ Mês Aberto, Trimestres, Ano Completo.
    """


    # helper interno (validador de custom_range)
    def _is_valid_range(rng):
        return (
            isinstance(rng, (list, tuple))
            and len(rng) == 2
            and rng[0] not in (None, "", pd.NaT)
            and rng[1] not in (None, "", pd.NaT)
        )

    # 1) custom range explícito -------------------------------------------------
    if _is_valid_range(custom_range):
        _, end_d = custom_range
        return pd.to_datetime(end_d, errors="coerce")

    periodo = (periodo or "").strip()

    # 2) Mês Aberto -------------------------------------------------------------
    if periodo == "Mês Aberto" and mes:
        last_day = calendar.monthrange(ano, mes)[1]
        return datetime(ano, mes, last_day)

    # 3) Ano Completo -----------------------------------------------------------
    if periodo == "Ano Completo":
        return datetime(ano, 12, 31)

    # 4) Y T D  (padronizado) ---------------------------------------------------
    if periodo == "YTD":
        current_month = datetime.now().month
        # Se mes for None ou cair no mês/ano corrente, recua 1 mês
        if mes is None or mes >= current_month:
            ref_mes = current_month - 1
            if ref_mes < 1:   # estamos em janeiro
                ref_mes = 1
        else:
            ref_mes = mes
        last_day = calendar.monthrange(ano, ref_mes)[1]
        return datetime(ano, ref_mes, last_day)

    # 5) Trimestres -------------------------------------------------------------
    tri_end = {
        "1° Trimestre": (3, 31),
        "2° Trimestre": (6, 30),
        "3° Trimestre": (9, 30),
        "4° Trimestre": (12, 31),
    }
    if periodo in tri_end:
        mm, dd = tri_end[periodo]
        return datetime(ano, mm, dd)

    # 6) fallback seguro --------------------------------------------------------
    return datetime(ano, 12, 31)

def get_period_range(ano, periodo, mes, custom_range):
    """Retorna (start_date, end_date) baseado na opção de período."""
    start = get_period_start(ano, periodo, mes, custom_range)
    end = get_period_end(ano, periodo, mes, custom_range)
    return start, end


# =================================================================================
# FILTRAR PERÍODO PRINCIPAL
# =================================================================================

def filtrar_periodo_principal(df, ano, periodo, mes, custom_range):
    """
    Filtra um DataFrame pelo intervalo determinado em (ano, periodo, mes, custom_range).

    Regras:
    ───────
    ① Procura qualquer coluna de data em `DATE_COLS`
       e filtra pelo intervalo (start_d … end_d).  
    ② Se não encontrar, usa combinação 'Ano' + 'Mês'.  
    ③ Caso contrário, devolve DataFrame vazio.
    """

    if df is None or df.empty:
        logger.debug(
            "[filtrar_periodo_principal] DataFrame vazio para ano=%s, periodo=%s, mes=%s, custom_range=%s",
            ano,
            periodo,
            mes,
            custom_range,
        )
        return pd.DataFrame()

    # calcula limites
    start_d = get_period_start(ano, periodo, mes, custom_range)
    end_d   = get_period_end(ano, periodo, mes, custom_range)
    logger.debug(
        "[filtrar_periodo_principal] ano=%s, periodo=%s, mes=%s, custom_range=%s",
        ano,
        periodo,
        mes,
        custom_range,
    )
    logger.debug(
        "[filtrar_periodo_principal] start_d=%s, end_d=%s",
        start_d,
        end_d,
    )

    df_ = df.copy()
    linhas_antes = len(df_)

    # ──────── AJUSTE: múltiplas colunas possíveis de data ────────
    DATE_COLS = ["Data", "Data do Show", "Data de Pagamento"]
    for col in DATE_COLS:
        if col in df_.columns:
            df_[col] = pd.to_datetime(df_[col], errors="coerce")
            mask = (df_[col] >= start_d) & (df_[col] <= end_d)
            df_filtrado = df_[mask].copy()
            logger.debug(
                "[filtrar_periodo_principal] (via '%s') Linhas antes: %s, depois: %s",
                col,
                linhas_antes,
                len(df_filtrado),
            )
            return df_filtrado
    # ──────────────────────────────────────────────────────────────

    # caminho com Ano / Mês
    if "Ano" in df_.columns and "Mês" in df_.columns:
        df_["Ano"] = pd.to_numeric(df_["Ano"], errors="coerce")
        df_["Mês"] = pd.to_numeric(df_["Mês"], errors="coerce")
        start_ano, start_mes = start_d.year, start_d.month
        end_ano,   end_mes   = end_d.year,   end_d.month
        df_["AnoMes"] = df_["Ano"] * 100 + df_["Mês"]
        min_val = start_ano * 100 + start_mes
        max_val = end_ano   * 100 + end_mes
        df_filtrado = df_[(df_["AnoMes"] >= min_val) &
                          (df_["AnoMes"] <= max_val)].copy()
        logger.debug(
            "[filtrar_periodo_principal] (via Ano/Mês) Linhas antes: %s, depois: %s",
            linhas_antes,
            len(df_filtrado),
        )
        return df_filtrado

    logger.debug("[filtrar_periodo_principal] DataFrame sem colunas de data válidas. Retornando vazio.")
    return pd.DataFrame()


# utils.py  –  substituir a função toda
def calcular_periodo_anterior(ano: int, periodo: str, mes: int | None):
    """
    Devolve uma tupla (periodo_anterior, ano_anterior, mes_anterior) seguindo
    o conceito de período cronologicamente imediato:

        • 2° Trimestre/2025 → 1° Trimestre/2025
        • 1° Trimestre/2025 → 4° Trimestre/2024
        • Fev/2025 (Mês Aberto, mes=2) → Jan/2025
        • Jan/2025 → Dez/2024
        • Ano Completo/2025 → Ano Completo/2024
    """
    # ---------- MÊS ABERTO ----------
    if periodo == "Mês Aberto" and mes:
        if mes == 1:         # Janeiro → Dezembro do ano anterior
            return ("Mês Aberto", ano - 1, 12)
        return ("Mês Aberto", ano, mes - 1)

    # ---------- TRIMESTRES ----------
    if "Trimestre" in periodo:
        try:
            trim_atual = int(periodo.split("°")[0])
        except (ValueError, IndexError):
            # Se o texto estiver fora do padrão, mantém fallback antigo
            return (periodo, ano - 1, mes)

        if trim_atual == 1:   # 1º → 4º do ano anterior
            return ("4° Trimestre", ano - 1, None)
        return (f"{trim_atual - 1}° Trimestre", ano, None)

    # ---------- ANO COMPLETO ----------
    if periodo == "Ano Completo":
        return ("Ano Completo", ano - 1, None)

    # ---------- YTD ----------
    if periodo == "YTD":
        # Se vier um mês do dropdown (ex.: 4 = abr) voltamos 1.
        if mes and mes > 1:
            return ("YTD", ano, mes - 1)

        # Se não veio mês, usamos o mês atual do sistema
        mes_atual = datetime.now().month
        if mes_atual == 1:               # Jan/2025 → compara com Ano Completo/2024
            return ("Ano Completo", ano - 1, None)
        return ("YTD", ano, mes_atual - 1)


def filtrar_periodo_comparacao(df, ano, periodo, mes, comparar_opcao, datas_comparacao=None):
    """
    Filtra o DataFrame para o período de comparação.
    `datas_comparacao` é um tuple (start_date, end_date) para `comparar_opcao == 'custom-compare'`.
    `periodo` e `mes` aqui referem-se ao período *principal* para calcular o comparativo corretamente.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    start_date_principal_obj = get_period_start(ano, periodo, mes, datas_comparacao if periodo == 'custom-range' else None)
    end_date_principal_obj   = get_period_end(ano, periodo, mes, datas_comparacao if periodo == 'custom-range' else None)


    if comparar_opcao == "ano_anterior":
        ano_comp = ano - 1
        mes_comp = mes
        periodo_comp = periodo
        
        # Se o período principal é custom-range, calcula custom_range para o ano anterior
        if periodo == "custom-range" and start_date_principal_obj and end_date_principal_obj:
            start_date_compare = start_date_principal_obj - pd.DateOffset(years=1)
            end_date_compare = end_date_principal_obj - pd.DateOffset(years=1)
            return filtrar_periodo_principal(df, ano_comp, periodo_comp, mes_comp, (start_date_compare, end_date_compare))
        else:
            return filtrar_periodo_principal(df, ano_comp, periodo_comp, mes_comp, None)

    elif comparar_opcao == "periodo_anterior":
        periodo_comp, ano_comp, mes_comp = calcular_periodo_anterior(ano, periodo, mes)
        
        # Se o período principal é custom-range, calcula o período anterior com a mesma duração
        if periodo == "custom-range" and start_date_principal_obj and end_date_principal_obj:
            duration = end_date_principal_obj - start_date_principal_obj
            end_date_compare = start_date_principal_obj - pd.Timedelta(days=1)
            start_date_compare = end_date_compare - duration
            # Usamos o ano e mês do start_date_compare para que get_period_start/end funcione corretamente dentro de filtrar_periodo_principal
            # ou passamos diretamente o range.
            return filtrar_periodo_principal(df, start_date_compare.year, 'custom-range', start_date_compare.month, (start_date_compare, end_date_compare))
        else:
            return filtrar_periodo_principal(df, ano_comp, periodo_comp, mes_comp, None)
            
    elif comparar_opcao == "custom-compare":
        if datas_comparacao and datas_comparacao[0] and datas_comparacao[1]:
            # Para custom-compare, o ano e mes não importam tanto quanto o range explícito
            return filtrar_periodo_principal(df, ano, "custom-range", mes, datas_comparacao)
        else:
            return pd.DataFrame() # Retorna DataFrame vazio se não houver datas válidas

    return pd.DataFrame() # Fallback


# =================================================================================
# MES NOME INTERVALO (P/ EXIBIR)
# =================================================================================

def mes_nome(m):
    mapa = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return mapa.get(m, str(m))

def mes_nome_intervalo(df_filtrado, periodo):
    """
    Retorna uma string como "Janeiro/24 até Fevereiro/24",
    ou "Janeiro/24", se for Mês Aberto. Exibe apenas os dois
    últimos dígitos do ano.
    Se df_filtrado estiver vazio, retorna "Sem dados".
    """
    if df_filtrado is None or df_filtrado.empty:
        return "Sem dados"

    # Caso 1: se tiver 'Data'
    if "Data" in df_filtrado.columns:
        dmin = pd.to_datetime(df_filtrado["Data"], errors='coerce').min()
        dmax = pd.to_datetime(df_filtrado["Data"], errors='coerce').max()
        if pd.isna(dmin) or pd.isna(dmax):
            return "Sem dados"

        min_y = dmin.year
        max_y = dmax.year
        min_m = dmin.month
        max_m = dmax.month

        # Converte ano para 2 dígitos => str(...)[2:]
        min_y_2d = str(min_y)[2:]
        max_y_2d = str(max_y)[2:]

        # Se "Mês Aberto" ou se range é só um mês
        if periodo == 'Mês Aberto' or (min_m == max_m and min_y == max_y):
            return f"{mes_nome(min_m)}/{min_y_2d}"
        else:
            return f"{mes_nome(min_m)}/{min_y_2d} até {mes_nome(max_m)}/{max_y_2d}"

    # Caso 2: se tiver 'Ano' e 'Mês'
    if ("Ano" in df_filtrado.columns) and ("Mês" in df_filtrado.columns):
        df_filtrado["Ano"] = pd.to_numeric(df_filtrado["Ano"], errors='coerce')
        df_filtrado["Mês"] = pd.to_numeric(df_filtrado["Mês"], errors='coerce')

        min_ano = int(df_filtrado["Ano"].min())
        max_ano = int(df_filtrado["Ano"].max())
        min_mes = int(df_filtrado["Mês"].min())
        max_mes = int(df_filtrado["Mês"].max())

        min_ano_2d = str(min_ano)[2:]
        max_ano_2d = str(max_ano)[2:]

        # Se for Mês Aberto ou se range é do mesmo mês/ano
        if periodo == 'Mês Aberto' or (min_mes == max_mes and min_ano == max_ano):
            return f"{mes_nome(min_mes)}/{min_ano_2d}"
        else:
            return f"{mes_nome(min_mes)}/{min_ano_2d} até {mes_nome(max_mes)}/{max_ano_2d}"

    return "Sem dados"

def carregar_kpi_descriptions(caminho_relativo='data/kpi_descriptions.json'):
    """
    Carrega o arquivo JSON de descrições de KPIs.

    :param caminho_relativo: Caminho relativo para o arquivo JSON.
    :return: Dicionário com as descrições dos KPIs.
    """
    # Obter o diretório atual do arquivo utils.py
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_absoluto = os.path.join(diretorio_atual, caminho_relativo)

    logger.debug("Carregando kpi_descriptions.json de: %s", caminho_absoluto)

    if not os.path.exists(caminho_absoluto):
        raise FileNotFoundError(f"O arquivo {caminho_absoluto} não foi encontrado.")

    with open(caminho_absoluto, 'r', encoding="utf-8") as file:
        kpi_descriptions = json.load(file)

    return kpi_descriptions

# =================================================================================
# TOP5 GRUPOS
# =================================================================================
def obter_top5_grupos_ano_anterior(df, ano):
    logger.debug("[obter_top5_grupos_ano_anterior] Iniciando para ano base: %s", ano)
    if df is None or df.empty:
        logger.debug("[obter_top5_grupos_ano_anterior] Erro: DataFrame de entrada está vazio ou None.")
        return []
    if "Grupo" not in df.columns:
        logger.debug("[obter_top5_grupos_ano_anterior] Erro: Coluna 'Grupo' não encontrada no DataFrame.")
        return []

    prev_year = ano - 1
    logger.debug("[obter_top5_grupos_ano_anterior] Filtrando para o ano anterior: %s", prev_year)
    if "Ano" not in df.columns:
        logger.debug("[obter_top5_grupos_ano_anterior] Erro: Coluna 'Ano' não encontrada para filtrar.")
        return []

    # Garantir que 'Ano' seja numérico antes de filtrar
    df["Ano"] = pd.to_numeric(df["Ano"], errors='coerce')
    df_prev = df[df["Ano"] == prev_year].copy()

    if df_prev.empty:
        logger.debug("[obter_top5_grupos_ano_anterior] Nenhum dado encontrado para o ano %s.", prev_year)
        return []
    logger.debug(
        "[obter_top5_grupos_ano_anterior] Dados encontrados para %s: %s linhas.",
        prev_year,
        len(df_prev),
    )

    colunas_fat = [
        "Comissão B2B","Comissão B2C","Antecipação de Cachês",
        "Curadoria","SaaS Percentual","SaaS Mensalidade","Notas Fiscais"
    ]
    valid_cols = [c for c in colunas_fat if c in df_prev.columns]
    if not valid_cols:
        logger.debug("[obter_top5_grupos_ano_anterior] Erro: Nenhuma coluna de faturamento válida encontrada.")
        return []
    logger.debug(
        "[obter_top5_grupos_ano_anterior] Colunas de faturamento válidas: %s",
        valid_cols,
    )

    for c in valid_cols:
        df_prev[c] = pd.to_numeric(df_prev[c], errors='coerce').fillna(0)
    df_prev["FatGrupo"] = df_prev[valid_cols].sum(axis=1)

    logger.debug("[obter_top5_grupos_ano_anterior] Agrupando faturamento por Grupo...")
    df_gp = df_prev.groupby("Grupo")["FatGrupo"].sum().reset_index()
    df_gp.sort_values("FatGrupo", ascending=False, inplace=True)

    logger.debug(
        "[obter_top5_grupos_ano_anterior] Faturamento por grupo (Top 10): %s",
        df_gp.head(10),
    )

    top5 = df_gp.head(5)
    if top5.empty:
        logger.debug("[obter_top5_grupos_ano_anterior] Top 5 grupos está vazio após agregação.")
        return []

    ret = []
    for _, row in top5.iterrows():
        # Ensure group name is not None/NaN and revenue is positive
        if pd.notna(row["Grupo"]) and row["FatGrupo"] > 0:
             ret.append((row["Grupo"], row["FatGrupo"]))

    logger.debug("[obter_top5_grupos_ano_anterior] Retornando top 5: %s", ret)
    return ret

def faturamento_dos_grupos(df_, list_grp):
    if not list_grp or df_ is None or df_.empty:
        return 0.0
    grp_names = [item[0] for item in list_grp]
    df_sub = df_[df_["Grupo"].isin(grp_names)].copy()
    if df_sub.empty:
        return 0.0
    colunas_fat = [
        "Comissão B2B","Comissão B2C","Antecipação de Cachês",
        "Curadoria","SaaS Percentual","SaaS Mensalidade","Notas Fiscais"
    ]
    valid_cols = [c for c in colunas_fat if c in df_sub.columns]
    if not valid_cols:
        return 0.0
    total_fat = 0.0
    for c in valid_cols:
        df_sub[c] = pd.to_numeric(df_sub[c], errors='coerce').fillna(0)
        total_fat += df_sub[c].sum() # Sum column by column
    return float(total_fat) # Return the total sum

def novos_palcos_dos_grupos(df_new_period, df_principal, list_grp):
    if not list_grp or df_new_period is None or df_new_period.empty or df_principal is None or df_principal.empty: # Check 1: Inputs valid
        return 0
    if "Id da Casa" not in df_new_period.columns or "Id da Casa" not in df_principal.columns or "Grupo" not in df_principal.columns:  # Check 2: Columns exist
        logger.debug("[novos_palcos_dos_grupos] Missing required columns ('Id da Casa' or 'Grupo')")
        return 0
    grp_names = [item[0] for item in list_grp]
    new_ids = df_new_period["Id da Casa"].unique()
    df_map = df_principal[["Id da Casa","Grupo"]].drop_duplicates()
    df_map = df_map[df_map["Id da Casa"].isin(new_ids)]
    df_map = df_map[df_map["Grupo"].isin(grp_names)]
    return df_map["Id da Casa"].nunique()

def get_churn_ka_for_period(ano, periodo, mes, top5_list, start_date_main=None, end_date_main=None, dias_sem_show=45):
    """
    Calcula o churn de Key Accounts (contas-chave) para um determinado período.
    Refatorado para calcular churn que *ocorre* no período (data_churn_tech cai no período).
    
    Args:
        ano: Ano de referência
        periodo: Período ('YTD', 'Mês Aberto', etc) - Para histórico, usar 'Mês Aberto'.
        mes: Mês (se aplicável, obrigatório para 'Mês Aberto').
        top5_list: Lista com top 5 contas-chave.
        start_date_main, end_date_main: Datas para período personalizado (ignorado se periodo != 'custom-range').
        dias_sem_show: Dias sem show para considerar churn.
        
    Returns:
        Número de casas KA cujo churn técnico ocorreu no período.
    """
    # Verificação de parâmetros
    if not top5_list:
        logger.debug("[get_churn_ka_for_period] Lista de Key Accounts está vazia")
        return 0
    grupos_ka = [g[0] for g in top5_list]
    
    # Carregar dados da base, aplicando filtros iniciais para economizar memória
    logger.debug("[get_churn_ka_for_period] Carregando dados e aplicando filtros iniciais...")
    df = carregar_base_eshows()
    if df is None or df.empty:
        logger.debug("[get_churn_ka_for_period] Base de dados vazia ou None")
        return 0
    required_cols = ["Data do Show", "Id da Casa", "Grupo"]
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        logger.debug("[get_churn_ka_for_period] Colunas faltando: %s", missing)
        return 0
    df_reduced = df[required_cols].copy()
    df = None; gc.collect()
    df_reduced["Data do Show"] = pd.to_datetime(df_reduced["Data do Show"], errors='coerce')
    df_ka = df_reduced[df_reduced["Grupo"].isin(grupos_ka)].copy()
    del df_reduced; gc.collect()
    if df_ka.empty:
        logger.debug("[get_churn_ka_for_period] Nenhum show encontrado para os grupos KA.")
        return 0

    # Definir intervalo de datas EXATO para o período/mês solicitado
    # Usamos as funções auxiliares get_period_start/end
    periodo_start = get_period_start(ano, periodo, mes, (start_date_main, end_date_main))
    periodo_end = get_period_end(ano, periodo, mes, (start_date_main, end_date_main))

    if periodo_start is None or periodo_end is None:
        logger.debug("[get_churn_ka_for_period] Não foi possível determinar o período de análise.")
        return 0

    # 1. Calcular LastShow GLOBALMENTE para todos os palcos KA
    df_last_show = df_ka.groupby("Id da Casa")["Data do Show"].max().reset_index(name="LastShow")

    # 2. Calcular data_churn_tech
    df_last_show["data_churn_tech"] = df_last_show["LastShow"] + timedelta(days=dias_sem_show)

    # 3. Filtrar palcos cuja data_churn_tech cai DENTRO do período/mês alvo
    churn_candidates_month = df_last_show[
        (df_last_show["data_churn_tech"] >= periodo_start) &
        (df_last_show["data_churn_tech"] <= periodo_end)
    ].copy()

    if churn_candidates_month.empty:
        return 0

    # 4. Verificar se esses candidatos realmente não retornaram APÓS LastShow
    #    (Esta verificação pode ser redundante se LastShow é global, mas garante)
    casas_cand = churn_candidates_month["Id da Casa"].unique()
    df_shows_cand = df_ka[df_ka["Id da Casa"].isin(casas_cand)] # Shows *globais* desses candidatos

    # Merge para comparar Data do Show com LastShow calculado
    df_check = pd.merge(
        churn_candidates_month[["Id da Casa", "LastShow"]],
        df_shows_cand[["Id da Casa", "Data do Show"]],
        on="Id da Casa",
        how="left"
    )

    # Verifica se existe algum show DEPOIS do LastShow calculado
    df_check["Retornou"] = df_check["Data do Show"] > df_check["LastShow"]
    df_status = df_check.groupby("Id da Casa")["Retornou"].any().reset_index()

    # Casas que SÃO candidatas ao churn no mês E que NÃO retornaram
    casas_nao_retornaram = df_status[~df_status["Retornou"]]["Id da Casa"].unique()

    # Contagem final: candidatos do mês que não retornaram
    churn_count_final = churn_candidates_month[churn_candidates_month["Id da Casa"].isin(casas_nao_retornaram)]["Id da Casa"].nunique()

    logger.debug(
        "[get_churn_ka_for_period] Período: %s a %s, Churns ocorridos: %s",
        periodo_start.date(),
        periodo_end.date(),
        churn_count_final,
    )

    del df_ka, df_last_show, churn_candidates_month, df_shows_cand, df_check, df_status
    gc.collect()

    return churn_count_final


def formatar_valor_utils(valor, tipo='numero'):
    """
    Formata valores numéricos (monetário, percentual, etc.) seguindo estas regras:

    - MONETÁRIO:
        * >= 10_000_000 => R$X.XM
        * >= 1_000_000  => R$X.XXM
        * >= 1_000      => R$X.Xk
        * senão => R$X (inteiro, sem casas decimais)
    
    - PERCENTUAL:
        Se abs(valor) < 10 => sempre 2 casas decimais (ex.: 7.55% => '7.55%')
        Se abs(valor) >= 10 => lógica especial para remover zeros:
            Ex. 12.00 => '12%'
            Ex. 12.05 => '12.05%'
            Ex. 12.57 => '12.5%'
    
    - numero_2f => exibe sempre 2 casas decimais, com separador de milhar (vírgula) => '1,234.56'
    - numero => se >=1_000 => exibe com abreviação (k/M); senão, exibe inteiro.
                **Se não for inteiro, mostra 1 casa decimal**.
    
    - Se valor for NaN ou não for numérico, retorna "N/A".
    """
    # Se valor for NaN ou None, retorna "N/A"
    if pd.isna(valor):
        return "N/A"
    if not isinstance(valor, numbers.Number):
        return "N/A"

    # ======= ALTERAÇÃO 1: Normalização do parâmetro "tipo" =======
    tipo = tipo.lower().strip()
    if tipo == "monetary":
        tipo = "monetario"
    elif tipo == "number":
        tipo = "numero"
    elif tipo == "percent":
        tipo = "percentual"
    # ============================================================

    # ===============================
    # 1) Formatação Monetária
    # ===============================
    if tipo == 'monetario':
        if abs(valor) >= 10_000_000:
            return f'R${valor / 1_000_000:.1f}M'
        elif abs(valor) >= 1_000_000:
            return f'R${valor / 1_000_000:.2f}M'
        elif abs(valor) >= 1_000:
            return f'R${valor / 1_000:.1f}k'
        else:
            return f'R${valor:.0f}'

    # ===============================
    # 2) Formatação Percentual
    # ===============================
    elif tipo == 'percentual':
        if abs(valor) < 10:
            return f"{valor:.2f}%"
        else:
            temp_str = f"{valor:.2f}"
            int_part, dec_part = temp_str.split(".")
            if dec_part == "00":
                return f"{int_part}%"
            elif dec_part[0] == '0':
                return f"{int_part}.{dec_part}%"
            else:
                return f"{int_part}.{dec_part[0]}%"

    # ===============================
    # 3) Número com 2 casas decimais e separador de milhar
    # ===============================
    elif tipo == 'numero_2f':
        return f"{valor:,.2f}"

    # ===============================
    # 4) Número (abreviação k/M ou valor simples)
    # ===============================
    elif tipo == 'numero':
        if abs(valor) >= 1_000_000:
            return f'{valor / 1_000_000:.2f}M'
        elif abs(valor) >= 1_000:
            return f'{valor / 1_000:.2f}k'
        else:
            # -------- Ajuste solicitado --------
            # inteiro → sem casas; não inteiro → 1 casa decimal
            return f'{valor:.1f}' if valor % 1 else f'{int(valor)}'

    # ===============================
    # Fallback: Retorna o valor como string
    # ===============================
    return str(valor)


def converter_centavos_para_reais(valor):
    """
    Converte valores de centavos para reais.
    
    Args:
        valor: Valor em centavos (int, float, ou pd.Series)
        
    Returns:
        Valor em reais (dividido por 100)
    """
    if pd.isna(valor):
        return valor
    
    if isinstance(valor, pd.Series):
        return valor / 100
    
    try:
        return float(valor) / 100
    except (TypeError, ValueError):
        return valor


##################################
# Funções de Apoio
##################################
# utils.py  ⇢  único ponto alterado: função parse_valor_formatado

# ------------------------------------------------------------------
# Funções de Apoio – **CORRIGIDA / UNIFICADA**
# ------------------------------------------------------------------
def parse_valor_formatado(valor_str):
    """Converte string formatada (ex: "R$ 1.23k", "50.5%", "N/A") para float.
    Retorna None se a conversão não for possível ou se for 'N/A'.
    """
    if valor_str is None: # Se já for None, retorna None
        return None
    if not isinstance(valor_str, str):
        # Se não for string (e não None), tenta converter direto para float
        # Se falhar, retorna None. Isso cobre casos onde o raw_data já tem números.
        try:
            return float(valor_str)
        except (ValueError, TypeError):
            return None

    s = valor_str.strip() # Mantém case original para replace de "R$"
    
    if s.upper() == 'N/A' or not s: # Checa "N/A" (case-insensitive) ou string vazia
        return None

    # Normaliza a string: remove "R$", espaços. Troca vírgula por ponto para k/M/%.
    # Não removemos o ponto de milhar globalmente ainda, pois pode ser decimal em alguns formatos.
    s_upper = s.upper()
    s_cleaned = s.replace("R$", "")
    
    # Tenta preservar o sinal negativo no início
    is_negative = False
    if s_cleaned.startswith('-'):
        is_negative = True
        s_cleaned = s_cleaned[1:]
    
    s_cleaned = s_cleaned.strip() # Remove espaços após remover R$ e sinal

    # Remove pontos de milhar ANTES de tratar k, M, %
    # Mantém a última vírgula se for decimal, ou a substitui por ponto
    # Heurística: se tem vírgula E ponto, assume ponto é milhar, vírgula é decimal
    # Se só tem vírgula, assume vírgula é decimal
    # Se só tem ponto (e não é k/M), pode ser decimal já
    
    # Lógica de K, M, % (deve vir antes da conversão geral para float)
    val = None
    try:
        if 'K' in s_upper:
            val = float(s_cleaned.upper().replace("K", "").replace(",", ".").strip()) * 1000
        elif 'M' in s_upper:
            val = float(s_cleaned.upper().replace("M", "").replace(",", ".").strip()) * 1000000
        elif '%' in s_upper:
            val = float(s_cleaned.replace("%", "").replace(",", ".").strip()) / 100.0
        else:
            # Tratar números que não são K, M, ou %
            # s_cleaned está sem R$, e o sinal negativo já foi tratado por is_negative
            # Exemplos de s_cleaned: "123", "123.5", "1,234.56", "1.234" (milhar)
            
            if ',' in s_cleaned and '.' in s_cleaned:
                # Formato provável: "1.234,56" (PT-BR com milhar)
                # Remover pontos de milhar, depois trocar vírgula decimal por ponto
                numeric_string = s_cleaned.replace('.', '').replace(',', '.')
            elif ',' in s_cleaned:
                # Formato provável: "123,45" (PT-BR decimal, sem milhar)
                # Trocar vírgula decimal por ponto
                numeric_string = s_cleaned.replace(',', '.')
            elif '.' in s_cleaned:
                # Formato provável: "1234.56" (EUA decimal) OU "1.234" (PT-BR/EUA milhar em inteiro)
                # Se houver múltiplos pontos, e o último segmento após um ponto tiver menos de 3 dígitos,
                # consideramos o último ponto como decimal. Caso contrário, todos os pontos são milhares.
                parts = s_cleaned.split('.')
                if len(parts) > 1 and len(parts[-1]) < 3: # Ex: 123.45 ou 1.2.3 (improvável aqui) ou 1.234.56
                    # Se for "1.234.56", parts[:-1] é ["1","234"], "".join é "1234" -> "1234.56"
                    numeric_string = "".join(parts[:-1]) + "." + parts[-1]
                else: # Ex: "1.234" (milhar) ou "1234" (inteiro) ou "123.456" (decimal longo)
                    numeric_string = s_cleaned.replace('.', '') # Remove pontos de milhar
            else:
                # Formato provável: "1234" (inteiro puro)
                numeric_string = s_cleaned
            
            val = float(numeric_string)
            
    except ValueError:
        # Se K, M, % ou conversão direta falhou, val continua None
        # Isso pode acontecer se a string for algo como "texto"
        # ou se a formatação numérica for inesperada após as substituições.
        pass # val já é None ou continua com o valor da tentativa anterior

    if val is not None and is_negative:
        return -val
    return val # Retorna o valor numérico ou None se todas as tentativas falharem
   
# =================================================================================
# CALCULAR CHURN (carimbando data de churn = LastShow + 45d)
# =================================================================================
def calcular_churn(ano, periodo, mes, start_date=None, end_date=None, uf=None, dias_sem_show=45, custom_range=None):
    """
    Lógica: data_churn = LastShow + dias_sem_show (ex. 45 dias).
    Se a casa não fez show após LastShow, e data_churn cai no período, conta churn.
    
    Args:
        ano (int): Ano de referência
        periodo (str): Período selecionado
        mes (int, optional): Mês específico (caso período seja 'Mês Aberto')
        start_date (datetime, optional): Data inicial
        end_date (datetime, optional): Data final
        uf (str, optional): Estado para filtrar (ex: 'SP')
        dias_sem_show (int): Dias sem show para considerar churn
        custom_range (tuple, optional): (data_inicial, data_final) para período personalizado
    
    Returns:
        int: Quantidade de casas que deram churn no período
    """
    # Ajusta o custom_range ou date_range para usar em get_period_start/end
    date_range = None
    if custom_range is not None:
        date_range = custom_range
    elif start_date is not None and end_date is not None:
        date_range = (start_date, end_date)
    
    start_periodo = get_period_start(ano, periodo, mes, date_range)
    end_periodo = get_period_end(ano, periodo, mes, date_range)

    if df_eshows is None or df_eshows.empty:
        return 0

    df_relevante = df_eshows
    if uf and uf != "BR":
        df_relevante = df_relevante[df_relevante["Estado"] == uf]
    if df_relevante.empty:
        return 0

    df_last = (
        df_relevante
        .groupby("Id da Casa")["Data do Show"]
        .max()
        .reset_index(name="LastShow")
    )

    df_last["data_churn"] = df_last["LastShow"] + timedelta(days=dias_sem_show)

    df_churn_cand = df_last[df_last["data_churn"] <= end_periodo].copy()
    if df_churn_cand.empty:
        return 0

    casas_cand = df_churn_cand["Id da Casa"].unique()
    df_shows_cand = df_relevante[df_relevante["Id da Casa"].isin(casas_cand)]
    df_churn_cand = pd.merge(
        df_churn_cand,
        df_shows_cand[["Id da Casa", "Data do Show"]],
        on="Id da Casa", how="left"
    )

    df_churn_cand["Retornou"] = df_churn_cand["Data do Show"] > df_churn_cand["LastShow"]
    df_status = df_churn_cand.groupby("Id da Casa")["Retornou"].any().reset_index()
    casas_nao_retornaram = df_status[~df_status["Retornou"]]["Id da Casa"].unique()

    df_churn_final = df_last[df_last["Id da Casa"].isin(casas_nao_retornaram)].copy()
    df_churn_final = df_churn_final[
        (df_churn_final["data_churn"] >= start_periodo) &
        (df_churn_final["data_churn"] <= end_periodo)
    ]

    churn_count = df_churn_final["Id da Casa"].nunique()
    return churn_count

def floatify_hist_data(data):
    """
    Converte recursivamente dados para serem serializáveis em JSON:
    - Chaves Timestamp para string ISO format.
    - Valores numpy (float64, int64, etc.) para float/int nativo.
    - Trata dicionários e listas.
    """
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            new_key = k
            if isinstance(k, pd.Timestamp):
                new_key = k.isoformat()  # Converte Timestamp key para string
            elif isinstance(k, (np.floating, np.integer)):
                 new_key = float(k) if isinstance(k, np.floating) else int(k) # Converte numpy key para float/int

            new_dict[new_key] = floatify_hist_data(v) # Processa o valor recursivamente
        return new_dict
    elif isinstance(data, list):
        return [floatify_hist_data(item) for item in data]
    elif isinstance(data, (np.floating, np.integer)):
        # Converte valores numpy para float ou int nativo
        return float(data) if isinstance(data, np.floating) else int(data)
    elif isinstance(data, pd.Timestamp):
         # Converte Timestamps em valores para string ISO
         return data.isoformat()
    # Mantém outros tipos (str, int, float, bool, None) como estão
    return data

# =============================================================================
# FUNÇÃO DE CÁLCULO DE CHURN EXCLUSIVO PARA NOVOS PALCOS
# =============================================================================
def calcular_churn_novos_palcos(
    ano, periodo, mes,
    start_date, end_date,
    df_earliest,
    df_eshows,
    df_new_period,
    dias_sem_show=45,
    uf=None
):
    """
    Calcula a quantidade de novos palcos (df_new_period) que deram churn no período.
    Definição de churn = não retornar 45 dias após último show dentro do período.
    """
    if df_earliest is None or df_earliest.empty:
        return 0
    if df_eshows is None or df_eshows.empty:
        return 0
    if df_new_period is None or df_new_period.empty:
        return 0

    start_periodo = get_period_start(ano, periodo, mes, (start_date, end_date))
    end_periodo   = get_period_end(ano, periodo, mes, (start_date, end_date))

    df_relevante = df_eshows.copy()
    if uf and uf != "BR":
        df_relevante = df_relevante[df_relevante["Estado"] == uf]
    if df_relevante.empty:
        return 0

    df_relevante = df_relevante[df_relevante["Id da Casa"].isin(df_new_period["Id da Casa"])]
    if df_relevante.empty:
        return 0

    df_last = (
        df_relevante
        .groupby("Id da Casa")["Data do Show"]
        .max()
        .reset_index(name="LastShow")
    )
    df_last["data_churn_tech"] = df_last["LastShow"] + timedelta(days=dias_sem_show)
    churn_candidates = df_last[df_last["data_churn_tech"] <= end_periodo].copy()
    if churn_candidates.empty:
        return 0

    casas_cand = churn_candidates["Id da Casa"].unique()
    df_shows_cand = df_relevante[df_relevante["Id da Casa"].isin(casas_cand)]
    df_merged = pd.merge(
        churn_candidates[["Id da Casa", "LastShow"]],
        df_shows_cand[["Id da Casa", "Data do Show"]],
        on="Id da Casa", how="left"
    )
    df_merged["Retornou"] = df_merged["Data do Show"] > df_merged["LastShow"]
    df_status = df_merged.groupby("Id da Casa")["Retornou"].any().reset_index()
    casas_nao_retornaram = df_status[~df_status["Retornou"]]["Id da Casa"].unique()

    # Filtra os candidatos iniciais que não retornaram
    churn_final_candidates = churn_candidates[churn_candidates["Id da Casa"].isin(casas_nao_retornaram)].copy()

    # CORREÇÃO: Filtra pelo período em que a DATA DE CHURN TÉCNICA ocorre, não a LastShow
    churn_final = churn_final_candidates[
        (churn_final_candidates["data_churn_tech"] >= start_periodo) &
        (churn_final_candidates["data_churn_tech"] <= end_periodo)
    ]

    return churn_final["Id da Casa"].nunique()

# =================================================================================
# FUNÇÕES PARA FILTRAR APENAS OS PALCOS QUE SÃO NOVOS
# =================================================================================
def filtrar_novos_palcos_por_periodo(df_earliest, ano, periodo, mes, custom_range):
    """
    Considera apenas casas com EarliestShow >= 2022-04-01 e filtra pela data
    do EarliestShow dentro do período selecionado.
    """
    if df_earliest is None or df_earliest.empty:
        logger.debug(
            "[filtrar_novos_palcos_por_periodo] DataFrame vazio para ano=%s, periodo=%s, mes=%s, custom_range=%s",
            ano,
            periodo,
            mes,
            custom_range,
        )
        return pd.DataFrame()
    linhas_antes = len(df_earliest)
    df_novos = df_earliest[df_earliest["EarliestShow"] >= pd.to_datetime("2022-04-01")]
    if df_novos.empty:
        logger.debug("[filtrar_novos_palcos_por_periodo] Nenhum novo palco após 2022-04-01.")
        return df_novos
    df_temp = df_novos.rename(columns={"EarliestShow": "Data"}).copy()
    df_filt = filtrar_periodo_principal(df_temp, ano, periodo, mes, custom_range)
    df_filt.rename(columns={"Data": "EarliestShow"}, inplace=True)
    logger.debug(
        "[filtrar_novos_palcos_por_periodo] Linhas antes: %s, depois: %s",
        linhas_antes,
        len(df_filt),
    )
    return df_filt

def filtrar_novos_palcos_por_comparacao(df_earliest, ano, periodo, mes, comparar_opcao, custom_range_compare):
    if df_earliest is None or df_earliest.empty:
        logger.debug(
            "[filtrar_novos_palcos_por_comparacao] DataFrame vazio para ano=%s, periodo=%s, mes=%s, comparar_opcao=%s, custom_range_compare=%s",
            ano,
            periodo,
            mes,
            comparar_opcao,
            custom_range_compare,
        )
        return pd.DataFrame()
    linhas_antes = len(df_earliest)
    df_novos = df_earliest[df_earliest["EarliestShow"] >= pd.to_datetime("2022-04-01")]
    if df_novos.empty:
        logger.debug("[filtrar_novos_palcos_por_comparacao] Nenhum novo palco após 2022-04-01.")
        return df_novos
    df_temp = df_novos.rename(columns={"EarliestShow": "Data"}).copy()
    df_filt = filtrar_periodo_comparacao(df_temp, ano, periodo, mes, comparar_opcao, custom_range_compare)
    df_filt.rename(columns={"Data": "EarliestShow"}, inplace=True)
    logger.debug(
        "[filtrar_novos_palcos_por_comparacao] Linhas antes: %s, depois: %s",
        linhas_antes,
        len(df_filt),
    )
    return df_filt

def calcular_variacao_percentual(atual, anterior, *, infinito_com_div_zero=True):
    # Se anterior é None ou NaN, e atual também, variação é 0
    if (anterior is None or pd.isna(anterior)) and \
       (atual is None or pd.isna(atual)):
        return 0.0

    # Se anterior é None/NaN ou 0, mas atual não é
    if anterior is None or pd.isna(anterior) or anterior == 0:
        if atual is None or pd.isna(atual) or atual == 0:
            return 0.0  # Ambos zero ou None
        if infinito_com_div_zero:
            return float('inf') if atual > 0 else float('-inf') if atual < 0 else 0.0
        else: # Se não quer infinito, e anterior é zero mas atual não, retorna 100% ou -100%
              # ou se preferir, pode retornar None ou um valor específico
            return 100.0 if atual > 0 else -100.0 if atual < 0 else 0.0


    # Se atual é None ou NaN, mas anterior não é
    if atual is None or pd.isna(atual):
        # Comportamento pode variar: aqui, consideramos uma queda de 100%
        # se o anterior era positivo, ou um "aumento" de 100% se era negativo
        # ou 0 se anterior era 0 (já tratado acima)
        if anterior > 0:
            return -100.0
        elif anterior < 0:
            return 100.0 # De -X para Nada (0 ou None) é uma "melhora" de 100% da dívida/prejuízo
        else: # anterior == 0, atual == None/NaN
            return 0.0 # Ou float('nan') dependendo da preferência

    # Caso normal: ambos são números e anterior não é zero
    try:
        # Garante que são floats para a divisão
        atual_float = float(atual)
        anterior_float = float(anterior)

        if anterior_float == 0: # Deveria ter sido pego antes, mas como segurança
            if atual_float == 0: return 0.0
            return float('inf') if atual_float > 0 else float('-inf') # Se infinito_com_div_zero=True
            # ou algum outro tratamento se infinito_com_div_zero=False

        # Lógica para quando o valor anterior é negativo
        if anterior_float < 0:
            # Ex: Anterior -100, Atual -50. Variação = ((-50 - (-100)) / |-100|) * 100 = (50 / 100) * 100 = 50% (melhora)
            # Ex: Anterior -100, Atual -150. Variação = ((-150 - (-100)) / |-100|) * 100 = (-50 / 100) * 100 = -50% (piora)
            # Ex: Anterior -100, Atual 50. Variação = ((50 - (-100)) / |-100|) * 100 = (150 / 100) * 100 = 150% (grande melhora)
            return ((atual_float - anterior_float) / abs(anterior_float)) * 100.0

        # Caso padrão (anterior positivo)
        return ((atual_float - anterior_float) / anterior_float) * 100.0

    except (ValueError, TypeError):
         # Em caso de erro de conversão, pode retornar 0, None, ou levantar o erro
        return None # Ou 0.0, ou raise

def formatar_range_legivel(start_date, end_date):
    """
    Formata um par de datas para "DD/MM/YY – DD/MM/YY".
    Retorna string vazia se alguma data for None.
    """
    if start_date and end_date:
        try:
            start_dt_str = pd.to_datetime(start_date).strftime('%d/%m/%y')
            end_dt_str = pd.to_datetime(end_date).strftime('%d/%m/%y')
            return f"{start_dt_str} – {end_dt_str}"
        except Exception:
            return "" # Em caso de erro na conversão
    return ""




