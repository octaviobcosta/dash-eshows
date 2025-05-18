# hist.py
import pandas as pd
import plotly.express as px
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
from .modulobase import (
    carregar_base_eshows,
    carregar_base2 as base2,
    carregar_pessoas,
    carregar_ocorrencias,
    carregar_base_inad,
    carregar_base_inadimplencia,
    carregar_base2
)
from .utils import formatar_valor_utils, calcular_churn, obter_top5_grupos_ano_anterior, get_churn_ka_for_period, filtrar_periodo_principal, get_period_end, filtrar_novos_palcos_por_periodo, filtrar_novos_palcos_por_comparacao, calcular_churn_novos_palcos, faturamento_dos_grupos, novos_palcos_dos_grupos, ensure_grupo_col  # Função para formatação
from datetime import timedelta
import random
import gc
import numpy as np
import calendar

# Colunas de Faturamento padrão
COLUNAS_FATURAMENTO = [
    "Comissão B2B",
    "Comissão B2C",
    "Antecipação de Cachês",
    "Curadoria",
    "SaaS Percentual",
    "SaaS Mensalidade",
    "Notas Fiscais"
]


# --------------------------
# Funções Auxiliares
# --------------------------

def get_date_range_for_period(end_date, months=12):
    """
    Retorna a data de início, considerando que end_date é o fim do período e queremos
    os últimos 'months' meses.
    """
    # Converte em Timestamp; valores inválidos viram NaT
    end_date = pd.to_datetime(end_date, errors='coerce')
    # Se a conversão falhar, usa hoje como fallback
    if pd.isna(end_date):
        end_date = pd.Timestamp.today()

    # Se for array ou série, usa o valor mais recente
    if hasattr(end_date, "ndim") and getattr(end_date, "ndim", 0) > 0:
        end_date = end_date.max()

    end_date = pd.Timestamp(end_date)
    # Retrocede 'months' meses e soma 1 dia para incluir o dia seguinte ao período
    start_date = end_date - relativedelta(months=months) + pd.DateOffset(days=1)
    return start_date, end_date

def moving_average(series, window=3):
    """Calcula a média móvel da série com o período definido."""
    return series.rolling(window=window, min_periods=1).mean()

def growth_rate(series):
    """
    Calcula a taxa de crescimento composta da série.
    Considera o primeiro e o último valor e o número de períodos.
    Retorna a taxa mensal.
    """
    if series.empty or series.iloc[0] == 0:
        return None
    n = len(series)
    return (series.iloc[-1] / series.iloc[0]) ** (1 / n) - 1

def std_deviation(series):
    """Retorna o desvio padrão da série."""
    return series.std()

def prepare_base2_with_date(df_base2: pd.DataFrame) -> pd.DataFrame:
    """
    Se o DataFrame da Base2 não possuir a coluna 'Data' e tiver as colunas 'Ano' e 'Mês',
    cria a coluna 'Data' no primeiro dia do mês.
    """
    df = df_base2.copy()
    if "Data" not in df.columns and "Ano" in df.columns and "Mês" in df.columns:
        df["Data"] = pd.to_datetime(df["Ano"].astype(str) + "-" + df["Mês"].astype(str) + "-01", errors='coerce')
        df = df.dropna(subset=["Data"])
        df = df.sort_values("Data")
    return df

def get_recent_metrics(series, window_quarter=3, window_semester=6, fmt='monetario'):
    """
    Calcula os valores médios dos últimos 'window_quarter' e 'window_semester' períodos
    da série e os formata com formatar_valor_utils.
    """
    if len(series) >= window_quarter:
        last_quarter = series.iloc[-window_quarter:].mean()
        last_quarter_str = formatar_valor_utils(last_quarter, fmt)
    else:
        last_quarter_str = 'N/A'
    if len(series) >= window_semester:
        last_semester = series.iloc[-window_semester:].mean()
        last_semester_str = formatar_valor_utils(last_semester, fmt)
    else:
        last_semester_str = 'N/A'
    return last_quarter_str, last_semester_str


# --------------------------
# Funções Históricas
# --------------------------

def historical_rpc(months: int = 12) -> dict:
    """
    Histórico para Receita por Colaborador (RPC).

    RPC mensal = Faturamento / Funcionários.
    (Neste exemplo, usamos funcionários fixos = 30.)
    """
    # ── 1. Carrega base ────────────────────────────────────────────────
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}

    # ── 2. Prepara coluna de data ─────────────────────────────────────
    df_eshows["Data do Show"] = pd.to_datetime(
        df_eshows["Data do Show"], errors="coerce"
    )
    df_eshows = (
        df_eshows.dropna(subset=["Data do Show"])
        .sort_values("Data do Show")
    )

    # ── 3. Calcula Faturamento por show ───────────────────────────────
    COLS_FAT = [
        "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
        "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    for c in COLS_FAT:
        df_eshows[c] = pd.to_numeric(df_eshows.get(c, 0), errors="coerce").fillna(0)

    df_eshows["Faturamento"] = df_eshows[COLS_FAT].sum(axis=1)

    # ── 4. Agrega mensalmente ─────────────────────────────────────────
    df_monthly = (
        df_eshows
        .groupby(pd.Grouper(key="Data do Show", freq="ME"))
        .agg({"Faturamento": "sum"})
        .reset_index()
    )
    if df_monthly.empty:
        return {}

    # ── 5. Últimos *months* meses ─────────────────────────────────────
    end_date = df_monthly["Data do Show"].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly["Data do Show"] >= start_date]
    if df_period.empty:
        return {}

    # ── 6. Série histórica de RPC ─────────────────────────────────────
    df_period["Funcionarios"] = 30  # valor fixo
    df_period["RPC"] = df_period["Faturamento"] / df_period["Funcionarios"]
    rpc_series = df_period.set_index("Data do Show")["RPC"]

    ma   = moving_average(rpc_series, window=3)
    gr   = growth_rate(rpc_series)
    std  = std_deviation(rpc_series)
    last_q, last_s = get_recent_metrics(rpc_series, fmt="monetario")

    # ── 7. Monta resultado ────────────────────────────────────────────
    resultado = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date":   end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "monetario"),
        "growth_rate":    formatar_valor_utils(
            gr * 100 if gr is not None else 0, "percentual"
        ),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data": {
            d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "monetario")
            for d, v in rpc_series.to_dict().items()
        },
    }

    # ── 8. Libera memória ────────────────────────────────────────────
    del df_eshows, df_monthly, df_period, rpc_series, ma
    gc.collect()

    return resultado

import gc  # (mantenha no topo do hist.py se ainda não estiver)

def historical_cmgr(months: int = 12) -> dict:
    """
    Histórico para Compound Monthly Growth Rate (CMGR) do faturamento.

    CMGR = ((Faturamento_final / Faturamento_inicial) ** (1 / n)) - 1,
    onde *n* é o número de intervalos mensais.
    """
    # ── 1. Carrega base ────────────────────────────────────────────────
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}

    # ── 2. Prepara data e ordena ──────────────────────────────────────
    df_eshows["Data do Show"] = pd.to_datetime(
        df_eshows["Data do Show"], errors="coerce"
    )
    df_eshows = (
        df_eshows.dropna(subset=["Data do Show"])
        .sort_values("Data do Show")
    )

    # ── 3. Faturamento por show ───────────────────────────────────────
    COLS_FAT = [
        "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
        "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    for c in COLS_FAT:
        df_eshows[c] = pd.to_numeric(df_eshows.get(c, 0), errors="coerce").fillna(0)

    df_eshows["Faturamento"] = df_eshows[COLS_FAT].sum(axis=1)

    # ── 4. Agrega por mês ─────────────────────────────────────────────
    df_monthly = (
        df_eshows
        .groupby(pd.Grouper(key="Data do Show", freq="ME"))
        .agg({"Faturamento": "sum"})
        .reset_index()
    )
    if df_monthly.empty:
        return {}

    # ── 5. Corte para últimos *months* ────────────────────────────────
    end_date = df_monthly["Data do Show"].max()
    start_date = end_date - relativedelta(months=months) + pd.DateOffset(days=1)
    df_period = df_monthly[df_monthly["Data do Show"] >= start_date]
    if df_period.empty:
        return {}

    # ── 6. Série de faturamento ───────────────────────────────────────
    fatt_series = df_period.set_index("Data do Show")["Faturamento"]

    # Inclui mês imediatamente anterior, se existir
    primeiro_mes = df_period["Data do Show"].min()
    mes_prev = primeiro_mes - pd.DateOffset(months=1)
    df_prev = df_monthly[df_monthly["Data do Show"] == mes_prev]
    if not df_prev.empty:
        valor_ini = df_prev["Faturamento"].iloc[0]
        fatt_series = pd.concat(
            [pd.Series({mes_prev: valor_ini}), fatt_series]
        ).sort_index()

    # ── 7. Calcula CMGR ───────────────────────────────────────────────
    n = len(fatt_series) - 1
    cmgr = 0.0
    if n > 0 and fatt_series.iloc[0] > 0:
        cmgr = (fatt_series.iloc[-1] / fatt_series.iloc[0]) ** (1 / n) - 1

    # ── 8. Métricas auxiliares ────────────────────────────────────────
    ma   = fatt_series.rolling(window=3, min_periods=1).mean()
    std  = fatt_series.std()
    last_q, last_s = get_recent_metrics(fatt_series, fmt="monetario")

    growth_series = fatt_series.pct_change().dropna()
    growth_series = growth_series[growth_series.index >= start_date]

    resultado = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date":   pd.Timestamp(end_date).strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "monetario"),
        "growth_rate":    formatar_valor_utils(cmgr * 100, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data": {
            d.strftime("%Y-%m-%d"): formatar_valor_utils(v * 100, "percentual")
            for d, v in growth_series.items()
        },
    }

    # ── 9. Libera memória ────────────────────────────────────────────
    del df_eshows, df_monthly, df_period, fatt_series, ma, growth_series
    gc.collect()

    return resultado


# ----------------------------------------------------------------------
# Histórico • Lucratividade
# ----------------------------------------------------------------------
def historical_lucratividade(months: int = 12) -> dict:
    """
    Lucratividade mensal = ((Faturamento – Custos) / Faturamento) * 100
    • Faturamento: colunas de receita na Base Eshows
    • Custos     : coluna "Custos" na Base2
    """
    df_eshows = carregar_base_eshows()
    df_base2  = carregar_base2()
    if df_eshows is None or df_eshows.empty or df_base2 is None or df_base2.empty:
        return {}

    # ── 1. Datas e faturamento ───────────────────────────────────────
    df_eshows["Data do Show"] = pd.to_datetime(
        df_eshows["Data do Show"], errors="coerce"
    )
    df_eshows = (
        df_eshows.dropna(subset=["Data do Show"])
        .sort_values("Data do Show")
    )

    COLS_FAT = [
        "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
        "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    for c in COLS_FAT:
        df_eshows[c] = pd.to_numeric(df_eshows.get(c, 0), errors="coerce").fillna(0)

    df_eshows["Faturamento"] = df_eshows[COLS_FAT].sum(axis=1)

    df_fat_monthly = (
        df_eshows
        .groupby(pd.Grouper(key="Data do Show", freq="ME"))
        .agg({"Faturamento": "sum"})
        .reset_index()
    )

    # ── 2. Custos mensais (Base2) ────────────────────────────────────
    df_base2 = prepare_base2_with_date(df_base2)
    df_base2["Custos"] = pd.to_numeric(df_base2.get("Custos", 0), errors="coerce").fillna(0)

    df_cst_monthly = (
        df_base2
        .groupby(pd.Grouper(key="Data", freq="ME"))
        .agg({"Custos": "sum"})
        .reset_index()
    )

    # ── 3. Merge e cálculo ───────────────────────────────────────────
    df_merged = pd.merge(
        df_fat_monthly, df_cst_monthly,
        left_on="Data do Show", right_on="Data", how="inner"
    ).drop(columns=["Data"]).rename(columns={"Data do Show": "Data"})

    df_merged = df_merged.drop_duplicates("Data")
    if df_merged.empty or "Faturamento" not in df_merged.columns:
        return {}

    df_merged["Lucratividade"] = (
        (df_merged["Faturamento"] - df_merged["Custos"]) / df_merged["Faturamento"]
    ) * 100
    df_merged = df_merged[df_merged["Faturamento"] > 0]
    if df_merged.empty:
        return {}

    # ── 4. Recorta últimos *months* ──────────────────────────────────
    end_date = df_merged["Data"].max()
    start_date = end_date - relativedelta(months=months) + pd.DateOffset(days=1)
    df_period = df_merged[df_merged["Data"] >= start_date]
    if df_period.empty:
        return {}

    serie = pd.Series(
        df_period["Lucratividade"].values,
        index=df_period["Data"]
    ).sort_index()

    ma   = serie.rolling(window=3, min_periods=1).mean()
    gr   = growth_rate(serie)
    std  = serie.std()
    last_q, last_s = get_recent_metrics(serie, fmt="percentual")

    resultado = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date":   end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "percentual"),
        "growth_rate":    formatar_valor_utils(
            gr * 100 if gr is not None else 0, "percentual"
        ),
        "std_deviation":  formatar_valor_utils(std, "percentual"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data": {
            d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "percentual")
            for d, v in serie.items()
        },
    }

    # ── 5. Libera memória ────────────────────────────────────────────
    del (
        df_eshows, df_base2, df_fat_monthly, df_cst_monthly,
        df_merged, df_period, serie, ma
    )
    gc.collect()

    return resultado


# ----------------------------------------------------------------------
# Histórico • EBITDA
# ----------------------------------------------------------------------
def historical_ebitda(months: int = 12) -> dict:
    """
    EBITDA mensal (%) = ((ReceitaEBTIDA – CustosEBTIDA) / ReceitaEBTIDA) * 100
      • ReceitaEBTIDA = Faturamento – Notas Fiscais
      • CustosEBTIDA  = Custos – Imposto  (ambos em Base2)
    """
    df_eshows = carregar_base_eshows()
    df_base2  = carregar_base2()
    if df_eshows is None or df_eshows.empty or df_base2 is None or df_base2.empty:
        return {}

    # ── 1. Datas e receita EBTIDA ─────────────────────────────────────
    df_eshows["Data do Show"] = pd.to_datetime(
        df_eshows["Data do Show"], errors="coerce"
    )
    df_eshows = (
        df_eshows.dropna(subset=["Data do Show"])
        .sort_values("Data do Show")
    )

    COLS_FAT = [
        "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
        "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    for c in COLS_FAT:
        df_eshows[c] = pd.to_numeric(df_eshows.get(c, 0), errors="coerce").fillna(0)

    df_eshows["Faturamento"]    = df_eshows[COLS_FAT].sum(axis=1)
    df_eshows["ReceitaEBTIDA"]  = (
        df_eshows["Faturamento"] - df_eshows.get("Notas Fiscais", 0)
    )

    df_fat_monthly = (
        df_eshows
        .groupby(pd.Grouper(key="Data do Show", freq="ME"))
        .agg({"ReceitaEBTIDA": "sum"})
        .reset_index()
    )

    # ── 2. CustosEBTIDA ──────────────────────────────────────────────
    df_base2 = prepare_base2_with_date(df_base2)
    df_base2["Custos"]  = pd.to_numeric(df_base2.get("Custos", 0), errors="coerce").fillna(0)
    df_base2["Imposto"] = pd.to_numeric(df_base2.get("Imposto", 0), errors="coerce").fillna(0)
    df_base2["CustosEBTIDA"] = df_base2["Custos"] - df_base2["Imposto"]

    df_cst_monthly = (
        df_base2
        .groupby(pd.Grouper(key="Data", freq="ME"))
        .agg({"CustosEBTIDA": "sum"})
        .reset_index()
    )

    # ── 3. Merge e cálculo ───────────────────────────────────────────
    df_merged = pd.merge(
        df_fat_monthly, df_cst_monthly,
        left_on="Data do Show", right_on="Data", how="inner"
    ).drop(columns=["Data"]).rename(columns={"Data do Show": "Data"})

    df_merged = df_merged.drop_duplicates("Data")
    if df_merged.empty or "ReceitaEBTIDA" not in df_merged.columns:
        return {}

    df_merged["EBITDA"] = (
        (df_merged["ReceitaEBTIDA"] - df_merged["CustosEBTIDA"])
        / df_merged["ReceitaEBTIDA"]
    ) * 100
    df_merged = df_merged[df_merged["ReceitaEBTIDA"] > 0]
    if df_merged.empty:
        return {}

    # ── 4. Recorta últimos *months* ──────────────────────────────────
    end_date = df_merged["Data"].max()
    start_date = end_date - relativedelta(months=months) + pd.DateOffset(days=1)
    df_period = df_merged[df_merged["Data"] >= start_date]
    if df_period.empty:
        return {}

    serie = pd.Series(
        df_period["EBITDA"].values,
        index=df_period["Data"]
    ).sort_index()

    ma   = serie.rolling(window=3, min_periods=1).mean()
    gr   = growth_rate(serie)
    std  = serie.std()
    last_q, last_s = get_recent_metrics(serie, fmt="percentual")

    resultado = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date":   end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "percentual"),
        "growth_rate":    formatar_valor_utils(
            gr * 100 if gr is not None else 0, "percentual"
        ),
        "std_deviation":  formatar_valor_utils(std, "percentual"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data": {
            d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "percentual")
            for d, v in serie.items()
        },
    }

    # ── 5. Libera memória ────────────────────────────────────────────
    del (
        df_eshows, df_base2, df_fat_monthly, df_cst_monthly,
        df_merged, df_period, serie, ma
    )
    gc.collect()

    return resultado


def historical_metric(df: pd.DataFrame, date_col: str, value_col: str, months=12, window=3):
    """
    Função genérica para calcular métricas históricas a partir de um DataFrame.
    Se a coluna value_col não existir e value_col for 'Faturamento', ela é calculada a partir de COLUNAS_FATURAMENTO.
    Retorna um dicionário com médias móveis, growth_rate, desvio padrão e últimos trimestre/semestre formatados.
    """
    df = df.copy()
    if df.empty or date_col not in df.columns:
        return {}
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    # Calcula 'Faturamento' se necessário
    if value_col not in df.columns and value_col == 'Faturamento':
        COLUNAS_FATURAMENTO = ["Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
                               "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"]
        for col in COLUNAS_FATURAMENTO:
            if col not in df.columns:
                df[col] = 0
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df[value_col] = df[COLUNAS_FATURAMENTO].sum(axis=1)
    if value_col not in df.columns:
        return {}
    df_monthly = df.groupby(pd.Grouper(key=date_col, freq='ME')).agg({value_col: 'sum'}).reset_index()
    end_date = pd.to_datetime(df_monthly[date_col].max(), errors='coerce')
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly[date_col] >= start_date]
    if df_period.empty:
        return {}
    series = df_period.set_index(date_col)[value_col]
    ma = moving_average(series, window=window)
    gr = growth_rate(series)
    std = std_deviation(series)
    last_q, last_s = get_recent_metrics(series, fmt='monetario')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'monetario'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'monetario'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'monetario')
                     for d, v in series.to_dict().items()}
    }

def historical_roll6m(months=12):
    """
    Histórico para Roll 6M Growth.
    Calcula o Roll 6M Growth a partir da Base Eshows.

    Para cada mês (a partir do 6º dado), o Roll 6M Growth é calculado como:
      roll6m = (Faturamento_atual / Faturamento_6meses_atrás)^(1/5) - 1
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show']).sort_values('Data do Show')
    # Garante colunas de faturamento necessárias
    COLUNAS_FATURAMENTO = ["Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
                           "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"]
    for col in COLUNAS_FATURAMENTO:
        if col not in df_eshows.columns:
            df_eshows[col] = 0
        else:
            df_eshows[col] = pd.to_numeric(df_eshows[col], errors='coerce').fillna(0)
    df_eshows['Faturamento'] = df_eshows[COLUNAS_FATURAMENTO].sum(axis=1)
    df_monthly = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Faturamento': 'sum'}).reset_index()
    if df_monthly.empty or len(df_monthly) < 6:
        return {}
    faturamento_series = df_monthly.set_index('Data do Show')['Faturamento']
    # Calcula roll6m para cada ponto a partir do 6º mês
    roll6m_values = {}
    dates = faturamento_series.index
    for i in range(5, len(faturamento_series)):
        current_val = faturamento_series.iloc[i]
        past_val = faturamento_series.iloc[i - 5]
        if past_val > 0:
            growth = (current_val / past_val) ** (1/5) - 1
            roll6m_values[dates[i]] = growth
    if not roll6m_values:
        return {}
    roll6m_series = pd.Series(roll6m_values).sort_index()
    ma = moving_average(roll6m_series, window=3)
    gr = growth_rate(roll6m_series)
    std = std_deviation(roll6m_series)
    last_q, last_s = get_recent_metrics(roll6m_series, fmt='percentual')
    start_date = roll6m_series.index.min()
    end_date = roll6m_series.index.max()
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1] * 100, 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std * 100, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v * 100, 'percentual')
                     for d, v in roll6m_series.to_dict().items()}
    }

def historical_estabilidade(months=12):
    """
    Histórico para Estabilidade.
    A Estabilidade mensal é calculada a partir da Base2 usando as métricas:
      - Uptime (%)
      - MTBF (horas)
      - MTTR (Min)
      - Taxa de Erros (%)
    As métricas são normalizadas e combinadas com pesos fixos.
    """
    df_base2 = carregar_base2()
    if df_base2 is None or df_base2.empty:
        return {}
    df_base2 = prepare_base2_with_date(df_base2)
    for col in ['Uptime (%)', 'MTBF (horas)', 'MTTR (Min)', 'Taxa de Erros (%)']:
        if col not in df_base2.columns:
            df_base2[col] = 0
        else:
            df_base2[col] = pd.to_numeric(df_base2[col], errors='coerce').fillna(0)
    df_monthly = df_base2.groupby(pd.Grouper(key='Data', freq='ME')).agg({
        'Uptime (%)': 'mean',
        'MTBF (horas)': 'mean',
        'MTTR (Min)': 'mean',
        'Taxa de Erros (%)': 'mean'
    }).reset_index()
    if df_monthly.empty:
        return {}
    # Parâmetros para normalização
    MTBF_MAX = 200.0
    MTTR_MAX = 60.0
    ERROS_MAX = 50.0
    PESO_UPTIME = 0.4
    PESO_MTBF = 0.2
    PESO_MTTR = 0.2
    PESO_ERROS = 0.2
    # Calcula índice de estabilidade para cada mês
    def calc_estabilidade(row):
        uptime_norm = row['Uptime (%)']
        mtbf_norm = min((row['MTBF (horas)'] / MTBF_MAX) * 100, 100)
        mttr_norm = max(min(((MTTR_MAX - row['MTTR (Min)']) / MTTR_MAX) * 100, 100), 0)
        erros_norm = max(min(((ERROS_MAX - row['Taxa de Erros (%)']) / ERROS_MAX) * 100, 100), 0)
        return uptime_norm * PESO_UPTIME + mtbf_norm * PESO_MTBF + mttr_norm * PESO_MTTR + erros_norm * PESO_ERROS
    df_monthly['Estabilidade'] = df_monthly.apply(calc_estabilidade, axis=1)
    # Filtra últimos 'months' meses
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    estabilidade_series = df_period.set_index('Data')['Estabilidade']
    ma = moving_average(estabilidade_series, window=3)
    gr = growth_rate(estabilidade_series)
    std = std_deviation(estabilidade_series)
    last_q, last_s = get_recent_metrics(estabilidade_series, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in estabilidade_series.to_dict().items()}
    }

def historical_nrr(months=12):
    """
    Histórico para Net Revenue Retention (NRR).
    Calcula, para cada mês que possui dado no mesmo mês do ano anterior:
      NRR = ((Faturamento_mês_atual - Faturamento_ano_anterior) / Faturamento_ano_anterior) * 100
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show']).sort_values('Data do Show')
    # Calcula faturamento mensal total
    COLUNAS_FATURAMENTO = ["Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
                           "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"]
    for col in COLUNAS_FATURAMENTO:
        if col not in df_eshows.columns:
            df_eshows[col] = 0
        else:
            df_eshows[col] = pd.to_numeric(df_eshows[col], errors='coerce').fillna(0)
    df_eshows['Faturamento'] = df_eshows[COLUNAS_FATURAMENTO].sum(axis=1)
    df_monthly = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Faturamento': 'sum'}).reset_index()
    if df_monthly.empty:
        return {}
    # Calcula NRR para cada mês com dado no ano anterior
    nrr_values = {}
    for idx, row in df_monthly.iterrows():
        ano = row['Data do Show'].year
        mes = row['Data do Show'].month
        valor_atual = row['Faturamento']
        prev = df_monthly[(df_monthly['Data do Show'].dt.year == ano - 1) & (df_monthly['Data do Show'].dt.month == mes)]
        if not prev.empty:
            valor_prev = prev['Faturamento'].iloc[0]
            if valor_prev > 0:
                nrr = ((valor_atual - valor_prev) / valor_prev) * 100
                nrr_values[row['Data do Show']] = nrr
    if not nrr_values:
        return {}
    nrr_series = pd.Series(nrr_values).sort_index()
    # Filtra últimos 'months' meses
    end_date = nrr_series.index.max()
    start_date, _ = get_date_range_for_period(end_date, months)
    nrr_series = nrr_series[nrr_series.index >= start_date]
    if nrr_series.empty:
        return {}
    ma = moving_average(nrr_series, window=3)
    gr = growth_rate(nrr_series)
    std = std_deviation(nrr_series)
    last_q, last_s = get_recent_metrics(nrr_series, fmt='percentual')
    return {
        "start_date": nrr_series.index.min().strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in nrr_series.to_dict().items()}
    }

def historical_perdas_operacionais(months=12) -> dict:
    """
    Histórico das Perdas Operacionais (%).
    Calcula: Perdas (%) = (Custos "Op. Shows" / GMV) * 100.
    """
    # Base Eshows (GMV)
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    # Base2 (Op. Shows)
    df_b2 = carregar_base2()
    if df_b2 is None or df_b2.empty:
        return {}
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show']).sort_values('Data do Show')
    # Garante coluna Valor Total do Show
    if "Valor Total do Show" not in df_eshows.columns:
        for alt in ["ValorTotaldoShow", "Valor_Total_do_Show"]:
            if alt in df_eshows.columns:
                df_eshows.rename(columns={alt: "Valor Total do Show"}, inplace=True)
                break
        if "Valor Total do Show" not in df_eshows.columns:
            df_eshows["Valor Total do Show"] = 0
    df_eshows["Valor Total do Show"] = pd.to_numeric(df_eshows["Valor Total do Show"], errors="coerce").fillna(0)
    # GMV mensal
    gmv_month = df_eshows.groupby(pd.Grouper(key="Data do Show", freq="M"))["Valor Total do Show"].sum()
    # Base2 Op. Shows
    df_b2 = prepare_base2_with_date(df_b2)
    if "Op. Shows" not in df_b2.columns:
        for alt in ["Op Shows", "Op_Shows", "OpShows"]:
            if alt in df_b2.columns:
                df_b2.rename(columns={alt: "Op. Shows"}, inplace=True)
                break
        if "Op. Shows" not in df_b2.columns:
            df_b2["Op. Shows"] = 0
    df_b2["Op. Shows"] = pd.to_numeric(df_b2["Op. Shows"], errors="coerce").fillna(0)
    op_month = df_b2.groupby(pd.Grouper(key="Data", freq="M"))["Op. Shows"].sum()
    # Mescla GMV e Op. Shows mensais
    df_merge = pd.merge(gmv_month.rename("GMV"), op_month.rename("Op. Shows"),
                        left_index=True, right_index=True, how="inner")
    if df_merge.empty:
        return {}
    df_merge["Perdas (%)"] = df_merge.apply(lambda r: (r["Op. Shows"] / r["GMV"] * 100) if r["GMV"] > 0 else 0, axis=1)
    # Considera últimos 'months' períodos
    perdas_series = df_merge["Perdas (%)"].tail(months)
    if perdas_series.empty:
        return {}
    ma = moving_average(perdas_series, 3)
    gr = growth_rate(perdas_series)
    std = std_deviation(perdas_series)
    last_q, last_s = get_recent_metrics(perdas_series, fmt="percentual")
    return {
        "start_date": perdas_series.index.min().strftime("%Y-%m-%d"),
        "end_date": perdas_series.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "percentual"),
        "growth_rate": formatar_valor_utils((gr or 0) * 100, "percentual"),
        "std_deviation": formatar_valor_utils(std, "percentual"),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "percentual")
                     for d, v in perdas_series.to_dict().items()}
    }

def historical_churn(months=12, dias_sem_show=45):
    """
    Histórico para Churn.
    Para cada mês no intervalo dos últimos 'months' meses, calcula a taxa de churn:
      churn_rate = (casas que não retornaram / estabelecimentos ativos) * 100.
    """
    df = carregar_base_eshows()
    if df is None or df.empty:
        return {}
    df['Data do Show'] = pd.to_datetime(df['Data do Show'], errors='coerce')
    df = df.dropna(subset=['Data do Show']).sort_values('Data do Show')
    end_date = df['Data do Show'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    dates = pd.date_range(start=start_date, end=end_date, freq='ME')
    churn_series = {}
    global df_eshows  # disponibiliza df para uso em calcular_churn
    df_eshows = df.copy()
    for d in dates:
        period_start, period_end = get_date_range_for_period(d, months)
        churn_count = calcular_churn(
            ano=period_end.year, periodo="Custom", mes=period_end.month,
            start_date=period_start, end_date=period_end, dias_sem_show=dias_sem_show
        )
        ativos = df[df['Data do Show'] <= d]['Id da Casa'].nunique()
        churn_rate_val = (churn_count / ativos * 100) if ativos > 0 else 0
        churn_series[d] = churn_rate_val
    churn_series_pd = pd.Series(churn_series).sort_index()
    if churn_series_pd.empty:
        return {}
    ma = moving_average(churn_series_pd, window=3)
    gr = growth_rate(churn_series_pd)
    std = std_deviation(churn_series_pd)
    last_q, last_s = get_recent_metrics(churn_series_pd, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in churn_series_pd.to_dict().items()}
    }

def historical_inadimplencia(months=12):
    """
    Histórico para Inadimplência.
    Taxa = (Valor Inadimplente / GMV) * 100, considerando boletos vencidos ou em dunning até o cutoff do mês.
    """
    # 1. Base Eshows (GMV)
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show']).sort_values('Data do Show')
    df_eshows["Valor Total do Show"] = pd.to_numeric(df_eshows["Valor Total do Show"], errors='coerce').fillna(0)
    df_gmv = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Valor Total do Show': 'sum'}).reset_index()
    # 2. Base de Inadimplência (Casas)
    df_casas, _ = carregar_base_inad()
    if df_casas is None or df_casas.empty:
        return {}
    df_casas = df_casas.copy()
    for col in ["AnoVenc", "MesVenc", "DiaVenc"]:
        df_casas[col] = pd.to_numeric(df_casas[col], errors="coerce").fillna(0)
    df_casas.loc[df_casas["DiaVenc"] <= 0, "DiaVenc"] = 1
    df_casas["DataVenc"] = pd.to_datetime(
        df_casas["AnoVenc"].astype(int).astype(str) + "-" +
        df_casas["MesVenc"].astype(int).astype(str) + "-" +
        df_casas["DiaVenc"].astype(int).astype(str),
        errors='coerce'
    )
    df_casas["Valor Real"] = pd.to_numeric(df_casas["Valor Real"], errors="coerce").fillna(0)
    # 3. Janela de análise
    end_date = df_eshows['Data do Show'].max()
    start_date = end_date - relativedelta(months=months) + pd.DateOffset(days=1)
    # 4. Períodos mensais (início do mês)
    period_starts = pd.date_range(start=start_date, end=end_date, freq='MS')
    inad_series = {}
    status_inad = ["Vencido", "DUNNING_REQUESTED"]
    for period_start in period_starts:
        dt_min = period_start
        dt_max = (period_start + pd.offsets.MonthEnd(0))
        cutoff = dt_max - timedelta(days=22)
        df_casas_month = df_casas[(df_casas["DataVenc"] >= dt_min) & (df_casas["DataVenc"] <= dt_max) & (df_casas["DataVenc"] <= cutoff)]
        df_inad = df_casas_month[df_casas_month["Status"].isin(status_inad)]
        valor_inad = df_inad["Valor Real"].sum()
        # GMV do mês (compara datas normalizadas)
        gmv_val = df_gmv[df_gmv['Data do Show'].dt.normalize() == dt_max.normalize()]["Valor Total do Show"].sum()
        rate = (valor_inad / gmv_val * 100) if gmv_val > 0 else 0
        inad_series[dt_max.normalize()] = rate
    inad_series_pd = pd.Series(inad_series).sort_index()
    if inad_series_pd.empty:
        return {}
    ma = moving_average(inad_series_pd, window=3)
    gr = growth_rate(inad_series_pd)
    std = std_deviation(inad_series_pd)
    last_q, last_s = get_recent_metrics(inad_series_pd, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in inad_series_pd.to_dict().items()}
    }

def historical_turnover(months: int = 12) -> dict:
    """
    Série mensal de Turn Over para os últimos *months* meses.
    (desligamentos / quadro-ativo na véspera) × 100
    """
    df_p = carregar_pessoas()
    if df_p is None or df_p.empty:
        return {}

    df_p["DataInicio"] = pd.to_datetime(df_p.get("DataInicio"), errors="coerce")
    df_p["DataFinal"]  = pd.to_datetime(df_p.get("DataFinal"),  errors="coerce")

    end_date   = pd.Timestamp.today().normalize()
    start_date = (end_date - relativedelta(months=months)).replace(day=1)
    dates = pd.date_range(start=start_date, end=end_date, freq="MS")

    series = {}
    for first_day in dates:
        last_day = first_day + relativedelta(months=1) - pd.DateOffset(days=1)

        cond_inic = (
            (df_p["DataInicio"] < first_day)
            & (df_p["DataFinal"].isna() | (df_p["DataFinal"] >= first_day))
        )
        n_inic = int(cond_inic.sum())

        cond_desl = (
            (~df_p["DataFinal"].isna())
            & (df_p["DataFinal"] >= first_day)
            & (df_p["DataFinal"] <= last_day)
        )
        n_desl = int(cond_desl.sum())

        series[first_day] = 0 if n_inic == 0 else n_desl / n_inic * 100

    serie = pd.Series(series).sort_index()
    if serie.empty:
        return {}

    ma   = moving_average(serie, 3)
    gr   = growth_rate(serie)
    std  = std_deviation(serie)
    lq, ls = get_recent_metrics(serie)

    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date":   end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "percentual"),
        "growth_rate":    formatar_valor_utils(gr * 100 if gr else 0, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "percentual"),
        "last_quarter":   lq,
        "last_semester":  ls,
        "raw_data": {
            d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "percentual")
            for d, v in serie.to_dict().items()
        },
    }

def historical_perfis_completos(months=12):
    """
    Histórico para Perfis Completos.
    Calcula mensalmente a porcentagem de perfis completos:
      Perfis Completos (%) = (Base Acumulada Completa / Base Acumulada Total) * 100.
    """
    df_base2 = carregar_base2()
    if df_base2 is None or df_base2.empty:
        return {}
    df_base2 = prepare_base2_with_date(df_base2)
    for col in ["Base Acumulada Completa", "Base Acumulada Total"]:
        if col not in df_base2.columns:
            df_base2[col] = 0
        else:
            df_base2[col] = pd.to_numeric(df_base2[col], errors='coerce').fillna(0)
    df_monthly = df_base2.groupby(pd.Grouper(key='Data', freq='ME')).agg({
        "Base Acumulada Completa": "sum",
        "Base Acumulada Total": "sum"
    }).reset_index()
    df_monthly["Perfis Completos (%)"] = df_monthly.apply(
        lambda row: (row["Base Acumulada Completa"] / row["Base Acumulada Total"] * 100)
        if row["Base Acumulada Total"] > 0 else 0,
        axis=1
    )
    if df_monthly.empty:
        return {}
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    perfis_series = df_period.set_index('Data')["Perfis Completos (%)"]
    ma = moving_average(perfis_series, window=3)
    gr = growth_rate(perfis_series)
    std = std_deviation(perfis_series)
    last_q, last_s = get_recent_metrics(perfis_series, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in perfis_series.to_dict().items()}
    }

def historical_autonomia_usuario(months=12):
    """
    Histórico para Autonomia do Usuário.
    Calcula mensalmente: Autonomia (%) = (Propostas Lançadas Usuários / (Usuários + Internas)) * 100.
    """
    df_base2 = carregar_base2()
    if df_base2 is None or df_base2.empty:
        return {}
    df_base2 = prepare_base2_with_date(df_base2)
    for col in ["Propostas Lancadas Usuários", "Propostas Lancadas Internas"]:
        if col not in df_base2.columns:
            df_base2[col] = 0
        else:
            df_base2[col] = pd.to_numeric(df_base2[col], errors='coerce').fillna(0)
    df_monthly = df_base2.groupby(pd.Grouper(key='Data', freq='ME')).agg({
        "Propostas Lancadas Usuários": "sum",
        "Propostas Lancadas Internas": "sum"
    }).reset_index()
    df_monthly["Autonomia (%)"] = df_monthly.apply(
        lambda row: (row["Propostas Lancadas Usuários"] / (row["Propostas Lancadas Usuários"] + row["Propostas Lancadas Internas"]) * 100)
        if (row["Propostas Lancadas Usuários"] + row["Propostas Lancadas Internas"]) > 0 else 0,
        axis=1
    )
    if df_monthly.empty:
        return {}
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    autonomia_series = df_period.set_index('Data')["Autonomia (%)"]
    ma = moving_average(autonomia_series, window=3)
    gr = growth_rate(autonomia_series)
    std = std_deviation(autonomia_series)
    last_q, last_s = get_recent_metrics(autonomia_series, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in autonomia_series.to_dict().items()}
    }

def historical_sucesso_implantacao(months=12):
    """
    Histórico para Sucesso da Implantação.
    Gera valores aleatórios entre 10% e 95% para cada mês no período.
    Todos os valores formatados em 'percentual'.
    """
    end_date = pd.Timestamp.today().normalize()
    start_date = end_date - relativedelta(months=months) + pd.DateOffset(days=1)
    dates = pd.date_range(start=start_date, end=end_date, freq='ME')
    sucesso_values = {d: random.uniform(0.10, 0.95) for d in dates}
    sucesso_series = pd.Series(sucesso_values).sort_index()
    if sucesso_series.empty:
        return {}
    ma = moving_average(sucesso_series, window=3)
    gr = growth_rate(sucesso_series)
    std = std_deviation(sucesso_series)
    last_q, last_s = get_recent_metrics(sucesso_series, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1] * 100, 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std * 100, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v * 100, 'percentual')
                     for d, v in sucesso_series.to_dict().items()}
    }

def historical_conformidade_juridica(months=12):
    """
    Histórico para Conformidade Jurídica.
    Calcula: Conformidade (%) = (Casas Contrato / Casas Ativas) * 100.
    """
    df_base2 = carregar_base2()
    if df_base2 is None or df_base2.empty:
        return {}
    df_base2 = prepare_base2_with_date(df_base2)
    for col in ["Casas Contrato", "Casas Ativas"]:
        if col not in df_base2.columns:
            df_base2[col] = 0
        else:
            df_base2[col] = pd.to_numeric(df_base2[col], errors='coerce').fillna(0)
    df_monthly = df_base2.groupby(pd.Grouper(key='Data', freq='ME')).agg({
        "Casas Contrato": "sum",
        "Casas Ativas": "sum"
    }).reset_index()
    if df_monthly.empty:
        return {}
    df_monthly["Conformidade (%)"] = df_monthly.apply(
        lambda row: (row["Casas Contrato"] / row["Casas Ativas"] * 100) if row["Casas Ativas"] > 0 else 0,
        axis=1
    )
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    conformidade_series = df_period.set_index('Data')["Conformidade (%)"]
    ma = moving_average(conformidade_series, window=3)
    gr = growth_rate(conformidade_series)
    std = std_deviation(conformidade_series)
    last_q, last_s = get_recent_metrics(conformidade_series, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in conformidade_series.to_dict().items()}
    }

def historical_eficiencia_atendimento(months=12):
    """
    Histórico para Eficiência de Atendimento.
    Calcula um score (%) de eficiência a partir dos tempos médios de resposta e resolução:
    score = média(100 - (Tempo Resposta / LIM_RESPOSTA * 100), 100 - (Tempo Resolução / LIM_RESOLUCAO * 100)).
    """
    df_base2 = carregar_base2()
    if df_base2 is None or df_base2.empty:
        return {}
    df_base2 = prepare_base2_with_date(df_base2)
    for col in ["Tempo Resposta", "Tempo Resolução"]:
        if col not in df_base2.columns:
            df_base2[col] = 0
        else:
            df_base2[col] = pd.to_numeric(df_base2[col], errors='coerce').fillna(0)
    df_monthly = df_base2.groupby(pd.Grouper(key='Data', freq='ME')).agg({
        "Tempo Resposta": "mean",
        "Tempo Resolução": "mean"
    }).reset_index()
    if df_monthly.empty:
        return {}
    LIM_RESPOSTA = 30.0
    LIM_RESOLUCAO = 120.0
    def calc_score(row):
        score_resp = 100.0 - (row["Tempo Resposta"] / LIM_RESPOSTA * 100.0)
        score_resp = min(max(score_resp, 0), 100)
        score_resol = 100.0 - (row["Tempo Resolução"] / LIM_RESOLUCAO * 100.0)
        score_resol = min(max(score_resol, 0), 100)
        return (score_resp + score_resol) / 2.0
    df_monthly["Eficiência"] = df_monthly.apply(calc_score, axis=1)
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    eficiencia_series = df_period.set_index('Data')["Eficiência"]
    ma = moving_average(eficiencia_series, window=3)
    gr = growth_rate(eficiencia_series)
    std = std_deviation(eficiencia_series)
    last_q, last_s = get_recent_metrics(eficiencia_series, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in eficiencia_series.to_dict().items()}
    }

def historical_nivel_servico(months=12):
    """
    Histórico para Nível de Serviço.
    Calcula: Nível de Serviço (%) = (1 - (Ocorrências / Shows)) * 100.
    Usa Base Eshows (Shows mensais) e Ocorrências (Ocorrências mensais, excluindo leves).
    """
    df_eshows = carregar_base_eshows()
    df_ocorr = carregar_ocorrencias()
    if df_eshows is None or df_eshows.empty or df_ocorr is None or df_ocorr.empty:
        return {}
    # Preparação dos dados de shows mensais
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show']).sort_values('Data do Show')
    df_shows = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Id do Show': 'nunique'}).reset_index()
    df_shows.rename(columns={'Id do Show': 'Shows'}, inplace=True)
    # Preparação dos dados de ocorrências mensais
    if "DATA" in df_ocorr.columns:
        df_ocorr = df_ocorr.rename(columns={"DATA": "Data"})
    df_ocorr['Data'] = pd.to_datetime(df_ocorr['Data'], errors='coerce')
    df_ocorr = df_ocorr.dropna(subset=['Data']).sort_values('Data')
    if "TIPO" in df_ocorr.columns:
        df_ocorr = df_ocorr[df_ocorr["TIPO"] != "Leve"]
    if "ID_OCORRENCIA" in df_ocorr.columns:
        df_occ = df_ocorr.groupby(pd.Grouper(key='Data', freq='ME')).agg({'ID_OCORRENCIA': 'nunique'}).reset_index()
        df_occ.rename(columns={"ID_OCORRENCIA": "Ocorrências"}, inplace=True)
    else:
        df_occ = df_ocorr.groupby(pd.Grouper(key='Data', freq='ME')).size().reset_index(name="Ocorrências")
    # Mescla ocorrências e shows por mês
    df_merged = pd.merge(df_shows, df_occ, left_on='Data do Show', right_on='Data', how='inner')
    df_merged.drop(columns=['Data'], inplace=True)
    df_merged.rename(columns={'Data do Show': 'Data'}, inplace=True)
    if df_merged.empty:
        return {}
    df_merged["Nível de Serviço (%)"] = df_merged.apply(
        lambda row: (1 - (row["Ocorrências"] / row["Shows"])) * 100 if row["Shows"] > 0 else 0,
        axis=1
    )
    nivel_series = df_merged.set_index('Data')["Nível de Serviço (%)"]
    # Filtra últimos 'months' meses
    end_date = nivel_series.index.max()
    start_date, _ = get_date_range_for_period(end_date, months)
    nivel_series = nivel_series[nivel_series.index >= start_date]
    if nivel_series.empty:
        return {}
    ma = moving_average(nivel_series, window=3)
    gr = growth_rate(nivel_series)
    std = std_deviation(nivel_series)
    last_q, last_s = get_recent_metrics(nivel_series, fmt='percentual')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in nivel_series.to_dict().items()}
    }

def historical_take_rate(months: int = 12) -> dict:
    """
    Série mensal de Turn Over para os últimos *months* meses.
    (desligamentos / quadro-ativo na véspera) × 100
    """
    df_p = carregar_pessoas()
    if df_p is None or df_p.empty:
        return {}

    df_p["DataInicio"] = pd.to_datetime(df_p.get("DataInicio"), errors="coerce")
    df_p["DataFinal"]  = pd.to_datetime(df_p.get("DataFinal"),  errors="coerce")

    end_date   = pd.Timestamp.today().normalize()
    start_date = (end_date - relativedelta(months=months)).replace(day=1)
    dates = pd.date_range(start=start_date, end=end_date, freq="MS")

    series = {}
    for first_day in dates:
        last_day = first_day + relativedelta(months=1) - pd.DateOffset(days=1)

        cond_inic = (
            (df_p["DataInicio"] < first_day)
            & (df_p["DataFinal"].isna() | (df_p["DataFinal"] >= first_day))
        )
        n_inic = int(cond_inic.sum())

        cond_desl = (
            (~df_p["DataFinal"].isna())
            & (df_p["DataFinal"] >= first_day)
            & (df_p["DataFinal"] <= last_day)
        )
        n_desl = int(cond_desl.sum())

        series[first_day] = 0 if n_inic == 0 else n_desl / n_inic * 100

    serie = pd.Series(series).sort_index()
    if serie.empty:
        return {}

    ma   = moving_average(serie, 3)
    gr   = growth_rate(serie)
    std  = std_deviation(serie)
    lq, ls = get_recent_metrics(serie)

    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date":   end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "percentual"),
        "growth_rate":    formatar_valor_utils(gr * 100 if gr else 0, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "percentual"),
        "last_quarter":   lq,
        "last_semester":  ls,
        "raw_data": {
            d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "percentual")
            for d, v in serie.to_dict().items()
        },
    }

def historical_crescimento_sustentavel(months=12):
    """
    Histórico para Crescimento Sustentável calculado como:
    
      Crescimento Sustentável = ΔFaturamento (%) - ΔCusto (%)
      
    Onde:
      ΔFaturamento (%) = ((Faturamento Atual - Faturamento Anterior) / Faturamento Anterior) * 100
      ΔCusto (%)       = ((Custo Atual - Custo Anterior) / Custo Anterior) * 100

    Essa função agrupa os dados da BaseEshows e Base2 usando os campos 'Ano' e 'Mês'.
    """
    import pandas as pd
    from datetime import timedelta

    print(">> Iniciando cálculo histórico de Crescimento Sustentável (agrupado por Ano e Mês).")
    
    # 1) Carrega as bases
    df_eshows = carregar_base_eshows()
    df_base2 = carregar_base2()
    
    if df_eshows is None or df_eshows.empty or df_base2 is None or df_base2.empty:
        print(">> Dados do eshows ou base2 estão vazios.")
        return {}
    
    # 2) Cria coluna 'Period' na BaseEshows a partir de 'Ano' e 'Mês'
    df_eshows['Period'] = pd.to_datetime(
        df_eshows['Ano'].astype(str) + '-' + df_eshows['Mês'].astype(str) + '-01',
        errors='coerce'
    )
    
    # Define as colunas de faturamento conforme a função de variáveis
    COLUNAS_FATURAMENTO = [
        "Comissão B2B",
        "Comissão B2C",
        "Antecipação de Cachês",
        "Curadoria",
        "SaaS Percentual",
        "SaaS Mensalidade",
        "Notas Fiscais"
    ]
    # Garante que cada coluna exista e seja numérica
    for col in COLUNAS_FATURAMENTO:
        if col not in df_eshows.columns:
            df_eshows[col] = 0
        else:
            df_eshows[col] = pd.to_numeric(df_eshows[col], errors='coerce').fillna(0)
    
    # Agrega faturamento por mês
    df_fat = df_eshows.groupby('Period')[COLUNAS_FATURAMENTO].sum()
    df_fat['Faturamento'] = df_fat.sum(axis=1)
    df_fat = df_fat[['Faturamento']].reset_index()
    
    # 3) Cria coluna 'Period' na Base2 usando os campos 'Ano' e 'Mês'
    df_base2['Period'] = pd.to_datetime(
        df_base2['Ano'].astype(str) + '-' + df_base2['Mês'].astype(str) + '-01',
        errors='coerce'
    )
    if "Custos" not in df_base2.columns:
        df_base2["Custos"] = 0
    else:
        df_base2["Custos"] = pd.to_numeric(df_base2["Custos"], errors='coerce').fillna(0)
    df_cst = df_base2.groupby('Period')['Custos'].sum().reset_index()
    
    # 4) Mescla os dados mensais
    df_merged = pd.merge(df_fat, df_cst, on='Period', how='inner')
    df_merged = df_merged.sort_values('Period')
    print(">> Dados mensais agregados:")
    print(df_merged)
    
    # 5) Para comparar com o mesmo mês do ano anterior, crie uma versão "deslocada" dos dados:
    df_prev = df_merged.copy()
    # Adiciona 1 ano para que o registro de 2023 vire 2024 ao fazer o merge
    df_prev['Period'] = df_prev['Period'] + pd.DateOffset(years=1)
    df_prev = df_prev.rename(columns={'Faturamento': 'Faturamento_prev', 'Custos': 'Custos_prev'})
    
    # Mescla: cada registro atual com o registro do mesmo mês do ano anterior
    df_compare = pd.merge(df_merged, df_prev, on='Period', how='inner')
    # df_compare terá: Period, Faturamento, Custos, Faturamento_prev, Custos_prev
    
    # 6) Calcula as variações percentuais e o Crescimento Sustentável
    def calc_growth(current, prev):
        return ((current - prev) / prev) * 100 if prev > 0 else 0

    df_compare['Delta_Fat'] = df_compare.apply(
        lambda row: calc_growth(row['Faturamento'], row['Faturamento_prev']), axis=1
    )
    df_compare['Delta_Cst'] = df_compare.apply(
        lambda row: calc_growth(row['Custos'], row['Custos_prev']), axis=1
    )
    df_compare['Crescimento_Sustentavel'] = df_compare['Delta_Fat'] - df_compare['Delta_Cst']
    
    print(">> Dados comparados com ano anterior:")
    print(df_compare[['Period', 'Faturamento', 'Faturamento_prev', 'Custos', 'Custos_prev', 
                      'Delta_Fat', 'Delta_Cst', 'Crescimento_Sustentavel']])
    
    # 7) Selecione os últimos 'months' registros (apenas os períodos com comparação)
    df_compare = df_compare.sort_values('Period').tail(months)
    
    # Cria a série com índice = Period e valor = Crescimento Sustentável
    cs_series = df_compare.set_index('Period')['Crescimento_Sustentavel']
    
    if cs_series.empty:
        print(">> Nenhum período com dados do ano anterior encontrado.")
        return {}
    
    # 8) Calcula as métricas históricas (supondo que as funções auxiliares estão implementadas)
    ma = moving_average(cs_series, window=3)
    gr = growth_rate(cs_series)
    std = std_deviation(cs_series)
    last_q, last_s = get_recent_metrics(cs_series, fmt='percentual')
    
    result = {
        "start_date": cs_series.index.min().strftime("%Y-%m-%d"),
        "end_date": cs_series.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in cs_series.to_dict().items()}
    }
    
    print(">> Resultado final histórico de Crescimento Sustentável:")
    print(result)
    return result

def historical_inadimplencia_real(months=12):
    """
    Histórico para Inadimplência Real utilizando o mesmo método de cálculo da função
    get_inadimplencia_real_variables.
    """
    from datetime import timedelta
    import pandas as pd

    print(">> Iniciando cálculo histórico da Inadimplência Real (método variáveis).")

    # 1) Carrega a base eshows e converte datas
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        print(">> Base de eshows vazia ou não carregada.")
        return {}
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')

    # 2) Define o período histórico com base na data máxima da base
    overall_max = df_eshows["Data do Show"].max()
    overall_min = overall_max - pd.DateOffset(months=months)
    dates = pd.date_range(start=overall_min, end=overall_max, freq='ME')
    print(f">> Período histórico: de {dates[0].strftime('%Y-%m-%d')} até {dates[-1].strftime('%Y-%m-%d')}")

    # 3) Carrega os dados de inadimplência (casas e artistas)
    df_inad_casas, df_inad_artistas = carregar_base_inad()
    
    # ADICIONAR ESTE BLOCO LOGO APÓS CARREGAR OS DADOS
    print(f">> DIAGNÓSTICO: Colunas em df_inad_artistas: {df_inad_artistas.columns.tolist()}")
    try:
        # Verificar se a função pode acessar ID_Boleto diretamente
        teste = df_inad_artistas["ID_Boleto"].iloc[0] if len(df_inad_artistas) > 0 else None
        print(f">> TESTE OK: Conseguiu acessar ID_Boleto: {teste}")
    except Exception as e:
        print(f">> ERRO ao acessar ID_Boleto: {e}")
        # Se não conseguir acessar ID_Boleto, tentar corrigir a situação
        print(">> Tentando garantir que ID_Boleto exista no DataFrame...")
        df_inad_artistas = df_inad_artistas.copy()  # Criar uma cópia explícita
        
        # Verificar e corrigir as colunas necessárias
        if "ID_Boleto" not in df_inad_artistas.columns:
            print(">> ID_Boleto não encontrado. Tentando criar...")
            # Tentar várias estratégias para criar ID_Boleto
            if "ID" in df_inad_artistas.columns:
                df_inad_artistas["ID_Boleto"] = df_inad_artistas["ID"]
                print(">> ID_Boleto criado a partir de ID")
            else:
                # Se não houver coluna ID, criar ID_Boleto do zero
                df_inad_artistas["ID_Boleto"] = range(len(df_inad_artistas))
                print(">> ID_Boleto criado sequencialmente (nenhuma coluna ID encontrada)")


    # 4) Processa df_inad_casas: converte AnoVenc, MesVenc, DiaVenc e gera DataVenc
    df_casas = df_inad_casas.copy()
    for col in ["AnoVenc", "MesVenc", "DiaVenc"]:
        if col in df_casas.columns:
            df_casas[col] = pd.to_numeric(df_casas[col], errors="coerce").fillna(0)
    
    if "DiaVenc" in df_casas.columns:
        df_casas.loc[df_casas["DiaVenc"] <= 0, "DiaVenc"] = 1
    
    # Gerar DataVenc se as colunas necessárias existirem
    if all(col in df_casas.columns for col in ["AnoVenc", "MesVenc", "DiaVenc"]):
        try:
            df_casas["DataVenc"] = pd.to_datetime({
                "year": df_casas["AnoVenc"].astype(int),
                "month": df_casas["MesVenc"].astype(int),
                "day": df_casas["DiaVenc"].astype(int)
            }, errors="coerce")
        except Exception as e:
            print(f">> Erro ao criar DataVenc: {e}")
            df_casas["DataVenc"] = pd.NaT

    # 5) Processa df_inad_artistas: garante que Adiantamento esteja em minúsculas
    df_artistas = df_inad_artistas.copy()
    if "Adiantamento" in df_artistas.columns:
        df_artistas["Adiantamento"] = df_artistas["Adiantamento"].astype(str).str.lower().fillna("")
    else:
        print(">> Coluna 'Adiantamento' não encontrada em df_artistas")
        df_artistas["Adiantamento"] = "não"

    # 6) Itera para cada mês no período e calcula a inadimplência real
    inad_series = {}
    for period_end in dates:
        period_start = period_end.replace(day=1)

        # 6.1) Filtro do faturamento no período (usando COLUNAS_FATURAMENTO)
        df_period = df_eshows[(df_eshows["Data do Show"] >= period_start) & 
                              (df_eshows["Data do Show"] <= period_end)].copy()
        for c in COLUNAS_FATURAMENTO:
            if c not in df_period.columns:
                df_period[c] = 0
            else:
                df_period[c] = pd.to_numeric(df_period[c], errors='coerce').fillna(0)
        fat = df_period[COLUNAS_FATURAMENTO].sum().sum()
        if fat <= 0:
            inad_rate = 0
            inad_series[period_end] = inad_rate
            continue

        # 6.2) Define dt_min e dt_max para o período
        dt_min = period_start
        dt_max = period_end

        # 6.3) Filtra df_casas para o período e status inadimplente
        if "DataVenc" not in df_casas.columns:
            print(">> Coluna 'DataVenc' não encontrada em df_casas")
            continue
            
        mask_casas = (df_casas["DataVenc"] >= dt_min) & (df_casas["DataVenc"] <= dt_max)
        df_casas_periodo = df_casas[mask_casas].copy()
        
        if "Status" not in df_casas_periodo.columns:
            print(">> Coluna 'Status' não encontrada em df_casas_periodo")
            continue
            
        status_inad = ["Vencido", "DUNNING_REQUESTED"]
        df_inad = df_casas_periodo[df_casas_periodo["Status"].isin(status_inad)].copy()
        cutoff_date = dt_max - timedelta(days=22)
        df_inad = df_inad[df_inad["DataVenc"] <= cutoff_date]

        if df_inad.empty:
            inad_rate = 0
            inad_series[period_end] = inad_rate
            continue

        # 6.4) Filtra adiantamentos em artistas para os boletos inadimplentes
        # Garantir que ID_Boleto e Adiantamento existam em df_artistas
        if "ID_Boleto" not in df_artistas.columns or "Adiantamento" not in df_artistas.columns:
            print(">> Colunas necessárias não encontradas em df_artistas")
            continue
            
        df_adiant = df_artistas[(df_artistas["Adiantamento"] == "sim") &
                                (df_artistas["ID_Boleto"].isin(df_inad["ID_Boleto"]))].copy()
                                
        if "Valor Bruto" not in df_adiant.columns:
            print(">> Coluna 'Valor Bruto' não encontrada em df_adiant")
            continue
            
        df_adiant["Valor Bruto"] = pd.to_numeric(df_adiant["Valor Bruto"], errors='coerce').fillna(0)
        
        if "Valor Real" not in df_inad.columns:
            print(">> Coluna 'Valor Real' não encontrada em df_inad")
            continue
            
        df_inad["Valor Real"] = pd.to_numeric(df_inad["Valor Real"], errors='coerce').fillna(0)

        if df_adiant.empty:
            inad_rate = 0
            inad_series[period_end] = inad_rate
            continue

        # 6.5) Agrupa por ID_Boleto e ajusta o valor adiantado (mínimo entre Valor Bruto e Valor Real)
        df_adiant_grouped = df_adiant.groupby("ID_Boleto")["Valor Bruto"].sum().reset_index()
        df_adiant_grouped = df_adiant_grouped.merge(
            df_inad[["ID_Boleto", "Valor Real"]],
            on="ID_Boleto",
            how="left"
        )
        df_adiant_grouped["Valor Adiantado Ajustado"] = df_adiant_grouped.apply(
            lambda row: min(row["Valor Bruto"], row["Valor Real"]) if pd.notnull(row["Valor Real"]) else 0,
            axis=1
        )
        valor_adiantado_inad = df_adiant_grouped["Valor Adiantado Ajustado"].sum()

        # 6.6) Calcula a inadimplência real para o período
        inad_rate = (valor_adiantado_inad / fat) * 100
        inad_series[period_end] = inad_rate

        print(f">> Período {period_start.strftime('%Y-%m-%d')} a {period_end.strftime('%Y-%m-%d')}:")
        print(f"   Faturamento = {fat}, Valor adiantado inadimplente = {valor_adiantado_inad}, Taxa = {inad_rate:.2f}%")

    # 7) Converte a série para pandas e calcula métricas históricas
    if not inad_series:
        print(">> Não foi possível calcular taxas de inadimplência para nenhum período")
        return {
            "start_date": dates[0].strftime("%Y-%m-%d") if len(dates) > 0 else "",
            "end_date": dates[-1].strftime("%Y-%m-%d") if len(dates) > 0 else "",
            "moving_average": "0,00%",
            "growth_rate": "0,00%",
            "std_deviation": "0,00%",
            "last_quarter": "0,00%",
            "last_semester": "0,00%",
            "raw_data": {}
        }
        
    inad_series_pd = pd.Series(inad_series).sort_index()
    ma = moving_average(inad_series_pd, window=3)
    gr = growth_rate(inad_series_pd)
    std = std_deviation(inad_series_pd)
    last_q, last_s = get_recent_metrics(inad_series_pd, fmt='percentual')

    result = {
        "start_date": inad_series_pd.index.min().strftime("%Y-%m-%d"),
        "end_date": inad_series_pd.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'percentual'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                     for d, v in inad_series_pd.to_dict().items()}
    }

    print(">> Resultado final histórico Inadimplência Real:")
    print(result)
    return result

def historical_palcos_vazios(months=12):
    """
    Histórico para Palcos Vazios.
    Calcula o número de ocorrências com TIPO "Palco vazio" por mês.
    Valores de médias e desvio são formatados como 'numero' e growth_rate em 'percentual'.
    """
    df_ocorr = carregar_ocorrencias()
    if df_ocorr is None or df_ocorr.empty:
        return {}
    if "DATA" in df_ocorr.columns:
        df_ocorr = df_ocorr.rename(columns={"DATA": "Data"})
    df_ocorr['Data'] = pd.to_datetime(df_ocorr['Data'], errors='coerce')
    df_ocorr = df_ocorr.sort_values('Data')
    if "TIPO" not in df_ocorr.columns:
        return {}
    df_palco = df_ocorr[df_ocorr["TIPO"] == "Palco vazio"]
    if "ID_OCORRENCIA" in df_palco.columns:
        df_monthly = df_palco.groupby(pd.Grouper(key='Data', freq='ME')).agg({'ID_OCORRENCIA': 'nunique'}).reset_index()
        df_monthly.rename(columns={'ID_OCORRENCIA': 'Palcos Vazios'}, inplace=True)
    else:
        df_monthly = df_palco.groupby(pd.Grouper(key='Data', freq='ME')).size().reset_index(name='Palcos Vazios')
    
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    
    palcos_series = df_period.set_index('Data')['Palcos Vazios']
    ma = moving_average(palcos_series, window=3)
    gr = growth_rate(palcos_series)
    std = std_deviation(palcos_series)
    last_q, last_s = get_recent_metrics(palcos_series, fmt='numero')
    
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'numero'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'numero'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'numero')
                     for d, v in palcos_series.to_dict().items()}
    }

def historical_palcos_ativos(months=12):
    """
    Histórico para Palcos Ativos.
    Calcula o número de palcos ativos (únicos "Id da Casa") por mês a partir da base eShows.
    Valores: médias e desvio como 'numero'; growth_rate como 'percentual'.
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.sort_values('Data do Show')
    df_monthly = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Id da Casa': 'nunique'}).reset_index()
    df_monthly.rename(columns={'Id da Casa': 'Palcos Ativos'}, inplace=True)
    
    end_date = df_monthly['Data do Show'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_hist = df_monthly[df_monthly['Data do Show'] >= start_date]
    if df_hist.empty:
        return {}
    pa_series = df_hist.set_index('Data do Show')['Palcos Ativos']
    ma = moving_average(pa_series, window=3)
    gr = growth_rate(pa_series)
    std = std_deviation(pa_series)
    last_q, last_s = get_recent_metrics(pa_series, fmt='numero')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'numero'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'numero'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'numero')
                     for d, v in pa_series.to_dict().items()}
    }

def historical_ocorrencias(months=12):
    """
    Histórico para Ocorrências.
    Conta o número de ocorrências (excluindo as de tipo 'Leve') por mês.
    Valores formatados como 'numero'.
    """
    df_ocorr = carregar_ocorrencias()
    if df_ocorr is None or df_ocorr.empty:
        return {}
    if "DATA" in df_ocorr.columns:
        df_ocorr.rename(columns={"DATA": "Data"}, inplace=True)
    df_ocorr['Data'] = pd.to_datetime(df_ocorr['Data'], errors='coerce')
    df_ocorr = df_ocorr.dropna(subset=['Data']).sort_values('Data')
    if "TIPO" in df_ocorr.columns:
        df_ocorr = df_ocorr[df_ocorr["TIPO"] != "Leve"]
    # Agrupa ocorrências por mês
    if "ID_OCORRENCIA" in df_ocorr.columns:
        df_occ = df_ocorr.groupby(pd.Grouper(key='Data', freq='ME')).agg({'ID_OCORRENCIA': 'nunique'}).reset_index()
        df_occ.rename(columns={"ID_OCORRENCIA": "Ocorrencias"}, inplace=True)
    else:
        df_occ = df_ocorr.groupby(pd.Grouper(key='Data', freq='ME')).size().reset_index(name="Ocorrencias")
    if df_occ.empty:
        return {}
    end_date = df_occ['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_occ[df_occ['Data'] >= start_date]
    if df_period.empty:
        return {}
    ocorr_series = df_period.set_index('Data')["Ocorrencias"]
    ma = moving_average(ocorr_series, window=3)
    gr = growth_rate(ocorr_series)
    std = std_deviation(ocorr_series)
    last_q, last_s = get_recent_metrics(ocorr_series, fmt='numero')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'numero'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'numero'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'numero')
                     for d, v in ocorr_series.to_dict().items()}
    }

def historical_erros_operacionais(months: int = 12):
    """
    Série histórica dos 12 últimos meses *com erro registrado*.
    Coluna-fonte: "Op. Shows" da Base2.
    Retorna dict compatível com kpi_charts.kpi_hist_data().
    """
    df = carregar_base2()
    if df is None or df.empty:
        return {"raw_data": OrderedDict()}

    df = prepare_base2_with_date(df)            # garante coluna 'Data'

    # Coluna pode não existir ainda
    if "Op. Shows" not in df.columns:
        df["Op. Shows"] = 0
    else:
        df["Op. Shows"] = pd.to_numeric(
            df["Op. Shows"], errors="coerce"
        ).fillna(0)

    # Agrupa por ano-mês e soma erros do mês
    df_mensal = (
        df.groupby(pd.Grouper(key="Data", freq="MS"))  # MS = month start
          .agg({"Op. Shows": "sum"})
          .reset_index()
    )

    # Remove meses sem erro (> 0)
    df_mensal = df_mensal[df_mensal["Op. Shows"] > 0]
    if df_mensal.empty:
        return {"raw_data": OrderedDict()}

    # Mantém os N últimos meses com dados
    df_last = df_mensal.sort_values("Data").tail(months)

    # Série para métricas
    serie = df_last.set_index("Data")["Op. Shows"]

    # Métricas auxiliares
    ma  = moving_average(serie, window=3)
    gr  = growth_rate(serie) or 0
    std = std_deviation(serie) or 0
    last_q, last_s = get_recent_metrics(serie, fmt="monetario")

    # Raw data formatado
    raw = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "monetario"))
        for d, v in serie.items()
    )

    return {
        "start_date":   serie.index.min().strftime("%Y-%m-%d"),
        "end_date":     serie.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "monetario"),
        "growth_rate":    formatar_valor_utils(gr * 100, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw
    }

def historical_cidades(months=12):
    """
    Histórico para Número de Cidades.
    Conta cidades únicas por mês; valores médios e std formatados como 'numero'.
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show']).sort_values('Data do Show')
    df_monthly = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Cidade': 'nunique'}).reset_index()
    df_monthly.rename(columns={'Cidade': 'Cidades'}, inplace=True)
    if df_monthly.empty:
        return {}
    end_date = df_monthly['Data do Show'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data do Show'] >= start_date]
    if df_period.empty:
        return {}
    cidades_series = df_period.set_index('Data do Show')['Cidades']
    ma = moving_average(cidades_series, window=3)
    gr = growth_rate(cidades_series)
    std = std_deviation(cidades_series)
    last_q, last_s = get_recent_metrics(cidades_series, fmt='numero')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'numero'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'numero'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'numero')
                     for d, v in cidades_series.to_dict().items()}
    }

def historical_novos_palcos(months=12):
    """
    Histórico para Novos Palcos.
    Calcula o número de casas que tiveram o primeiro show em cada mês.
    Valores formatados como 'numero'.
    """
    df = carregar_base_eshows()
    if df is None or df.empty:
        return {}
    df['Data do Show'] = pd.to_datetime(df['Data do Show'], errors='coerce')
    df = df.dropna(subset=['Data do Show']).sort_values('Data do Show')
    # Encontra data do primeiro show de cada casa
    first_show = df.groupby('Id da Casa')['Data do Show'].min().reset_index()
    first_show['Month'] = first_show['Data do Show'].dt.to_period('M').dt.to_timestamp()
    novos_series = first_show.groupby('Month').size()
    if novos_series.empty:
        return {}
    # Filtra últimos 'months' meses
    end_date = novos_series.index.max()
    start_date, _ = get_date_range_for_period(end_date, months)
    novos_series = novos_series[novos_series.index >= start_date]
    if novos_series.empty:
        return {}
    ma = moving_average(novos_series, window=3)
    gr = growth_rate(novos_series)
    std = std_deviation(novos_series)
    last_q, last_s = get_recent_metrics(novos_series, fmt='numero')
    return {
        "start_date": novos_series.index.min().strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'numero'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'numero'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'numero')
                     for d, v in novos_series.to_dict().items()}
    }

def historical_fat_ka(months=12):
    """
    Histórico para Faturamento KA (Contas Chave).
    Calcula o faturamento mensal dos shows dos grupos-chave (top5 do ano anterior ao final do período).
    Utiliza a função `faturamento_dos_grupos` de utils.py para consistência.
    Valores: média e std 'monetario'; growth_rate em 'percentual'.
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {"raw_data": OrderedDict()}

    # Garantir colunas e tipos
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show'])
    df_eshows = ensure_grupo_col(df_eshows) # Garante a coluna 'Grupo'
    if 'Grupo' not in df_eshows.columns:
        print("[hist.historical_fat_ka] Coluna 'Grupo' não encontrada após ensure_grupo_col.")
        return {"raw_data": OrderedDict()}

    # Determinar período e ano de referência para Top 5
    today_month = pd.Timestamp.today().normalize().replace(day=1)
    last_data_month = df_eshows['Data do Show'].max().normalize().replace(day=1) if not df_eshows.empty else today_month
    last_month = max(today_month, last_data_month)
    period_starts = pd.date_range(end=last_month, periods=months, freq='MS') # Inícios de mês

    ano_referencia_top5 = last_month.year # Usa o ano do último mês como referência
    print(f"[hist.historical_fat_ka] Ano de referência para Top 5: {ano_referencia_top5}")
    top5_list = obter_top5_grupos_ano_anterior(df_eshows, ano_referencia_top5)
    if not top5_list:
        print("[hist.historical_fat_ka] Lista Top 5 está vazia.")
        return {"raw_data": OrderedDict()}
    print(f"[hist.historical_fat_ka] Top 5 Grupos: {[g[0] for g in top5_list]}")

    # Calcular faturamento KA mensalmente
    serie_vals = OrderedDict()
    for month_start in period_starts:
        ano_iter = month_start.year
        mes_iter = month_start.month
        periodo_iter = 'Mês Aberto'

        # Filtrar dados do mês
        df_principal_iter = filtrar_periodo_principal(
            df_eshows,
            ano_iter,
            periodo_iter,
            mes_iter,
            custom_range=None
        )

        if df_principal_iter.empty:
            fat_ka_mes = 0.0
        else:
            # Calcular faturamento KA para o mês
            fat_ka_mes = faturamento_dos_grupos(df_principal_iter, top5_list)

        serie_vals[month_start] = fat_ka_mes
        print(f"[hist.historical_fat_ka] Fat KA para {ano_iter}-{mes_iter:02d}: {fat_ka_mes:.2f}")

    # Finalizar e formatar retorno
    if not serie_vals:
        return {"raw_data": OrderedDict()}

    serie = pd.Series(serie_vals).sort_index()

    # Métricas auxiliares
    ma = moving_average(serie, 3) if len(serie) >= 3 else pd.Series([0]*len(serie), index=serie.index)
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie, fmt="monetario")

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "monetario"))
        for d, v in serie.items()
    )

    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    print(f"[hist.historical_fat_ka] Finalizando. Série: {serie.to_dict()}")

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "monetario"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_take_rate_ka(months=12):
    """
    Histórico para Take Rate KA (Contas Chave).
    Calcula mensalmente: (Faturamento KA / GMV KA) * 100.
    Faturamento KA usa `faturamento_dos_grupos`.
    GMV KA é a soma de `Valor Total do Show` dos grupos KA no mês.
    Valores formatados em 'percentual'.
    """
    # ---------- 1) Carrega bases e garante colunas ----------
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {"raw_data": OrderedDict()}

    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show'])
    df_eshows = ensure_grupo_col(df_eshows)

    # Garante coluna Valor Total do Show
    if "Valor Total do Show" not in df_eshows.columns:
        for alt in ["ValorTotaldoShow", "Valor_Total", "Valor_Total_do_Show"]:
            if alt in df_eshows.columns:
                df_eshows.rename(columns={alt: "Valor Total do Show"}, inplace=True)
                break
        if "Valor Total do Show" not in df_eshows.columns:
            df_eshows["Valor Total do Show"] = 0
    df_eshows["Valor Total do Show"] = pd.to_numeric(df_eshows["Valor Total do Show"], errors='coerce').fillna(0)

    # ---------- 2) Determina Top 5 e Período ----------
    today_month = pd.Timestamp.today().normalize().replace(day=1)
    last_data_month = df_eshows['Data do Show'].max().normalize().replace(day=1) if not df_eshows.empty else today_month
    last_month = max(today_month, last_data_month)
    period_starts = pd.date_range(end=last_month, periods=months, freq='MS')

    ano_referencia_top5 = last_month.year
    print(f"[hist.historical_take_rate_ka] Ano de referência para Top 5: {ano_referencia_top5}")
    top5_list = obter_top5_grupos_ano_anterior(df_eshows, ano_referencia_top5)
    if not top5_list:
        print("[hist.historical_take_rate_ka] Lista Top 5 está vazia.")
        return {"raw_data": OrderedDict()}
    print(f"[hist.historical_take_rate_ka] Top 5 Grupos: {[g[0] for g in top5_list]}")
    grp_names = [g[0] for g in top5_list]

    # ---------- 3) Itera e calcula mensalmente ----------
    serie_vals = OrderedDict()
    for month_start in period_starts:
        ano_iter = month_start.year
        mes_iter = month_start.month
        periodo_iter = 'Mês Aberto'

        # Filtra dados do mês
        df_principal_iter = filtrar_periodo_principal(
            df_eshows, ano_iter, periodo_iter, mes_iter, custom_range=None
        )

        if df_principal_iter.empty:
            take_rate_ka_mes = 0.0
        else:
            # Calcula faturamento KA do mês
            fat_ka_mes = faturamento_dos_grupos(df_principal_iter, top5_list)

            # Calcula GMV KA do mês
            df_ka_iter = df_principal_iter[df_principal_iter['Grupo'].isin(grp_names)]
            gmv_ka_mes = df_ka_iter['Valor Total do Show'].sum()

            # Calcula Take Rate KA do mês
            take_rate_ka_mes = (fat_ka_mes / gmv_ka_mes * 100) if gmv_ka_mes > 0 else 0.0

        serie_vals[month_start] = take_rate_ka_mes
        print(f"[hist.historical_take_rate_ka] Take Rate KA para {ano_iter}-{mes_iter:02d}: {take_rate_ka_mes:.2f}%")

    # ---------- 4) Finaliza e formata retorno ----------
    if not serie_vals:
        return {"raw_data": OrderedDict()}

    serie = pd.Series(serie_vals).sort_index()

    ma = moving_average(serie, 3) if len(serie) >= 3 else pd.Series([0]*len(serie), index=serie.index)
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie, fmt="percentual") # Formato percentual

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "percentual"))
        for d, v in serie.items()
    )

    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    print(f"[hist.historical_take_rate_ka] Finalizando. Série: {serie.to_dict()}")

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "percentual"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "percentual"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_num_shows(months=12):
    """
    Histórico para Número de Shows.
    Conta o número de shows únicos por mês.
    Valores: médias e std como 'numero'; growth_rate como 'percentual'.
    """
    df = carregar_base_eshows()
    if df is None or df.empty:
        return {}
    df['Data do Show'] = pd.to_datetime(df['Data do Show'], errors='coerce')
    df = df.dropna(subset=['Data do Show']).sort_values('Data do Show')
    df_monthly = df.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Id do Show': 'nunique'}).reset_index()
    df_monthly.rename(columns={'Id do Show': 'Num Shows'}, inplace=True)
    if df_monthly.empty:
        return {}
    end_date = df_monthly['Data do Show'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_hist = df_monthly[df_monthly['Data do Show'] >= start_date]
    if df_hist.empty:
        return {}
    series = df_hist.set_index('Data do Show')['Num Shows']
    ma = moving_average(series, window=3)
    gr = growth_rate(series)
    std = std_deviation(series)
    last_q, last_s = get_recent_metrics(series, fmt='numero')
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], 'numero'),
        "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
        "std_deviation": formatar_valor_utils(std, 'numero'),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'numero')
                     for d, v in series.to_dict().items()}
    }

def historical_custos_totais(months: int = 12):
    df = carregar_base2()
    if df is None or df.empty:
        return {"raw_data": OrderedDict()}

    # garante Coluna mês
    mes_col = "Mes_ord" if "Mes_ord" in df.columns else "Mês"

    # 1) agrupa por ano-mês  ---------------------------------------------------
    df_mensal = (
        df.groupby(["Ano", mes_col], as_index=False)["Custos"].sum()
    )
    # cria data (1º dia do mês)
    df_mensal["Data"] = pd.to_datetime(
        df_mensal["Ano"].astype(int).astype(str) + "-"
        + df_mensal[mes_col].astype(int).astype(str) + "-01"
    )

    # 2) descarta meses sem custos (> 0) ---------------------------------------
    df_mensal = df_mensal[df_mensal["Custos"] > 0]
    if df_mensal.empty:
        return {"raw_data": OrderedDict()}          # nada a exibir

    # 3) últimos N meses com dados > 0 ----------------------------------------
    df_last = df_mensal.sort_values("Data").tail(months)

    raw = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "monetario"))
        for d, v in zip(df_last["Data"], df_last["Custos"])
    )

    # métricas básicas (opcionais)
    serie = df_last.set_index("Data")["Custos"]
    ma  = serie.rolling(3).mean().iloc[-1] or 0
    gr  = (serie.iloc[-1] - serie.iloc[0]) / serie.iloc[0] if len(serie) > 1 else 0
    std = serie.std() or 0

    return {
        "start_date":   serie.index.min().strftime("%Y-%m-%d"),
        "end_date":     serie.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma, "monetario"),
        "growth_rate":    formatar_valor_utils(gr*100, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   formatar_valor_utils(serie.tail(3).sum(), "monetario"),
        "last_semester":  formatar_valor_utils(serie.tail(6).sum(), "monetario"),
        "raw_data":       raw
    }

def historical_gmv(months: int = 12) -> dict:
    """
    Histórico para GMV (Gross Merchandise Volume) dos últimos *months* meses.
    Soma o valor total do show mensal (Valor Total do Show) e calcula métricas.
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    # Garante coluna Valor Total do Show
    if "Valor Total do Show" not in df_eshows.columns:
        for alt in ["ValorTotaldoShow", "Valor_Total", "Valor_Total_do_Show"]:
            if alt in df_eshows.columns:
                df_eshows.rename(columns={alt: "Valor Total do Show"}, inplace=True)
                break
        if "Valor Total do Show" not in df_eshows.columns:
            df_eshows["Valor Total do Show"] = 0
    df_eshows["Valor Total do Show"] = pd.to_numeric(df_eshows["Valor Total do Show"], errors="coerce").fillna(0)
    if "Data do Show" not in df_eshows.columns:
        return {}
    df_eshows["Data do Show"] = pd.to_datetime(df_eshows["Data do Show"], errors='coerce')
    df_group = df_eshows.groupby(pd.Grouper(key="Data do Show", freq="M"))["Valor Total do Show"].sum()
    df_group = df_group[df_group > 0]
    if df_group.empty:
        return {}
    series = df_group.tail(months)
    if series.empty:
        return {}
    ma = moving_average(series, window=3)
    gr = growth_rate(series)
    std = std_deviation(series)
    last_q, last_s = get_recent_metrics(series, fmt="monetario")
    return {
        "start_date": series.index.min().strftime("%Y-%m-%d"),
        "end_date": series.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "monetario"),
        "growth_rate": formatar_valor_utils((gr or 0) * 100, "percentual"),
        "std_deviation": formatar_valor_utils(std, "monetario"),
        "last_quarter": last_q,
        "last_semester": last_s,
        "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "monetario")
                     for d, v in series.to_dict().items()}
    }

def historical_ticket(months: int = 12) -> dict:
    """
    Ticket Médio histórico (GMV / nº de shows) para os últimos *months* meses.
    """
    df = carregar_base_eshows()
    if df.empty:
        return {}

    # ---------- garante coluna única ----------
    if "Valor Total do Show" not in df.columns:
        for alt in ["ValorTotaldoShow", "Valor_Total_do_Show"]:
            if alt in df.columns:
                df.rename(columns={alt: "Valor Total do Show"}, inplace=True)
                break
        if "Valor Total do Show" not in df.columns:
            df["Valor Total do Show"] = 0

    # elimina duplicadas mantendo a 1ª
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    df["Valor Total do Show"] = pd.to_numeric(
        df["Valor Total do Show"], errors="coerce"
    ).fillna(0)

    if "Data do Show" not in df.columns:
        return {}

    df["Data do Show"] = pd.to_datetime(df["Data do Show"], errors="coerce")
    df_group = (
        df.groupby(pd.Grouper(key="Data do Show", freq="M"))
        .agg({"Valor Total do Show": "sum", "Id do Show": "count"})
        .rename(columns={"Valor Total do Show": "GMV", "Id do Show": "Qtd"})
    )

    df_group = df_group[df_group["Qtd"] > 0]
    if df_group.empty:
        return {}

    df_group["Ticket"] = df_group["GMV"] / df_group["Qtd"]
    series = df_group["Ticket"].tail(months)

    # métricas
    ma   = moving_average(series, 3)
    gr   = growth_rate(series)
    std  = std_deviation(series)
    qtr, sem = get_recent_metrics(series, fmt="monetario")

    return {
        "start_date": series.index.min().strftime("%Y-%m-%d"),
        "end_date":   series.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "monetario"),
        "growth_rate":    formatar_valor_utils((gr or 0) * 100, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   qtr,
        "last_semester":  sem,
        "raw_data": {
            d.strftime("%Y-%m-%d"): formatar_valor_utils(v, "monetario")
            for d, v in series.to_dict().items()
        }
    }

def historical_nps_artistas(months=12):
    """
    Histórico para NPS Artistas.
    Calcula a média mensal do NPS Artistas.
    Valores formatados em 'percentual'.
    """
    df = carregar_base2()
    if df is None or df.empty:
        return {}
    df = prepare_base2_with_date(df)
    if "NPS Artistas" not in df.columns:
        df["NPS Artistas"] = 0
    else:
        df["NPS Artistas"] = pd.to_numeric(df["NPS Artistas"], errors='coerce').fillna(0)
    df_monthly = df.groupby(pd.Grouper(key='Data', freq='ME')).agg({'NPS Artistas': 'mean'}).reset_index()
    if df_monthly.empty:
        return {}
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    series = df_period.set_index('Data')['NPS Artistas']
    ma = moving_average(series, window=3)
    gr = growth_rate(series)
    std = std_deviation(series)
    last_q, last_s = get_recent_metrics(series, fmt='percentual')
    return {
         "start_date": start_date.strftime("%Y-%m-%d"),
         "end_date": end_date.strftime("%Y-%m-%d"),
         "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
         "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
         "std_deviation": formatar_valor_utils(std, 'percentual'),
         "last_quarter": last_q,
         "last_semester": last_s,
         "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                      for d, v in series.to_dict().items()}
    }

def historical_nps_equipe(months=12):
    """
    Histórico para NPS Equipe.
    Calcula a média mensal do NPS Equipe.
    Valores formatados em 'percentual'.
    """
    df = carregar_base2()
    if df is None or df.empty:
        return {}
    df = prepare_base2_with_date(df)
    if "NPS Equipe" not in df.columns:
        df["NPS Equipe"] = 0
    else:
        df["NPS Equipe"] = pd.to_numeric(df["NPS Equipe"], errors='coerce').fillna(0)
    df_monthly = df.groupby(pd.Grouper(key='Data', freq='ME')).agg({'NPS Equipe': 'mean'}).reset_index()
    if df_monthly.empty:
        return {}
    end_date = df_monthly['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data'] >= start_date]
    if df_period.empty:
        return {}
    series = df_period.set_index('Data')['NPS Equipe']
    ma = moving_average(series, window=3)
    gr = growth_rate(series)
    std = std_deviation(series)
    last_q, last_s = get_recent_metrics(series, fmt='percentual')
    return {
         "start_date": start_date.strftime("%Y-%m-%d"),
         "end_date": end_date.strftime("%Y-%m-%d"),
         "moving_average": formatar_valor_utils(ma.iloc[-1], 'percentual'),
         "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
         "std_deviation": formatar_valor_utils(std, 'percentual'),
         "last_quarter": last_q,
         "last_semester": last_s,
         "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'percentual')
                      for d, v in series.to_dict().items()}
    }

def historical_lucro_liquido(months=12):
    """
    Histórico para Lucro Líquido.
    Calcula: Lucro Líquido = Faturamento Eshows - Custos Totais.
    Faturamento é calculado a partir de colunas padrão; custos a partir da Base2.
    Valores: média e std monetários; growth_rate em 'percentual'.
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {}
    COLUNAS_FATURAMENTO = [
         "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
         "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    for col in COLUNAS_FATURAMENTO:
        if col not in df_eshows.columns:
            df_eshows[col] = 0
        else:
            df_eshows[col] = pd.to_numeric(df_eshows[col], errors='coerce').fillna(0)
    df_eshows['Faturamento'] = df_eshows[COLUNAS_FATURAMENTO].sum(axis=1)
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.sort_values('Data do Show')
    df_fat_monthly = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Faturamento': 'sum'}).reset_index()

    df_base2 = carregar_base2()
    if df_base2 is None or df_base2.empty:
        return {}
    df_base2 = prepare_base2_with_date(df_base2)
    if "Custos" not in df_base2.columns:
        df_base2["Custos"] = 0
    else:
        df_base2["Custos"] = pd.to_numeric(df_base2["Custos"], errors='coerce').fillna(0)
    df_cst_monthly = df_base2.groupby(pd.Grouper(key='Data', freq='ME')).agg({'Custos': 'sum'}).reset_index()

    df_merged = pd.merge(df_fat_monthly, df_cst_monthly, left_on='Data do Show', right_on='Data', how='inner')
    df_merged.drop(columns=['Data'], inplace=True)
    df_merged.rename(columns={'Data do Show': 'Data'}, inplace=True)
    df_merged['Lucro Liquido'] = df_merged['Faturamento'] - df_merged['Custos']
    df_merged = df_merged.sort_values('Data')
    if df_merged.empty:
        return {}
    end_date = df_merged['Data'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_merged[df_merged['Data'] >= start_date]
    series = df_period.set_index('Data')['Lucro Liquido']
    ma = moving_average(series, window=3)
    gr = growth_rate(series)
    std = std_deviation(series)
    last_q, last_s = get_recent_metrics(series, fmt='monetario')
    return {
         "start_date": start_date.strftime("%Y-%m-%d"),
         "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
         "moving_average": formatar_valor_utils(ma.iloc[-1], 'monetario'),
         "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
         "std_deviation": formatar_valor_utils(std, 'monetario'),
         "last_quarter": last_q,
         "last_semester": last_s,
         "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'monetario')
                      for d, v in series.to_dict().items()}
    }

def historical_faturamento_eshows(months=12):
    """
    Histórico para Faturamento Eshows.
    Soma o faturamento total a partir da base eShows.
    Valores monetários são formatados como 'monetario'.
    """
    df = carregar_base_eshows()
    if df is None or df.empty:
        return {}
    COLUNAS_FATURAMENTO = [
         "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
         "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    for col in COLUNAS_FATURAMENTO:
        if col not in df.columns:
            df[col] = 0
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['Faturamento'] = df[COLUNAS_FATURAMENTO].sum(axis=1)
    df['Data do Show'] = pd.to_datetime(df['Data do Show'], errors='coerce')
    df = df.sort_values('Data do Show')
    df_monthly = df.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg({'Faturamento': 'sum'}).reset_index()
    if df_monthly.empty:
        return {}
    end_date = df_monthly['Data do Show'].max()
    start_date, _ = get_date_range_for_period(end_date, months)
    df_period = df_monthly[df_monthly['Data do Show'] >= start_date]
    series = df_period.set_index('Data do Show')['Faturamento']
    ma = moving_average(series, window=3)
    gr = growth_rate(series)
    std = std_deviation(series)
    last_q, last_s = get_recent_metrics(series, fmt='monetario')
    return {
         "start_date": start_date.strftime("%Y-%m-%d"),
         "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
         "moving_average": formatar_valor_utils(ma.iloc[-1], 'monetario'),
         "growth_rate": formatar_valor_utils(gr * 100 if gr is not None else 0, 'percentual'),
         "std_deviation": formatar_valor_utils(std, 'monetario'),
         "last_quarter": last_q,
         "last_semester": last_s,
         "raw_data": {d.strftime("%Y-%m-%d"): formatar_valor_utils(v, 'monetario')
                      for d, v in series.to_dict().items()}
    }

def historical_lifetime_novos_palcos(months: int = 12):
    """
    Lifetime médio dos NOVOS palcos.

    • Cliente é "novo" apenas no ano em que estreou (mesma regra do card).
    • Lifetime = (último show até o fim do mês  –  primeiro show) em DIAS.
      → convertimos para MESES dividindo por 30.
    • Retorna dicionário no formato esperado por kpi_charts.kpi_hist_data().
    """
    df = carregar_base_eshows()
    if df is None or df.empty:
        return {"raw_data": OrderedDict()}

    df["Data"] = pd.to_datetime(df["Data"])

    # janela de exibição
    last_date  = df["Data"].max().normalize().replace(day=1)            # último mês fechado
    start_date = (last_date - relativedelta(months=months - 1)).normalize()

    # earliest & last-show globais
    earliest = (df.groupby("Id da Casa")["Data"].min()
                  .rename("EarliestShow")
                  .reset_index())
    df = df.merge(earliest, on="Id da Casa", how="left")

    # série mensal
    idx = pd.date_range(start_date, last_date, freq="MS")
    lifetime_dict = OrderedDict()

    for month_start in idx:
        month_end     = month_start + relativedelta(months=1, days=-1)
        ano_corrente  = month_start.year

        # Ids que estrearam neste ANO
        ids_novos = earliest[
            earliest["EarliestShow"].dt.year == ano_corrente
        ]["Id da Casa"].values
        if len(ids_novos) == 0:
            lifetime_dict[month_start] = 0
            continue

        # último show ATÉ o fim do mês
        last_show_mes = (
            df[(df["Id da Casa"].isin(ids_novos)) &
               (df["Data"] <= month_end)]
            .groupby("Id da Casa")["Data"]
            .max()
            .rename("LastShowMes")
            .reset_index()
        )

        tmp = pd.merge(
            earliest[earliest["Id da Casa"].isin(ids_novos)],
            last_show_mes,
            on="Id da Casa",
            how="inner"
        )
        if tmp.empty:
            lifetime_dict[month_start] = 0
            continue

        tmp["DiffDays"] = (tmp["LastShowMes"] - tmp["EarliestShow"]).dt.days
        tmp = tmp[tmp["DiffDays"] >= 0]

        lifetime_dict[month_start] = (
            tmp["DiffDays"].mean() if not tmp.empty else 0
        )

    # dias → meses (1 casa decimal)
    serie = pd.Series(lifetime_dict) / 30

    # métricas auxiliares
    ma  = moving_average(serie, 3)
    gr  = growth_rate(serie) or 0
    std = std_deviation(serie) or 0
    last_q, last_s = get_recent_metrics(serie, fmt="numero")

    raw = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "numero"))
        for d, v in serie.items()
    )

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d"),
        "end_date":       serie.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "numero"),
        "growth_rate":    formatar_valor_utils(gr * 100, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "numero"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw
    }

def historical_fat_novos_palcos(months: int = 12):
    """
    Faturamento mensal dos NOVOS palcos, com corte ANO-a-ANO.

    Para cada mês M do ano Y:
      • considera-se "novo" a casa cujo PRIMEIRO show ocorreu
        em qualquer data de 1 jan Y até 31 dez Y.
      • mesmo que o primeiro show tenha sido antes do intervalo `months`,
        ela continua sendo tratada como "nova" durante todo o ano Y
        (e só nesse ano).

    Retorna dict no formato exigido por kpi_charts.kpi_hist_data().
    """
    df = carregar_base_eshows()
    if df is None or df.empty:
        return {"raw_data": OrderedDict()}

    # ---------- datas-chave --------------------------------------------
    df["Data"] = pd.to_datetime(df["Data"])
    last_date  = df["Data"].max().normalize().replace(day=1)          # último mês fechado
    start_date = (last_date - pd.DateOffset(months=months - 1)).normalize()

    # ---------- 1º show de cada casa (cálculo global) ------------------
    first_show = (
        df.groupby("Id da Casa")["Data"]
          .min()
          .rename("PrimeiroShow")
          .reset_index()
    )

    # ---------- apenas faturas dentro da janela de exibição -----------
    df_win = df[df["Data"] >= start_date].copy()
    df_win = df_win.merge(first_show, on="Id da Casa", how="left")

    # flag "novo no ano"
    df_win["NovoAnoFlag"] = (
        df_win["PrimeiroShow"].dt.year == df_win["Data"].dt.year
    )
    df_novos = df_win[df_win["NovoAnoFlag"]].copy()
    if df_novos.empty:
        return {"raw_data": OrderedDict()}

    # ---------- faturamento linha-a-linha ------------------------------
    for col in COLUNAS_FATURAMENTO:
        if col not in df_novos.columns:
            df_novos[col] = 0.0
    df_novos["FatLinha"] = df_novos[COLUNAS_FATURAMENTO].sum(axis=1)

    # ---------- agrega por mês ----------------------------------------
    df_novos["Mes"] = df_novos["Data"].dt.to_period("M").dt.to_timestamp()
    serie = (
        df_novos.groupby("Mes")["FatLinha"]
                .sum()
                .reindex(
                    pd.date_range(start_date, last_date, freq="MS"),   # todos os meses
                    fill_value=0
                )
    )

    # ---------- métricas auxiliares -----------------------------------
    ma  = moving_average(serie, 3)
    gr  = growth_rate(serie) or 0
    std = std_deviation(serie) or 0
    last_q, last_s = get_recent_metrics(serie, fmt="monetario")

    raw = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "monetario"))
        for d, v in serie.items()
    )

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d"),
        "end_date":       serie.index.max().strftime("%Y-%m-%d"),
        "moving_average": formatar_valor_utils(ma.iloc[-1], "monetario"),
        "growth_rate":    formatar_valor_utils(gr * 100, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw
    }


# ------------------------------------------------------------------
def historical_churn_novos_palcos(months: int = 12, dias_sem_show: int = 45):
    """
    Série mensal (últimos *months* meses) da quantidade de NOVOS palcos que deram churn.

    Utiliza a mesma lógica de `calcular_churn_novos_palcos` (utils.py) aplicada
    mensalmente para consistência com os cards do dashboard.

    - "Novo palco" para um mês = Palco cujo 1º show ocorreu NAQUELE mês.
    - Churn = Último show ocorreu no mês + dias_sem_show ultrapassou e não retornou até o fim do mês.
    """
    # ---------- 1) Carrega bases (se não forem globais) ----------
    try:
        # Tenta acessar DFs globais se existirem
        global df_eshows, df_casas_earliest
        if df_eshows is None or df_casas_earliest is None: raise NameError # Força o carregamento se não definidos
    except NameError:
        # Carrega se não forem globais ou se forem None
        print("[hist.historical_churn_novos_palcos] Carregando bases df_eshows e df_casas_earliest...")
        df_eshows = carregar_base_eshows()
        if df_eshows is not None and not df_eshows.empty:
            df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
            df_eshows.dropna(subset=['Data do Show', 'Id da Casa'], inplace=True)
            df_casas_earliest = df_eshows.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")
        else:
            df_casas_earliest = pd.DataFrame(columns=["Id da Casa", "EarliestShow"])
        print("[hist.historical_churn_novos_palcos] Bases carregadas.")


    if df_eshows is None or df_eshows.empty or df_casas_earliest is None: # df_casas_earliest pode estar vazio, mas não None
        print("[hist.historical_churn_novos_palcos] Erro: df_eshows ou df_casas_earliest não puderam ser carregados ou estão vazios.")
        return {"raw_data": OrderedDict()}

    # ---------- 2) Eixo temporal (últimos N meses) ----------------------
    today_month = pd.Timestamp.today().normalize().replace(day=1)
    last_data_month = df_eshows['Data do Show'].max().normalize().replace(day=1) if not df_eshows.empty else today_month
    last_month = max(today_month, last_data_month)
    # Gera os inícios de mês para os últimos 'months' meses
    period_starts = pd.date_range(end=last_month, periods=months, freq='MS') # MS = Month Start

    # ---------- 3) Itera sobre os meses ---------------------------------
    serie_vals = OrderedDict()

    for month_start in period_starts:
        ano_iter = month_start.year
        mes_iter = month_start.month
        periodo_ytd_iter = 'YTD' # <<< MUDANÇA: Considera palcos novos desde o início do ano até o mês atual

        print(f"[hist.historical_churn_novos_palcos] Calculando para: {ano_iter}-{mes_iter:02d}")

        # Filtra os palcos que se tornaram "novos" DESDE O INÍCIO DO ANO até este mês
        df_new_period_iter = filtrar_novos_palcos_por_periodo(
            df_casas_earliest,
            ano_iter,
            periodo_ytd_iter, # <<< MUDANÇA: Usa YTD
            mes_iter,         # <<< MUDANÇA: Passa o mês para limitar o YTD
            custom_range=None
        )

        # Calcula o churn que ocorreu NESTE MÊS para esses novos palcos
        churn_count_mes = calcular_churn_novos_palcos(
            ano=ano_iter,
            periodo='Mês Aberto', # <<< MUDANÇA: Calcula churn APENAS para este mês
            mes=mes_iter,
            start_date=None, # Usa ano/periodo/mes
            end_date=None,   # Usa ano/periodo/mes
            df_earliest=df_casas_earliest,
            df_eshows=df_eshows,
            df_new_period=df_new_period_iter, # Passa os novos palcos ACUMULADOS do ano
            dias_sem_show=dias_sem_show,
            uf=None # Churn geral, sem filtro de UF
        )

        serie_vals[month_start] = churn_count_mes
        print(f"[hist.historical_churn_novos_palcos] Resultado para {ano_iter}-{mes_iter:02d}: {churn_count_mes}")


    # ---------- 4) Finaliza e formata retorno --------------------------
    if not serie_vals:
         print("[hist.historical_churn_novos_palcos] Nenhum dado calculado.")
         return {"raw_data": OrderedDict()}

    serie = pd.Series(serie_vals).sort_index()

    # Métricas auxiliares
    ma = moving_average(serie, 3) if len(serie) >=3 else pd.Series([0]*len(serie), index=serie.index) # Evita erro com menos de 3 pontos
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0 # Evita erro com menos de 2 pontos
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie, fmt="numero")

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "numero"))
        for d, v in serie.items()
    )

    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    print(f"[hist.historical_churn_novos_palcos] Finalizando cálculo. Série: {serie.to_dict()}")

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "numero"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "numero"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_novos_palcos_ka(months=12):
    """
    Histórico para Novos Palcos em Contas-Chave (KA).
    Conta mensalmente quantos novos palcos (primeiro show no mês) pertencem aos grupos KA.
    Utiliza `filtrar_novos_palcos_por_periodo` e `novos_palcos_dos_grupos` de utils.py.
    """
    # ---------- 1) Carrega bases ----------
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {"raw_data": OrderedDict()}

    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show'])
    df_eshows = ensure_grupo_col(df_eshows)
    if 'Grupo' not in df_eshows.columns:
        print("[hist.historical_novos_palcos_ka] Coluna 'Grupo' não encontrada.")
        return {"raw_data": OrderedDict()}

    # Earliest show (necessário para filtrar novos palcos)
    df_casas_earliest = df_eshows.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")

    # ---------- 2) Determina Top 5 e Período ----------
    today_month = pd.Timestamp.today().normalize().replace(day=1)
    last_data_month = df_eshows['Data do Show'].max().normalize().replace(day=1) if not df_eshows.empty else today_month
    last_month = max(today_month, last_data_month)
    period_starts = pd.date_range(end=last_month, periods=months, freq='MS')

    ano_referencia_top5 = last_month.year
    print(f"[hist.historical_novos_palcos_ka] Ano de referência para Top 5: {ano_referencia_top5}")
    top5_list = obter_top5_grupos_ano_anterior(df_eshows, ano_referencia_top5)
    if not top5_list:
        print("[hist.historical_novos_palcos_ka] Lista Top 5 está vazia.")
        return {"raw_data": OrderedDict()}
    print(f"[hist.historical_novos_palcos_ka] Top 5 Grupos: {[g[0] for g in top5_list]}")

    # ---------- 3) Itera e calcula mensalmente ----------
    serie_vals = OrderedDict()
    for month_start in period_starts:
        ano_iter = month_start.year
        mes_iter = month_start.month
        periodo_iter = 'Mês Aberto'

        # Filtra dados gerais do mês
        df_principal_iter = filtrar_periodo_principal(
            df_eshows, ano_iter, periodo_iter, mes_iter, custom_range=None
        )

        # Filtra SOMENTE os palcos cujo PRIMEIRO show foi neste mês
        df_new_period_iter = filtrar_novos_palcos_por_periodo(
            df_casas_earliest, ano_iter, periodo_iter, mes_iter, custom_range=None
        )

        # Calcula quantos desses novos palcos pertencem aos grupos KA
        np_ka_mes = novos_palcos_dos_grupos(df_new_period_iter, df_principal_iter, top5_list)

        serie_vals[month_start] = np_ka_mes
        print(f"[hist.historical_novos_palcos_ka] Novos Palcos KA para {ano_iter}-{mes_iter:02d}: {np_ka_mes}")

    # ---------- 4) Finaliza e formata retorno ----------
    if not serie_vals:
        return {"raw_data": OrderedDict()}

    serie = pd.Series(serie_vals).sort_index()

    ma = moving_average(serie, 3) if len(serie) >= 3 else pd.Series([0]*len(serie), index=serie.index)
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie, fmt="numero") # Formato numero

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "numero"))
        for d, v in serie.items()
    )

    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    print(f"[hist.historical_novos_palcos_ka] Finalizando. Série: {serie.to_dict()}")

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "numero"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "numero"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_churn_ka(months=12, dias_sem_show=45):
    """
    Histórico para Churn de Contas-Chave (KA).
    Calcula mensalmente o número de casas KA que entraram em churn.
    Utiliza `get_churn_ka_for_period` de utils.py para consistência.
    """
    # ---------- 1) Carrega bases e garante colunas ----------
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {"raw_data": OrderedDict()}

    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show'])
    df_eshows = ensure_grupo_col(df_eshows)
    if 'Grupo' not in df_eshows.columns:
        print("[hist.historical_churn_ka] Coluna 'Grupo' não encontrada.")
        return {"raw_data": OrderedDict()}

    # ---------- 2) Determina Top 5 e Período ----------
    today_month = pd.Timestamp.today().normalize().replace(day=1)
    last_data_month = df_eshows['Data do Show'].max().normalize().replace(day=1) if not df_eshows.empty else today_month
    last_month = max(today_month, last_data_month)
    period_starts = pd.date_range(end=last_month, periods=months, freq='MS')

    ano_referencia_top5 = last_month.year
    print(f"[hist.historical_churn_ka] Ano de referência para Top 5: {ano_referencia_top5}")
    top5_list = obter_top5_grupos_ano_anterior(df_eshows, ano_referencia_top5)
    if not top5_list:
        print("[hist.historical_churn_ka] Lista Top 5 está vazia.")
        return {"raw_data": OrderedDict()}
    print(f"[hist.historical_churn_ka] Top 5 Grupos: {[g[0] for g in top5_list]}")

    # ---------- 3) Itera e calcula mensalmente ----------
    serie_vals = OrderedDict()
    for month_start in period_starts:
        ano_iter = month_start.year
        mes_iter = month_start.month
        periodo_iter = 'Mês Aberto'

        # Calcula churn KA para este mês específico
        churn_ka_mes = get_churn_ka_for_period(
            ano=ano_iter,
            periodo=periodo_iter,
            mes=mes_iter,
            top5_list=top5_list,
            start_date_main=None,
            end_date_main=None,
            dias_sem_show=dias_sem_show
        )

        serie_vals[month_start] = churn_ka_mes
        print(f"[hist.historical_churn_ka] Churn KA para {ano_iter}-{mes_iter:02d}: {churn_ka_mes}")

    # ---------- 4) Finaliza e formata retorno ----------
    if not serie_vals:
        return {"raw_data": OrderedDict()}

    serie = pd.Series(serie_vals).sort_index()

    ma = moving_average(serie, 3) if len(serie) >= 3 else pd.Series([0]*len(serie), index=serie.index)
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie, fmt="numero") # Formato numero

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "numero"))
        for d, v in serie.items()
    )

    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    print(f"[hist.historical_churn_ka] Finalizando. Série: {serie.to_dict()}")

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "numero"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "numero"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_num_colaboradores(months=12):
    """
    Histórico mensal do número de colaboradores ativos.
    Considera ativo se DataInicio <= fim_do_mes e (DataFinal é nulo ou DataFinal > fim_do_mes).
    """
    df_p = carregar_pessoas()
    if df_p is None or df_p.empty:
        return {"raw_data": OrderedDict()}

    df_p["DataInicio"] = pd.to_datetime(df_p.get("DataInicio"), errors="coerce")
    df_p["DataFinal"]  = pd.to_datetime(df_p.get("DataFinal"),  errors="coerce")
    df_p = df_p.dropna(subset=["DataInicio"]) # Precisa de data de início

    end_date   = pd.Timestamp.today().normalize()
    start_date = (end_date - relativedelta(months=months)).replace(day=1)
    # Usamos fim de mês para garantir que peguemos todos ativos naquele mês
    dates = pd.date_range(start=start_date, end=end_date, freq="ME") # ME = Month End

    series_vals = OrderedDict()
    for month_end in dates:
        ativos = (
            (df_p["DataInicio"] <= month_end) &
            (df_p["DataFinal"].isna() | (df_p["DataFinal"] > month_end))
        )
        series_vals[month_end.replace(day=1)] = int(ativos.sum()) # Armazena com início do mês

    serie = pd.Series(series_vals).sort_index()
    if serie.empty: return {"raw_data": OrderedDict()}

    ma = moving_average(serie, 3) if len(serie) >= 3 else pd.Series([0]*len(serie), index=serie.index)
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie, fmt="numero")

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "numero"))
        for d, v in serie.items()
    )
    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "numero"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "numero"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def _format_tempo_casa(days):
    """Helper para formatar dias sempre em anos (2 casas decimais)."""
    if pd.isna(days) or days < 0:
        return "N/A"
    anos = float(days) / 365.0
    return f"{anos:.2f}".replace(".", ",") + " anos"

def historical_tempo_medio_casa(months=12):
    """
    Histórico mensal do tempo médio de casa (em dias) dos colaboradores ativos.
    A formatação em 'tempo' é feita apenas para o raw_data. Métricas usam dias.
    """
    df_p = carregar_pessoas()
    if df_p is None or df_p.empty:
        return {"raw_data": OrderedDict()}

    df_p["DataInicio"] = pd.to_datetime(df_p.get("DataInicio"), errors="coerce")
    df_p["DataFinal"]  = pd.to_datetime(df_p.get("DataFinal"),  errors="coerce")
    df_p = df_p.dropna(subset=["DataInicio"])

    end_date   = pd.Timestamp.today().normalize()
    start_date = (end_date - relativedelta(months=months)).replace(day=1)
    dates = pd.date_range(start=start_date, end=end_date, freq="ME") # Month End

    series_vals = OrderedDict()
    print(f"[hist.historical_tempo_medio_casa] Calculando de {start_date.date()} a {end_date.date()}")

    for month_end_dt in dates:
        print(f"Processing month ending: {month_end_dt.date()}")
        df_empregados_ate_mes = df_p[df_p["DataInicio"] <= month_end_dt].copy()

        if df_empregados_ate_mes.empty:
            print("  No employees started by this month.")
            series_vals[month_end_dt.replace(day=1)] = 0.0
            continue

        # Determina o "fim" da contagem para cada um:
        # 1. Default é o fim do mês que estamos analisando.
        df_empregados_ate_mes["FimContagem"] = month_end_dt

        # 2. Identifica quem saiu ANTES do fim do mês
        mask_saiu_antes = pd.notna(df_empregados_ate_mes["DataFinal"]) & (df_empregados_ate_mes["DataFinal"] < month_end_dt)

        # 3. Para esses que saíram antes, o FimContagem é a DataFinal
        df_empregados_ate_mes.loc[mask_saiu_antes, "FimContagem"] = df_empregados_ate_mes.loc[mask_saiu_antes, "DataFinal"]

        # Garante que FimContagem seja datetime antes de subtrair
        df_empregados_ate_mes["FimContagem"] = pd.to_datetime(df_empregados_ate_mes["FimContagem"], errors='coerce')
        # Garante que DataInicio seja datetime
        df_empregados_ate_mes["DataInicio"] = pd.to_datetime(df_empregados_ate_mes["DataInicio"], errors='coerce')

        # Calcula TempoDias
        df_empregados_ate_mes["TempoDias"] = (df_empregados_ate_mes["FimContagem"] - df_empregados_ate_mes["DataInicio"]).dt.days

        # Remove NaT e dias negativos
        df_empregados_ate_mes = df_empregados_ate_mes.dropna(subset=["TempoDias"])
        df_empregados_ate_mes = df_empregados_ate_mes[df_empregados_ate_mes["TempoDias"] >= 0]

        if df_empregados_ate_mes.empty:
             print("  No valid tenure calculated for this month.")
             media_dias = 0.0
        else:
            media_dias = df_empregados_ate_mes["TempoDias"].mean()
            print(f"  Avg tenure (days): {media_dias:.2f} for {len(df_empregados_ate_mes)} employees")

        series_vals[month_end_dt.replace(day=1)] = media_dias if pd.notna(media_dias) else 0.0

    serie = pd.Series(series_vals).sort_index()
    if serie.empty: return {"raw_data": OrderedDict()}

    # Métricas calculadas sobre a média de dias
    ma = moving_average(serie, 3) if len(serie) >= 3 else pd.Series([0]*len(serie), index=serie.index)
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    # Para last_q/last_s, formatamos a média dos últimos dias como 'tempo'
    last_q_val = serie.tail(3).mean() if len(serie) >= 3 else np.nan
    last_s_val = serie.tail(6).mean() if len(serie) >= 6 else np.nan
    last_q_str = _format_tempo_casa(last_q_val)
    last_s_str = _format_tempo_casa(last_s_val)


    # Raw data DEVE conter o valor NUMÉRICO (média de dias)
    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), float(v) if pd.notna(v) else 0.0) # Garante float
        for d, v in serie.items()
    )
    ma_last_val = ma.iloc[-1] if not ma.empty else 0.0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "numero"), # Média móvel de dias
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),  # Crescimento da média de dias
        "std_deviation":  formatar_valor_utils(std, "numero"),        # Desvio padrão de dias
        "last_quarter":   last_q_str, # Média formatada com _format_tempo_casa
        "last_semester":  last_s_str, # Média formatada com _format_tempo_casa
        "raw_data":       raw_data   # Valores mensais NUMÉRICOS (dias)
    }


def historical_receita_por_colaborador(months=12):
    """
    Histórico mensal da Receita por Colaborador (Faturamento / Nº Colaboradores).
    """
    df_eshows = carregar_base_eshows()
    df_p = carregar_pessoas()
    if df_eshows is None or df_eshows.empty or df_p is None or df_p.empty:
        return {"raw_data": OrderedDict()}

    # Prepara Faturamento
    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show'])
    for col in COLUNAS_FATURAMENTO:
        if col not in df_eshows.columns: df_eshows[col] = 0
        else: df_eshows[col] = pd.to_numeric(df_eshows[col], errors='coerce').fillna(0)
    df_eshows['Faturamento'] = df_eshows[COLUNAS_FATURAMENTO].sum(axis=1)
    df_fat_monthly = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME'))['Faturamento'].sum()

    # Prepara Colaboradores
    df_p["DataInicio"] = pd.to_datetime(df_p.get("DataInicio"), errors="coerce")
    df_p["DataFinal"]  = pd.to_datetime(df_p.get("DataFinal"),  errors="coerce")
    df_p = df_p.dropna(subset=["DataInicio"])

    # Calcula RPC mensal
    series_vals = OrderedDict()
    dates = pd.date_range(end=df_fat_monthly.index.max(), periods=months, freq='ME')

    for month_end in dates:
        # Faturamento do mês
        fat_mes = df_fat_monthly.get(month_end, 0.0)

        # Colaboradores ativos no fim do mês
        ativos = (
            (df_p["DataInicio"] <= month_end) &
            (df_p["DataFinal"].isna() | (df_p["DataFinal"] > month_end))
        )
        n_colab = int(ativos.sum())

        rpc_mes = (fat_mes / n_colab) if n_colab > 0 else 0.0
        series_vals[month_end.replace(day=1)] = rpc_mes

    serie = pd.Series(series_vals).sort_index()
    if serie.empty: return {"raw_data": OrderedDict()}

    ma = moving_average(serie, 3) if len(serie) >= 3 else pd.Series([0]*len(serie), index=serie.index)
    gr = growth_rate(serie) if len(serie) >= 2 else 0.0
    std = std_deviation(serie) if len(serie) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie, fmt="monetario")

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "monetario"))
        for d, v in serie.items()
    )
    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    return {
        "start_date":     serie.index.min().strftime("%Y-%m-%d") if not serie.empty else None,
        "end_date":       serie.index.max().strftime("%Y-%m-%d") if not serie.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "monetario"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_custo_medio_colaborador(months=12):
    """
    Histórico mensal do Custo Médio por Colaborador (Custo Equipe / Nº Colaboradores).
    Inclui apenas os últimos 'months' meses com dados válidos de CUSTO e COLABORADORES.
    """
    df_base2 = carregar_base2()
    df_p = carregar_pessoas()
    if df_base2 is None or df_p is None or df_base2.empty or df_p.empty:
        return {"raw_data": OrderedDict()}

    # 1. Prepara Custo Equipe Mensal
    df_base2 = prepare_base2_with_date(df_base2)
    if "Equipe" not in df_base2.columns: df_base2["Equipe"] = 0.0
    df_base2["Equipe"] = pd.to_numeric(df_base2["Equipe"], errors='coerce').fillna(0.0)
    # Agrupa e já filtra meses com custo zero ou negativo, se apropriado.
    # Vamos manter os zeros por enquanto e filtrar depois do cálculo.
    df_cost_monthly = df_base2.groupby(pd.Grouper(key='Data', freq='ME'))['Equipe'].sum().rename("CustoEquipe")

    # 2. Prepara Colaboradores Ativos Mensalmente
    df_p["DataInicio"] = pd.to_datetime(df_p.get("DataInicio"), errors="coerce")
    df_p["DataFinal"]  = pd.to_datetime(df_p.get("DataFinal"),  errors="coerce")
    df_p = df_p.dropna(subset=["DataInicio"])

    # Define um range amplo para garantir a captura de todos os colaboradores
    min_date_p = df_p["DataInicio"].min()
    max_date_cost = df_cost_monthly.index.max() if not df_cost_monthly.empty else pd.Timestamp.today()
    # Usamos o MÁXIMO fim de mês entre custo e hoje para o range
    overall_end_date = max(pd.Timestamp.today() + pd.offsets.MonthEnd(0), max_date_cost)
    if pd.isna(min_date_p):
         return {"raw_data": OrderedDict()} # Não há como calcular sem data de início

    all_months_index = pd.date_range(start=min_date_p, end=overall_end_date, freq='ME')

    colab_counts = {}
    for month_end in all_months_index:
        ativos = (
            (df_p["DataInicio"] <= month_end) &
            (df_p["DataFinal"].isna() | (df_p["DataFinal"] > month_end))
        )
        colab_counts[month_end] = int(ativos.sum())
    df_colab_monthly = pd.Series(colab_counts).rename("NumColab")
    # Filtra meses sem colaboradores, pois o custo médio seria infinito ou zero.
    df_colab_monthly = df_colab_monthly[df_colab_monthly > 0]

    # 3. Merge INTERNO: Mantém apenas meses com dados de CUSTO e COLABORADORES > 0
    df_merged = pd.merge(
        df_colab_monthly,
        df_cost_monthly,
        left_index=True,
        right_index=True,
        how='inner' # Só meses com ambos os dados
    )

    if df_merged.empty:
        return {"raw_data": OrderedDict()} # Retorna vazio se não houver meses com ambos os dados

    # 4. Calcula Custo Médio
    # Como NumColab > 0 e CustoEquipe existe (pode ser 0), o cálculo é seguro.
    df_merged["CustoMedio"] = df_merged["CustoEquipe"] / df_merged["NumColab"]

    # 5. Filtra meses com CustoMedio <= 0 (opcional, mas recomendado)
    df_merged = df_merged[df_merged["CustoMedio"] > 0]
    if df_merged.empty:
        return {"raw_data": OrderedDict()}

    # 6. Cria a série final com os últimos 'months' PONTOS VÁLIDOS
    serie = df_merged["CustoMedio"].sort_index().tail(months)
    if serie.empty:
        return {"raw_data": OrderedDict()}

    # 7. Calcula métricas sobre a série final
    serie_numeric = serie # Já não tem NaN aqui
    ma = moving_average(serie_numeric, 3) if len(serie_numeric) >= 3 else pd.Series()
    gr = growth_rate(serie_numeric) if len(serie_numeric) >= 2 else 0.0
    std = std_deviation(serie_numeric) if len(serie_numeric) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie_numeric, fmt="monetario")

    # 8. Raw data formatado (somente dos meses selecionados)
    raw_data = OrderedDict()
    for d, v in serie.items():
        raw_data[d.replace(day=1).strftime("%Y-%m-%d")] = formatar_valor_utils(v, "monetario")

    ma_last_val = ma.iloc[-1] if not ma.empty else 0.0 # Usa 0.0 se não puder calcular MA
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    start_date_str = serie.index.min().replace(day=1).strftime("%Y-%m-%d") if not serie.empty else None
    end_date_str = serie.index.max().replace(day=1).strftime("%Y-%m-%d") if not serie.empty else None

    return {
        "start_date":     start_date_str,
        "end_date":       end_date_str,
        "moving_average": formatar_valor_utils(ma_last_val, "monetario"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "monetario"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_artistas_ativos(months=12):
    """
    Histórico mensal do número de artistas ativos (únicos 'Nome do Artista').
    """
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty or 'Nome do Artista' not in df_eshows.columns:
        return {"raw_data": OrderedDict()}

    df_eshows['Data do Show'] = pd.to_datetime(df_eshows['Data do Show'], errors='coerce')
    df_eshows = df_eshows.dropna(subset=['Data do Show'])

    df_monthly = df_eshows.groupby(pd.Grouper(key='Data do Show', freq='ME'))['Nome do Artista'].nunique()

    # Filtra para os últimos meses
    series = df_monthly.tail(months)
    if series.empty: return {"raw_data": OrderedDict()}

    # Reindexa para garantir todos os meses no intervalo final e preenche com 0
    full_idx = pd.date_range(start=series.index.min(), end=series.index.max(), freq='ME')
    series = series.reindex(full_idx, fill_value=0)
    series.index = series.index.to_period('M').to_timestamp() # Converte para início do mês

    ma = moving_average(series, 3) if len(series) >= 3 else pd.Series([0]*len(series), index=series.index)
    gr = growth_rate(series) if len(series) >= 2 else 0.0
    std = std_deviation(series) if len(series) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(series, fmt="numero")

    raw_data = OrderedDict(
        (d.strftime("%Y-%m-%d"), formatar_valor_utils(v, "numero"))
        for d, v in series.items()
    )
    ma_last_val = ma.iloc[-1] if not ma.empty else 0
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    return {
        "start_date":     series.index.min().strftime("%Y-%m-%d") if not series.empty else None,
        "end_date":       series.index.max().strftime("%Y-%m-%d") if not series.empty else None,
        "moving_average": formatar_valor_utils(ma_last_val, "numero"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std, "numero"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        "raw_data":       raw_data
    }

def historical_take_rate(months=12):
    """
    Histórico para Take Rate GMV.
    Calcula mensalmente: (Soma Comissão B2B / Soma GMV) * 100.
    Valores formatados em 'percentual'.
    """
    df = carregar_base_eshows()
    if df is None or df.empty:
        return {"raw_data": OrderedDict()}

    # Garantir colunas necessárias e tipos
    if "Data do Show" not in df.columns:
        print("[hist.historical_take_rate] Coluna 'Data do Show' não encontrada.")
        return {"raw_data": OrderedDict()}
    df['Data do Show'] = pd.to_datetime(df['Data do Show'], errors='coerce')
    df = df.dropna(subset=['Data do Show'])

    if "Comissão B2B" not in df.columns:
        df["Comissão B2B"] = 0.0
    else:
        df["Comissão B2B"] = pd.to_numeric(df["Comissão B2B"], errors='coerce').fillna(0.0)

    # Garante coluna Valor Total do Show (GMV)
    if "Valor Total do Show" not in df.columns:
        for alt in ["ValorTotaldoShow", "Valor_Total", "Valor_Total_do_Show"]:
            if alt in df.columns:
                df.rename(columns={alt: "Valor Total do Show"}, inplace=True)
                break
        if "Valor Total do Show" not in df.columns:
            df["Valor Total do Show"] = 0.0
    df["Valor Total do Show"] = pd.to_numeric(df["Valor Total do Show"], errors='coerce').fillna(0.0)

    # Agrupa por mês, somando Comissão e GMV
    df_monthly = df.groupby(pd.Grouper(key='Data do Show', freq='ME')).agg(
        ComissaoB2B_Sum=("Comissão B2B", "sum"),
        GMV_Sum=("Valor Total do Show", "sum")
    )

    # Calcula Take Rate Mensal
    df_monthly["TakeRate"] = df_monthly.apply(
        lambda row: (row["ComissaoB2B_Sum"] / row["GMV_Sum"] * 100) if row["GMV_Sum"] > 0 else 0.0,
        axis=1
    )

    # Filtra últimos meses e cria a série
    serie = df_monthly["TakeRate"].sort_index().tail(months)

    if serie.empty:
        return {"raw_data": OrderedDict()}

    # Calcula métricas
    serie_numeric = serie.dropna()
    ma = moving_average(serie_numeric, 3) if len(serie_numeric) >= 3 else pd.Series()
    gr = growth_rate(serie_numeric) if len(serie_numeric) >= 2 else 0.0
    std = std_deviation(serie_numeric) if len(serie_numeric) >= 1 else 0.0
    last_q, last_s = get_recent_metrics(serie_numeric, fmt="percentual")

    # Formata retorno
    raw_data_numeric = OrderedDict() # Guarda números primeiro
    print(f"\n[hist.historical_take_rate] Gerando raw_data_numeric para {months} meses:") # DEBUG
    for d, v in serie.items():
        raw_data_numeric[d.replace(day=1).strftime("%Y-%m-%d")] = v # Guarda valor numérico percentual
        print(f"  Data: {d.replace(day=1).strftime('%Y-%m-%d')}, Valor NUMÉRICO para raw_data: {v}") # DEBUG

    ma_last_val = ma.iloc[-1] if not ma.empty else np.nan
    gr_pct = (gr * 100.0) if gr is not None else 0.0

    start_date_str = serie.index.min().replace(day=1).strftime("%Y-%m-%d") if not serie.empty else None
    end_date_str = serie.index.max().replace(day=1).strftime("%Y-%m-%d") if not serie.empty else None

    return {
        "start_date":     start_date_str,
        "end_date":       end_date_str,
        "moving_average": formatar_valor_utils(ma_last_val if pd.notna(ma_last_val) else None, "percentual"),
        "growth_rate":    formatar_valor_utils(gr_pct, "percentual"),
        "std_deviation":  formatar_valor_utils(std if pd.notna(std) else None, "percentual"),
        "last_quarter":   last_q,
        "last_semester":  last_s,
        # CORREÇÃO: Aplica a formatação percentual aos valores numéricos guardados
        "raw_data":       {k: formatar_valor_utils(v, "percentual") for k, v in raw_data_numeric.items()}
    }
