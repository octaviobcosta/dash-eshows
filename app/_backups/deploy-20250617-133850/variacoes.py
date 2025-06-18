# =======================
# variacoes.py
# =======================
from __future__ import annotations
from typing import Dict
import pandas as pd
import calendar
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import numpy as np
import gc # <--- ADICIONADO
import logging

logger = logging.getLogger(__name__)

# Imports do seu projeto
from .modulobase import (
    carregar_base_eshows,
    carregar_base2,
    carregar_pessoas,
    carregar_base_inad,
    carregar_ocorrencias,
    carregar_pessoas,
    carregar_npsartistas,
    carregar_custosabertos
)
from .controles import get_kpi_status
from .utils import (
    filtrar_periodo_principal,
    filtrar_periodo_comparacao,
    get_period_start,
    get_period_end,
    calcular_periodo_anterior,
    carregar_kpi_descriptions,
    formatar_valor_utils,
    mes_nome_intervalo,
    faturamento_dos_grupos,
    obter_top5_grupos_ano_anterior,
    calcular_churn,
    calcular_churn_novos_palcos,
    filtrar_novos_palcos_por_periodo,
    parse_valor_formatado
)

# Carrega descrições de KPI
kpi_descriptions = carregar_kpi_descriptions()

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


# ATENÇÃO: Nunca faça leitura direta de Excel neste módulo!
# Sempre use as funções de carregamento do modulobase.py para garantir uso eficiente de memória e cache.
# Utilize carregar_base_eshows(), carregar_base2(), carregar_ocorrencias(), carregar_base_inad(), carregar_pessoas() sempre que precisar dos dados.


# --------------------------------------------------------------------------- #
# Funções auxiliares de data / período                                         #
# --------------------------------------------------------------------------- #
def _last_day(ano: int, mes: int) -> date:
    """Retorna o último dia do mês/ano informado."""
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def _gerar_ranges_trimestre(ano: int, trimestre: int) -> list[tuple[date, date, str]]:
    """
    Gera uma lista de intervalos dentro de um trimestre, na ordem:
      1. Trimestre completo
      2. Bimestre (dois primeiros meses)
      3. Mês restante
    Retorna (data_ini, data_fim, label_periodo).
    """
    m1 = (trimestre - 1) * 3 + 1
    m2, m3 = m1 + 1, m1 + 2

    return [
        # Trimestre completo
        (date(ano, m1, 1), _last_day(ano, m3), f"{calendar.month_abbr[m1]}–{calendar.month_abbr[m3]} {ano}"),
        # Bimestre
        (date(ano, m1, 1), _last_day(ano, m2), f"{calendar.month_abbr[m1]}–{calendar.month_abbr[m2]} {ano}"),
        # Mês
        (date(ano, m2, 1), _last_day(ano, m2), f"{calendar.month_abbr[m2]} {ano}"),
    ]


# --------------------------------------------------------------------------- #
# Função genérica de busca de período válido                                  #
# --------------------------------------------------------------------------- #
def _buscar_periodo_valido_nps(
    df: pd.DataFrame,
    ano: int,
    periodo: str,
    mes: int | None,
    coluna_nps: str,                # ex.: 'NPS Eshows'
    custom_range: tuple | None = None,   #  ←  NOVO
    max_back: int = 8,
) -> tuple[pd.DataFrame, str]:
    """
    Procura o intervalo mais recente com dados completos na coluna NPS (notas 0-10).
    Lógica:
      • Trimestre: trimestre → bimestre → mês → trimestre anterior…
      • YTD      : recua mês a mês até encontrar dados.
      • Mês      : recua mês a mês.
    Retorna (df_filtrado_com_notas_originais, label_periodo). DataFrame vazio se nada encontrado.
    """
    try:
        max_back = int(max_back)
    except (ValueError, TypeError):
        max_back = 8 # Fallback para o valor padrão se a conversão falhar

    tentativas = 0
    label_periodo = "Sem dados"

    if "Data" not in df.columns or not pd.api.types.is_datetime64_any_dtype(df["Data"]):
        if "Data" in df.columns:
            df = df.copy()
            df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
            if df["Data"].isnull().all():
                return pd.DataFrame(), label_periodo
        else:
            return pd.DataFrame(), label_periodo

    while tentativas < max_back:
        df_sel = pd.DataFrame()
        # --------------------------- TRIMESTRES ----------------------------
        if "Trimestre" in periodo:
            tri = int(periodo.split("°")[0])
            for ini, fim, lbl_interno in _gerar_ranges_trimestre(ano, tri):
                mask = (df["Data"] >= pd.Timestamp(ini)) & (df["Data"] <= pd.Timestamp(fim))
                df_temp = df.loc[mask, ["Data", coluna_nps]].copy()
                if not df_temp.empty:
                    serie_notas = pd.to_numeric(df_temp[coluna_nps], errors="coerce").dropna()
                    if not serie_notas.empty:
                        df_temp = df_temp.loc[serie_notas.index]
                        df_sel = df_temp
                        label_periodo = lbl_interno
                        return df_sel, label_periodo
            if tri == 1:
                tri = 4
                ano -= 1
            else:
                tri -=1
            periodo = f"{tri}° Trimestre"

        # --------------------------- Y T D ---------------------------------
        elif periodo.upper() in {"YTD", "Y T D", "ANO CORRENTE"}:
            if mes is None or mes <= 0:
                if ano <= df["Data"].dt.year.min(): break
                ano -=1
                mes = 12
                periodo = "YTD"

            ini = date(ano, 1, 1)
            fim = _last_day(ano, mes)
            mask = (df["Data"] >= pd.Timestamp(ini)) & (df["Data"] <= pd.Timestamp(fim))
            df_temp = df.loc[mask, ["Data", coluna_nps]].copy()
            if not df_temp.empty:
                serie_notas = pd.to_numeric(df_temp[coluna_nps], errors="coerce").dropna()
                if not serie_notas.empty:
                    df_temp = df_temp.loc[serie_notas.index]
                    df_sel = df_temp
                    label_periodo = f"YTD até {calendar.month_abbr[mes]} {ano}"
                    return df_sel, label_periodo
            if mes == 1:
                if ano <= df["Data"].dt.year.min(): break
                ano -= 1
                mes = 12
            else:
                mes -=1
        # --------------------------- MÊS ABERTO ou CUSTOM-RANGE----------------------------
        else: 
            processar_periodo = False
            # custom_range é um parâmetro da função, então está no escopo.
            # No entanto, seu valor só é relevante se periodo == "custom-range".
            if periodo == "custom-range" and custom_range:
                ini, fim = custom_range
                label_periodo = f"{pd.to_datetime(ini):%d/%m/%y} a {pd.to_datetime(fim):%d/%m/%y}"
                processar_periodo = True
            elif periodo == "Ano Completo":
                ini, fim = date(ano, 1, 1), date(ano, 12, 31)
                label_periodo = f"Ano de {ano}"
                processar_periodo = True
            elif periodo == "Mês Aberto" and mes is not None and mes > 0:
                ini, fim = date(ano, mes, 1), _last_day(ano, mes)
                label_periodo = f"{calendar.month_abbr[mes]} {ano}"
                processar_periodo = True
            else: 
                break 

            if processar_periodo:
                mask = (df["Data"] >= pd.Timestamp(ini)) & (df["Data"] <= pd.Timestamp(fim))
                df_temp = df.loc[mask, ["Data", coluna_nps]].copy()
                if not df_temp.empty:
                    serie_notas = pd.to_numeric(df_temp[coluna_nps], errors="coerce").dropna()
                    if not serie_notas.empty:
                        df_temp = df_temp.loc[serie_notas.index]
                        df_sel = df_temp
                        return df_sel, label_periodo
            
            if periodo == "Mês Aberto":
                if mes == 1:
                    if ano <= df["Data"].dt.year.min(): break
                    ano -=1
                    mes = 12
                elif mes is not None: 
                    mes -=1
                else: 
                    break
            elif processar_periodo: # Se custom-range ou Ano Completo e não encontrou, sai.
                break

        tentativas += 1

    return pd.DataFrame(), label_periodo


# ======================================================================
# KPI • Roll 6M Growth
# ======================================================================
def get_roll_6m_growth(ano, periodo, mes, custom_range=None, df_eshows_global=None):
    """
    Rolling 6-Month Growth (R6MG)
    • Janela "atual"  = últimos 6 meses até a data final do período principal.
    • Janela "anterior" = 6 meses imediatamente anteriores à janela atual.
    Retorna dicionário padrão de KPI.
    """
    # ------------------------------------------------------------------ #
    # 1) Carrega base (ou usa a injetada)                                #
    # ------------------------------------------------------------------ #
    df_eshows = (
        df_eshows_global.copy()
        if df_eshows_global is not None
        else carregar_base_eshows().copy()
    )
    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    if df_eshows is None or df_eshows.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # ------------------------------------------------------------------ #
    # 2) Filtra período principal e obtém data final                     #
    # ------------------------------------------------------------------ #
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    label_periodo_base = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo_base,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    if "Data do Show" in df_principal.columns:
        end_date = pd.to_datetime(df_principal["Data do Show"], errors="coerce").max()
    else:
        df_principal["Ano"] = pd.to_numeric(df_principal["Ano"], errors="coerce")
        df_principal["Mês"] = pd.to_numeric(df_principal["Mês"], errors="coerce")
        df_principal["DataFake"] = pd.to_datetime(
            df_principal["Ano"].astype(str) + "-" + df_principal["Mês"].astype(str) + "-01",
            errors="coerce"
        )
        end_date = df_principal["DataFake"].max()

    if pd.isna(end_date):
        return {
            "periodo": label_periodo_base,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }
    end_date = end_date.normalize()

    # ------------------------------------------------------------------ #
    # 3) Define janelas de 6 meses                                       #
    # ------------------------------------------------------------------ #
    start_date_6m = end_date - relativedelta(months=6) + pd.DateOffset(days=1)
    end_date_6m_pass = start_date_6m - pd.DateOffset(days=1)
    start_date_6m_pass = end_date_6m_pass - relativedelta(months=6) + pd.DateOffset(days=1)

    # Helper para "Março/25"
    meses_pt = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }
    def fmt_mes_ano(dt):
        return f"{meses_pt[dt.month]}/{str(dt.year)[2:]}"

    janela_atual_txt    = f"{fmt_mes_ano(start_date_6m)} a {fmt_mes_ano(end_date)}"
    janela_anterior_txt = f"{fmt_mes_ano(start_date_6m_pass)} a {fmt_mes_ano(end_date_6m_pass)}"

    # ------------------------------------------------------------------ #
    # 4) Filtra as duas janelas                                          #
    # ------------------------------------------------------------------ #
    def filtrar_intervalo(df, d_ini, d_fim):
        df_ = df.copy()
        if "Data do Show" in df_.columns:
            df_["Data do Show"] = pd.to_datetime(df_["Data do Show"], errors="coerce")
            return df_[(df_["Data do Show"] >= d_ini) & (df_["Data do Show"] <= d_fim)]
        else:
            df_["Ano"] = pd.to_numeric(df_["Ano"], errors="coerce")
            df_["Mês"] = pd.to_numeric(df_["Mês"], errors="coerce")
            df_["DataFake"] = pd.to_datetime(
                df_["Ano"].astype(str) + "-" + df_["Mês"].astype(str) + "-01",
                errors="coerce"
            )
            return df_[(df_["DataFake"] >= d_ini) & (df_["DataFake"] <= d_fim)]

    df_6m_atual  = filtrar_intervalo(df_eshows, start_date_6m, end_date)
    df_6m_pass   = filtrar_intervalo(df_eshows, start_date_6m_pass, end_date_6m_pass)

    # ------------------------------------------------------------------ #
    # 5) Soma faturamento em cada janela                                 #
    # ------------------------------------------------------------------ #
    for c in COLUNAS_FATURAMENTO:
        df_6m_atual[c] = pd.to_numeric(df_6m_atual.get(c, 0), errors="coerce").fillna(0)
        df_6m_pass[c]  = pd.to_numeric(df_6m_pass.get(c, 0),  errors="coerce").fillna(0)

    rec_6m_atual   = df_6m_atual[COLUNAS_FATURAMENTO].sum().sum()
    rec_6m_passado = df_6m_pass[COLUNAS_FATURAMENTO].sum().sum()

    # ------------------------------------------------------------------ #
    # 6) Growth                                                         #
    # ------------------------------------------------------------------ #
    growth_pct = (
        0.0 if rec_6m_passado == 0
        else ((rec_6m_atual - rec_6m_passado) / abs(rec_6m_passado)) * 100.0
    )

    # ------------------------------------------------------------------ #
    # 7) Retorno                                                        #
    # ------------------------------------------------------------------ #
    return {
        "periodo": label_periodo_base,          # ex.: "Janeiro/25 até Março/25"
        "resultado": f"{growth_pct:.2f}%",
        "status": "controle",
        "variables_values": {
            "Janela atual": janela_atual_txt,
            "Janela anterior": janela_anterior_txt,
            "Receita 6m Atuais": rec_6m_atual,
            "Receita 6m Passados": rec_6m_passado,
        },
    }

# ----------------------------------------------------------------------
# HELPER • get_cmgr_variables  ➜  calcula CMGR e devolve variáveis
# ----------------------------------------------------------------------
def get_cmgr_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None, # Adicionado custom_range
    df_eshows_global=None
) -> dict:
    """
    Calcula o CMGR (Compound Monthly Growth Rate) do faturamento.

    CMGR = ((Receita_final / Receita_inicial) ** (1 / n)) - 1
    Onde *n* é o número de intervalos mensais entre os dois pontos —
    isto é, quantidade de meses distintos menos 1.
    """
    # 1) Carrega base ----------------------------------------------------
    df_eshows = (
        df_eshows_global.copy()
        if df_eshows_global is not None
        else carregar_base_eshows().copy()
    )
    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    if df_eshows is None or df_eshows.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {"n": 0},
        }

    # 2) Filtra período principal ---------------------------------------
    df_principal   = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range) # Passa custom_range
    label_periodo  = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {"n": 0},
        }

    # 3) Padroniza colunas de faturamento -------------------------------
    alt_map = [
        ("Comissao B2B", "Comissão B2B"),
        ("Comissao B2C", "Comissão B2C"),
        ("Antecipacao de Caches", "Antecipação de Cachês"),
    ]
    for alt, orig in alt_map:
        if alt in df_principal.columns and orig not in df_principal.columns:
            df_principal.rename(columns={alt: orig}, inplace=True)

    for col in COLUNAS_FATURAMENTO:
        df_principal[col] = pd.to_numeric(
            df_principal.get(col, 0), errors="coerce"
        ).fillna(0)

    df_principal["Faturamento"] = df_principal[COLUNAS_FATURAMENTO].sum(axis=1)

    # 4) Garante colunas Ano / Mês --------------------------------------
    if "Ano" not in df_principal.columns:
        df_principal["Ano"] = pd.to_datetime(df_principal["Data"], errors="coerce").dt.year
    if "Mês" not in df_principal.columns:
        df_principal["Mês"] = pd.to_datetime(df_principal["Data"], errors="coerce").dt.month

    # 5) Agrupa por Ano/Mês ---------------------------------------------
    df_agrup = (
        df_principal.groupby(["Ano", "Mês"], as_index=False)["Faturamento"]
        .sum()
        .sort_values(["Ano", "Mês"])
    )
    if df_agrup.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {"n": 0},
        }

    # 6) Nomes PT dos meses (para exibir depois) -------------------------
    meses_pt = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }

    # 7) Caso especial: só Janeiro disponível → comparar Dez x Jan -------
    if len(df_agrup) == 1 and df_agrup.iloc[0]["Mês"] == 1:
        row_jan   = df_agrup.iloc[0]
        df_dez_ant = df_eshows[
            (df_eshows["Ano"] == ano - 1) & (df_eshows["Mês"] == 12)
        ].copy()

        for col in COLUNAS_FATURAMENTO:
            df_dez_ant[col] = pd.to_numeric(
                df_dez_ant.get(col, 0), errors="coerce"
            ).fillna(0)

        fat_dez = df_dez_ant[COLUNAS_FATURAMENTO].sum().sum() if not df_dez_ant.empty else 0
        fat_jan = row_jan["Faturamento"]
        n       = 1  # um único intervalo: Dez → Jan

        cmgr_pct = (
            ((fat_jan / fat_dez) ** (1 / n) - 1) * 100
            if fat_dez > 0 and fat_jan > 0
            else 0.0
        )

        status = (
            "ruim"     if cmgr_pct < 0
            else "bom" if cmgr_pct >= 3
            else "controle"
        )
        return {
            "periodo": label_periodo,
            "resultado": f"{cmgr_pct:.2f}%",
            "status": status,
            "variables_values": {
                "Receita inicial": float(fat_dez),
                "Receita final":   float(fat_jan),
                "Periodo inicial": f"Dezembro/{str(ano-1)[2:]}",
                "Periodo final":   f"Janeiro/{str(ano)[2:]}",
                "n": n,
            },
        }

    # 8) Cálculo geral do CMGR ------------------------------------------
    fat_inicial = df_agrup.iloc[0]["Faturamento"]
    fat_final   = df_agrup.iloc[-1]["Faturamento"]
    n           = len(df_agrup) - 1  # agora CORRETO: intervalos mensais

    if n <= 0 or fat_inicial <= 0 or fat_final <= 0:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {
                "Receita inicial": float(fat_inicial),
                "Receita final":   float(fat_final),
                "Periodo inicial": "",
                "Periodo final":   "",
                "n": n,
            },
        }

    cmgr_pct = ((fat_final / fat_inicial) ** (1 / n) - 1) * 100
    status   = (
        "ruim"     if cmgr_pct < 0
        else "bom" if cmgr_pct >= 3
        else "controle"
    )

    mes_ini, ano_ini = int(df_agrup.iloc[0]["Mês"]), int(df_agrup.iloc[0]["Ano"])
    mes_fim, ano_fim = int(df_agrup.iloc[-1]["Mês"]), int(df_agrup.iloc[-1]["Ano"])

    periodo_ini_txt = f"{meses_pt[mes_ini]}/{str(ano_ini)[2:]}"
    periodo_fim_txt = f"{meses_pt[mes_fim]}/{str(ano_fim)[2:]}"

    return {
        "periodo": label_periodo,
        "resultado": f"{cmgr_pct:.2f}%",
        "status": status,
        "variables_values": {
            "Receita inicial": float(fat_inicial),
            "Receita final":   float(fat_final),
            "Periodo inicial": periodo_ini_txt,
            "Periodo final":   periodo_fim_txt,
            "n": n,
        },
    }

# ===========================================================================
# KPI: Lucratividade (["eshows", "base2"])
# ===========================================================================
def get_lucratividade_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
    df_base2_global=None,
) -> dict:
    """
    KPI: Lucratividade = ((Receita – Custos) / Receita) × 100

    • Receita: soma das colunas definidas em COLUNAS_FATURAMENTO na Base Eshows  
    • Custos: coluna "Custos" na Base 2  
    """
    # --------------------------------------------------------------- #
    # 1) Trata custom_range e carrega as bases
    # --------------------------------------------------------------- #
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    df_eshows = (df_eshows_global.copy()
                 if df_eshows_global is not None
                 else carregar_base_eshows().copy())

    df_b2_ = (df_base2_global.copy()
              if df_base2_global is not None
              else carregar_base2().copy())

    # remove colunas duplicadas
    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]
    if df_b2_ is not None:
        df_b2_ = df_b2_.loc[:, ~df_b2_.columns.duplicated()]

    # --------------------------------------------------------------- #
    # 2) Filtra período principal e verifica bases
    # --------------------------------------------------------------- #
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if (
        df_eshows is None or df_eshows.empty or
        df_b2_    is None or df_b2_.empty or
        df_principal.empty
    ):
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {
                "Lucro Líquido": 0,
                "Faturamento Total": 0,
                "Custos Total": 0,
            },
        }

    # --------------------------------------------------------------- #
    # 3) Ajusta colunas de faturamento e calcula Receita
    # --------------------------------------------------------------- #
    alt_map = [
        ("Comissao B2B", "Comissão B2B"),
        ("Comissao B2C", "Comissão B2C"),
        ("Antecipacao de Caches", "Antecipação de Cachês"),
    ]
    for alt, orig in alt_map:
        if alt in df_principal.columns and orig not in df_principal.columns:
            df_principal.rename(columns={alt: orig}, inplace=True)

    for col in COLUNAS_FATURAMENTO:
        if col not in df_principal.columns:
            df_principal[col] = 0
        else:
            df_principal[col] = pd.to_numeric(df_principal[col], errors="coerce").fillna(0)

    df_principal["Receita"] = df_principal[COLUNAS_FATURAMENTO].sum(axis=1)

    # garante Ano / Mês
    if "Ano" not in df_principal.columns:
        df_principal["Ano"] = pd.to_datetime(df_principal["Data"], errors="coerce").dt.year
    if "Mês" not in df_principal.columns:
        df_principal["Mês"] = pd.to_datetime(df_principal["Data"], errors="coerce").dt.month

    g_rec = df_principal.groupby(["Ano", "Mês"], as_index=False)["Receita"].sum()

    # --------------------------------------------------------------- #
    # 4) Ajusta Base 2 → Custos
    # --------------------------------------------------------------- #
    df_b2_princ = filtrar_periodo_principal(df_b2_, ano, periodo, mes, custom_range)

    if "Custos" not in df_b2_princ.columns:
        df_b2_princ["Custos"] = 0
    else:
        df_b2_princ["Custos"] = pd.to_numeric(df_b2_princ["Custos"], errors="coerce").fillna(0)

    if "Ano" not in df_b2_princ.columns:
        df_b2_princ["Ano"] = pd.to_datetime(df_b2_princ["Data"], errors="coerce").dt.year
    if "Mês" not in df_b2_princ.columns:
        df_b2_princ["Mês"] = pd.to_datetime(df_b2_princ["Data"], errors="coerce").dt.month

    g_cst = df_b2_princ.groupby(["Ano", "Mês"], as_index=False)["Custos"].sum()

    # --------------------------------------------------------------- #
    # 5) Une Receita × Custos
    # --------------------------------------------------------------- #
    df_merge = (
        pd.merge(g_rec, g_cst, on=["Ano", "Mês"], how="outer")
          .sort_values(["Ano", "Mês"])
    )

    # --------------------------------------------------------------- #
    # 6) Lógica para "Mês Aberto"
    # --------------------------------------------------------------- #
    if periodo == "Mês Aberto":
        row = df_merge[(df_merge["Ano"] == ano) & (df_merge["Mês"] == mes)]
        if row.empty:
            return {
                "periodo": label_periodo,
                "resultado": "0.00%",
                "status": "controle",
                "variables_values": {
                    "Lucro Líquido": 0,
                    "Faturamento Total": 0,
                    "Custos Total": 0,
                },
            }

        receita = row.iloc[0]["Receita"]
        custos  = row.iloc[0]["Custos"]

        if pd.isna(receita) or receita <= 0:
            perc = 0.0
        else:
            perc = ((receita - custos) / receita) * 100

        st, icon = get_kpi_status("Lucratividade", perc, kpi_descriptions)

        return {
            "periodo": label_periodo,
            "resultado": f"{perc:.2f}%",
            "status": st,
            "icon": icon,
            "variables_values": {
                "Lucro Líquido": float(receita - custos),
                "Faturamento Total": float(receita),
                "Custos Total": float(custos),
            },
        }

    # --------------------------------------------------------------- #
    # 7) Demais períodos (acumulado ou custom)
    # --------------------------------------------------------------- #
    df_clean = df_merge.fillna(0)
    total_rec = df_clean["Receita"].sum()
    total_cst = df_clean["Custos"].sum()

    if total_rec <= 0:
        perc = 0.0
    else:
        perc = ((total_rec - total_cst) / total_rec) * 100

    st, icon = get_kpi_status("Lucratividade", perc, kpi_descriptions)

    return {
        "periodo": label_periodo,
        "resultado": f"{perc:.2f}%",
        "status": st,
        "icon": icon,
        "variables_values": {
            "Lucro Líquido": float(total_rec - total_cst),
            "Faturamento Total": float(total_rec),
            "Custos Total": float(total_cst),
        },
    }

# ===========================================================================
# KPI: Net Revenue Retention (NRR) (["eshows"])
# ===========================================================================
def get_nrr_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
) -> dict:
    """
    Calcula o Net Revenue Retention (NRR) dos 5 maiores grupos do ano anterior.

    • Fórmula: NRR = ((Receita_atual – Receita_anterior) / Receita_anterior) × 100
    • O período "atual" segue os filtros (ano/periodo/mes ou custom_range).
    • O período "anterior" é o mesmo intervalo do ano anterior.
    """
    # ------------------------------------------------------------------ #
    # 1) Valida custom_range e carrega base                              #
    # ------------------------------------------------------------------ #
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    df_eshows = (
        df_eshows_global.copy()
        if df_eshows_global is not None
        else carregar_base_eshows().copy()
    )
    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    if df_eshows is None or df_eshows.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 2) Filtra período atual e obtém top-5 grupos do ano anterior        #
    # ------------------------------------------------------------------ #
    df_atual = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_atual, periodo)
    if custom_range and not df_atual.empty:
        label_periodo = f"{custom_range[0]:%d/%m/%y} – {custom_range[1]:%d/%m/%y}"

    top5 = obter_top5_grupos_ano_anterior(df_eshows, ano)
    if not top5:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 3) Cria período homólogo do ano anterior                           #
    # ------------------------------------------------------------------ #
    ano_ant = ano - 1
    if custom_range is not None:
        d_ini, d_fim = custom_range
        custom_range_ant = (
            (d_ini - pd.DateOffset(years=1)),
            (d_fim - pd.DateOffset(years=1)),
        )
    else:
        custom_range_ant = None

    df_ant = filtrar_periodo_principal(df_eshows, ano_ant, periodo, mes, custom_range_ant)

    # ------------------------------------------------------------------ #
    # 4) Receita agregada dos grupos                                     #
    # ------------------------------------------------------------------ #
    R_ant   = faturamento_dos_grupos(df_ant,   top5) if not df_ant.empty   else 0
    R_atual = faturamento_dos_grupos(df_atual, top5) if not df_atual.empty else 0

    if R_ant <= 0:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 5) Calcula NRR, variação absoluta e status                         #
    # ------------------------------------------------------------------ #
    nrr_pct = ((R_atual - R_ant) / R_ant) * 100.0
    delta   = R_atual - R_ant

    if nrr_pct < 0:
        status = "ruim"
    elif nrr_pct < 10:
        status = "controle"
    elif nrr_pct < 20:
        status = "bom"
    else:
        status = "excelente"

    key_ant   = f"Receita {ano_ant}"
    key_atual = f"Receita {ano}"

    # ------------------------------------------------------------------ #
    # 6) Retorno final                                                   #
    # ------------------------------------------------------------------ #
    return {
        "periodo": label_periodo,
        "resultado": f"{nrr_pct:.2f}%",
        "status": status,
        "variables_values": {
            key_ant:             float(R_ant),
            key_atual:           float(R_atual),
            "Variação Absoluta": float(delta),
        },
    }

# ======================================================================
# KPI: EBITDA  (["eshows","base2"])
# ======================================================================
def get_ebitda_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None, # Adicionado custom_range
    df_eshows_global=None,
    df_base2_global=None,
) -> dict:
    """
    KPI – EBITDA
        % EBITDA = ((ReceitaEBTIDA – CustosEBTIDA) / ReceitaEBTIDA) × 100

    • ReceitaEBTIDA  = soma(COLUNAS_FATURAMENTO) - "Notas Fiscais"
    • CustosEBTIDA   = Custos – Imposto   (Base 2)
    """
    # ------------------------------------------------------------------ #
    # 1) Carrega as bases e remove colunas duplicadas
    # ------------------------------------------------------------------ #
    df_eshows = (df_eshows_global.copy()
                 if df_eshows_global is not None
                 else carregar_base_eshows().copy())

    df_b2_ = (df_base2_global.copy()
              if df_base2_global is not None
              else carregar_base2().copy())

    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]
    if df_b2_ is not None:
        df_b2_ = df_b2_.loc[:, ~df_b2_.columns.duplicated()]

    # ------------------------------------------------------------------ #
    # 2) Filtra período e verifica dados
    # ------------------------------------------------------------------ #
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range) # Passa custom_range
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if (
        df_eshows is None or df_eshows.empty or
        df_b2_    is None or df_b2_.empty or
        df_principal.empty
    ):
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {
                "EBTIDA Valor": 0,
                "Receita EBTIDA": 0,
                "Custos EBTIDA": 0,
            },
        }

    # ------------------------------------------------------------------ #
    # 3) Calcula ReceitaEBTIDA
    # ------------------------------------------------------------------ #
    alt_map = [
        ("Comissao B2B", "Comissão B2B"),
        ("Comissao B2C", "Comissão B2C"),
        ("Antecipacao de Caches", "Antecipação de Cachês"),
    ]
    for alt, orig in alt_map:
        if alt in df_principal.columns and orig not in df_principal.columns:
            df_principal.rename(columns={alt: orig}, inplace=True)

    for col in COLUNAS_FATURAMENTO:
        if col not in df_principal.columns:
            df_principal[col] = 0
        else:
            df_principal[col] = pd.to_numeric(df_principal[col], errors="coerce").fillna(0)

    df_principal["FatTotal"] = df_principal[COLUNAS_FATURAMENTO].sum(axis=1)

    # garante coluna "Notas Fiscais"
    if "Notas Fiscais" not in df_principal.columns:
        for alt in ("NotasFiscais", "Notas_Fiscais"):
            if alt in df_principal.columns:
                df_principal.rename(columns={alt: "Notas Fiscais"}, inplace=True)
                break
        if "Notas Fiscais" not in df_principal.columns:
            df_principal["Notas Fiscais"] = 0

    df_principal["NotasF"] = pd.to_numeric(
        df_principal["Notas Fiscais"], errors="coerce"
    ).fillna(0)

    df_principal["ReceitaEBTIDA"] = df_principal["FatTotal"] - df_principal["NotasF"]

    # Ano / Mês
    if "Ano" not in df_principal.columns:
        df_principal["Ano"] = pd.to_datetime(df_principal["Data"], errors="coerce").dt.year
    if "Mês" not in df_principal.columns:
        df_principal["Mês"] = pd.to_datetime(df_principal["Data"], errors="coerce").dt.month

    g_ebt_rec = df_principal.groupby(["Ano", "Mês"], as_index=False)["ReceitaEBTIDA"].sum()

    # ------------------------------------------------------------------ #
    # 4) Calcula CustosEBTIDA
    # ------------------------------------------------------------------ #
    df_b2_princ = filtrar_periodo_principal(df_b2_, ano, periodo, mes, custom_range) # Passa custom_range

    for col in ("Custos", "Imposto"):
        if col not in df_b2_princ.columns:
            df_b2_princ[col] = 0
        else:
            df_b2_princ[col] = pd.to_numeric(df_b2_princ[col], errors="coerce").fillna(0)

    df_b2_princ["CustosEBTIDA"] = df_b2_princ["Custos"] - df_b2_princ["Imposto"]

    # ----------------- NOVOS TOTAIS ----------------------------
    total_notas_fiscais = float(df_principal["NotasF"].sum())
    total_imposto = float(df_b2_princ["Imposto"].sum())
    # -----------------------------------------------------------

    if "Ano" not in df_b2_princ.columns:
        df_b2_princ["Ano"] = pd.to_datetime(df_b2_princ["Data"], errors="coerce").dt.year
    if "Mês" not in df_b2_princ.columns:
        df_b2_princ["Mês"] = pd.to_datetime(df_b2_princ["Data"], errors="coerce").dt.month

    g_ebt_cst = df_b2_princ.groupby(["Ano", "Mês"], as_index=False)["CustosEBTIDA"].sum()

    # ------------------------------------------------------------------ #
    # 5) Une dados e calcula EBITDA
    # ------------------------------------------------------------------ #
    df_merge = (
        pd.merge(g_ebt_rec, g_ebt_cst, on=["Ano", "Mês"], how="outer")
          .sort_values(["Ano", "Mês"])
    )

    # -------------- Mês Aberto -------------- #
    if periodo == "Mês Aberto":
        row = df_merge[(df_merge["Ano"] == ano) & (df_merge["Mês"] == mes)]
        if row.empty:
            return {
                "periodo": label_periodo,
                "resultado": "0.00%",
                "status": "controle",
                "variables_values": {
                    "EBTIDA Valor": 0,
                    "Receita EBTIDA": 0,
                    "Custos EBTIDA": 0,
                },
            }

        rec_ebt = row.iloc[0]["ReceitaEBTIDA"]
        cst_ebt = row.iloc[0]["CustosEBTIDA"]

        if pd.isna(rec_ebt) or rec_ebt <= 0:
            perc = 0.0
        else:
            perc = ((rec_ebt - cst_ebt) / rec_ebt) * 100

        st, icon = get_kpi_status("EBITDA", perc, kpi_descriptions)

        return {
            "periodo": label_periodo,
            "resultado": f"{perc:.2f}%",
            "status": st,
            "icon": icon,
            "variables_values": {
                "EBTIDA Valor": float(rec_ebt - cst_ebt),
                "Receita EBTIDA": float(rec_ebt),
                "Custos EBTIDA": float(cst_ebt),
                "Notas Fiscais": total_notas_fiscais,
                "Imposto": total_imposto,
            },
        }

    # -------------- Período acumulado -------------- #
    df_clean = df_merge.fillna(0)
    total_rec_ebt = df_clean["ReceitaEBTIDA"].sum()
    total_cst_ebt = df_clean["CustosEBTIDA"].sum()

    if total_rec_ebt <= 0:
        perc = 0.0
    else:
        perc = ((total_rec_ebt - total_cst_ebt) / total_rec_ebt) * 100

    st, icon = get_kpi_status("EBITDA", perc, kpi_descriptions)

    return {
        "periodo": label_periodo,
        "resultado": f"{perc:.2f}%",
        "status": st,
        "icon": icon,
        "variables_values": {
            "EBTIDA Valor": float(total_rec_ebt - total_cst_ebt),
            "Receita EBTIDA": float(total_rec_ebt),
            "Custos EBTIDA": float(total_cst_ebt),
            "Notas Fiscais": total_notas_fiscais,
            "Imposto": total_imposto,
        },
    }

# ======================================================================
# KPI: Receita por Colaborador (RPC) (["eshows","pessoas"])
# ======================================================================
def get_rpc_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
    df_pessoas_global=None,
) -> dict:
    """
    KPI – Receita por Colaborador (RPC)
    Fórmula (perspectiva mensal):
        RPC = (Faturamento total / média de funcionários no período) / nº de meses
    """
    # 1) Valida custom_range e carrega bases necessárias
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None
    df_eshows = df_eshows_global.copy() if df_eshows_global is not None else carregar_base_eshows().copy()
    df_pessoas = df_pessoas_global.copy() if df_pessoas_global is not None else carregar_pessoas().copy()
    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]
    if df_pessoas is not None:
        df_pessoas = df_pessoas.loc[:, ~df_pessoas.columns.duplicated()]
    # 2) Filtra período principal de eShows e determina rótulo do período
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_principal, periodo)
    if df_principal.empty or df_pessoas is None or df_pessoas.empty:
        return {
            "periodo": label_periodo,
            "resultado": "R$0",
            "status": "controle",
            "variables_values": {},
        }
    # 3) Normaliza colunas de faturamento e calcula faturamento total no período
    alt_map = [
        ("Comissao B2B", "Comissão B2B"),
        ("Comissao B2C", "Comissão B2C"),
        ("Antecipacao de Caches", "Antecipação de Cachês"),
    ]
    for alt, orig in alt_map:
        if alt in df_principal.columns and orig not in df_principal.columns:
            df_principal.rename(columns={alt: orig}, inplace=True)
    for col in COLUNAS_FATURAMENTO:
        if col not in df_principal.columns:
            df_principal[col] = 0
        else:
            df_principal[col] = pd.to_numeric(df_principal[col], errors="coerce").fillna(0)
    df_principal["Faturamento"] = df_principal[COLUNAS_FATURAMENTO].sum(axis=1)
    total_fat = float(df_principal["Faturamento"].sum())
    # 4) Determina intervalo de datas efetivo do período analisado
    if "Data do Show" in df_principal.columns:
        df_principal["DataTemp"] = pd.to_datetime(df_principal["Data do Show"], errors="coerce")
    else:
        df_principal["Ano"] = pd.to_numeric(df_principal["Ano"], errors="coerce")
        df_principal["Mês"] = pd.to_numeric(df_principal["Mês"], errors="coerce")
        df_principal["DataTemp"] = pd.to_datetime(
            df_principal["Ano"].astype(str) + "-" + df_principal["Mês"].astype(str) + "-01",
            errors="coerce",
        )
    dt_min = df_principal["DataTemp"].min()
    dt_max = df_principal["DataTemp"].max()
    if pd.isna(dt_min) or pd.isna(dt_max):
        return {
            "periodo": label_periodo,
            "resultado": "R$0",
            "status": "controle",
            "variables_values": {},
        }
    # 5) Calcula funcionários ativos em cada mês dentro do intervalo
    df_p = df_pessoas.copy()
    if "DataInicio" in df_p.columns:
        df_p["DataInicio"] = pd.to_datetime(df_p["DataInicio"], errors="coerce")
    else:
        df_p["DataInicio"] = pd.NaT
    if "DataSaida" in df_p.columns:
        df_p["DataSaida"] = pd.to_datetime(df_p["DataSaida"], errors="coerce")
    else:
        df_p["DataSaida"] = pd.to_datetime(df_p.get("DataFinal", pd.NaT), errors="coerce")
    total_staff_sum = 0
    count_of_months = 0
    cursor = dt_min.replace(day=1)
    while cursor <= dt_max:
        first_day = cursor
        next_month = first_day + relativedelta(months=1)
        last_day = next_month - pd.DateOffset(days=1)
        cond_active = (df_p["DataInicio"] <= last_day) & (
            df_p["DataSaida"].isna() | (df_p["DataSaida"] >= first_day)
        )
        total_staff_sum += int(cond_active.sum())
        count_of_months += 1
        cursor += relativedelta(months=1)
    if count_of_months < 1:
        return {
            "periodo": label_periodo,
            "resultado": "R$0",
            "status": "controle",
            "variables_values": {},
        }
    media_func = total_staff_sum / count_of_months
    # 6) Calcula RPC (Receita por Colaborador)
    rpc_val = 0.0
    if media_func > 0:
        val_periodo = total_fat / media_func
        rpc_val = val_periodo / count_of_months
    return {
        "periodo": label_periodo,
        "resultado": formatar_valor_utils(rpc_val, "monetario"),
        "status": "controle",
        "variables_values": {
            "Faturamento": total_fat,
            "Média de Funcionários": float(media_func),
            "Meses Contabilizados": count_of_months,
            "Receita Colaborador Mensal": float(rpc_val),
        },
    }

# ------------------------------------------------------------------
# HELPER • get_inadimplencia_variables
# ------------------------------------------------------------------
def get_inadimplencia_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None, # Adicionado custom_range
    df_eshows_global=None,
    df_inad_casas=None,
    df_inad_artistas=None,
) -> dict:
    """
    Inadimplência = (Valor Inadimplente / GMV) × 100
    • GMV  : soma da coluna "Valor Total do Show" (shows no período)
    • Valor Inadimplente : boletos de casas B2B vencidos há ≥ 22 dias,
      com status "vencido" ou "dunning_requested"
    """
    # ------------------------------------------------------------------ #
    # 1) Carrega base Eshows
    # ------------------------------------------------------------------ #
    df_eshows = (df_eshows_global.copy()
                 if df_eshows_global is not None
                 else carregar_base_eshows().copy())

    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    # ------------------------------------------------------------------ #
    # 2) Filtra período principal e captura rótulo
    # ------------------------------------------------------------------ #
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range) # Passa custom_range
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 3) Calcula GMV
    # ------------------------------------------------------------------ #
    df_principal["Valor Total do Show"] = pd.to_numeric(
        df_principal["Valor Total do Show"], errors="coerce"
    ).fillna(0)
    gmv = df_principal["Valor Total do Show"].sum()

    # ------------------------------------------------------------------ #
    # 4) Intervalo de datas do período
    # ------------------------------------------------------------------ #
    df_principal["DataTemp"] = pd.to_datetime(
        df_principal["Data do Show"], errors="coerce"
    )
    dt_min = df_principal["DataTemp"].min()
    dt_max = df_principal["DataTemp"].max()
    if pd.isna(dt_min) or pd.isna(dt_max):
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 5) Carrega boletos (casas + artistas)
    # ------------------------------------------------------------------ #
    if df_inad_casas is None or df_inad_artistas is None:
        df_casas, df_artistas = carregar_base_inad()
    else:
        df_casas, df_artistas = df_inad_casas.copy(), df_inad_artistas

    if df_casas is None or df_casas.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 6) Usa "Data Vencimento" já sanitizada
    # ------------------------------------------------------------------ #
    df_casas["DataVenc"] = pd.to_datetime(
        df_casas["Data Vencimento"], errors="coerce"
    )

    mask_periodo = (df_casas["DataVenc"] >= dt_min) & (df_casas["DataVenc"] <= dt_max)
    df_casas_periodo = df_casas[mask_periodo].copy()

    # ------------------------------------------------------------------ #
    # 7) Seleciona boletos inadimplentes (≥22 dias vencidos)
    # ------------------------------------------------------------------ #
    status_inad = ["vencido", "dunning_requested"]
    cutoff_date = dt_max - timedelta(days=22)

    df_inad = df_casas_periodo[
        (df_casas_periodo["Status"].isin(status_inad)) &
        (df_casas_periodo["DataVenc"] <= cutoff_date)
    ].copy()

    # ------------------------------------------------------------------ #
    # 8) Soma valor inadimplente
    # ------------------------------------------------------------------ #
    df_inad["Valor Real"] = pd.to_numeric(
        df_inad["Valor Real"], errors="coerce"
    ).fillna(0)
    valor_inad = df_inad["Valor Real"].sum()

    # ------------------------------------------------------------------ #
    # 9) Percentual de inadimplência
    # ------------------------------------------------------------------ #
    inad_pct = 0.0 if gmv <= 0 else (valor_inad / gmv) * 100.0

    if inad_pct < 3:
        st = "bom"
    elif inad_pct < 5:
        st = "controle"
    else:
        st = "ruim"

    return {
        "periodo": label_periodo,
        "resultado": formatar_valor_utils(inad_pct, "percentual"),
        "status": st,
        "variables_values": {
            "Valor Inadimplente": float(valor_inad),
            "GMV": float(gmv),
        },
    }

#======================================================================
# KPI • Estabilidade  (usa sempre o último mês com dados completos)
# ======================================================================
def get_estabilidade_variables(ano, periodo, mes,
                               custom_range=None,
                               df_base2_global=None):
    # 1) Carrega base ---------------------------------------------------
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    df = df_base2_global.copy() if df_base2_global is not None else carregar_base2().copy()
    if df is not None:
        df = df.loc[:, ~df.columns.duplicated()]
    if df is None or df.empty:
        return {"periodo": "Sem dados", "resultado": "0.00%", "status": "controle",
                "variables_values": {}}

    # 2) Filtra período -------------------------------------------------
    df_f = filtrar_periodo_principal(df, ano, periodo, mes, custom_range)
    df_f.columns = df_f.columns.str.strip()
    if df_f.empty:
        return {"periodo": mes_nome_intervalo(df_f, periodo), "resultado": "0.00%",
                "status": "controle", "variables_values": {}}

    # 3) Agrega por mês e pega último mês NÃO-nulo ----------------------
    cols = ["Uptime (%)", "MTBF (horas)", "MTTR (Min)", "Taxa de Erros (%)"]
    mensal = (df_f.groupby(["Ano", "Mês"], as_index=False)[cols].mean()
                    .sort_values(["Ano", "Mês"]))
    row_sel = None
    for _, r in mensal[::-1].iterrows():                     # de trás pra frente
        if any(r[c] > 0 for c in cols):
            row_sel = r
            break
    if row_sel is None:                                      # tudo zerado → média
        row_sel = mensal.mean(numeric_only=True)

    avg_up, avg_mb, avg_mt, avg_er = map(float,
                                        [row_sel["Uptime (%)"],
                                         row_sel["MTBF (horas)"],
                                         row_sel["MTTR (Min)"],
                                         row_sel["Taxa de Erros (%)"]])

    # 4) Normaliza + pesos ---------------------------------------------
    MTBF_MAX, MTTR_MAX, ERROS_MAX = 200, 60, 50
    up_norm = avg_up
    mb_norm = min((avg_mb / MTBF_MAX) * 100, 100)
    mt_norm = max(min(((MTTR_MAX - avg_mt) / MTTR_MAX) * 100, 100), 0)
    er_norm = max(min(((ERROS_MAX - avg_er) / ERROS_MAX) * 100, 100), 0)
    W_UP, W_MB, W_MT, W_ER = 0.4, 0.2, 0.2, 0.2
    indice = up_norm*W_UP + mb_norm*W_MB + mt_norm*W_MT + er_norm*W_ER
    status, icon = get_kpi_status("Estabilidade", indice, kpi_descriptions)

    # 5) Formata --------------------------------------------------------
    f2 = lambda v: formatar_valor_utils(v, "numero_2f")
    up_txt, mb_txt, mt_txt, er_txt = map(f2, [avg_up, avg_mb, avg_mt, avg_er])
    indice_txt = formatar_valor_utils(indice, "percentual")
    meses = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho",
             "Agosto","Setembro","Outubro","Novembro","Dezembro"]
    periodo_txt = f"{meses[int(row_sel['Mês'])]}/{str(int(row_sel['Ano']))[2:]}"

    return {
        "periodo": periodo_txt,
        "resultado": indice_txt,
        "status": status,
        "icon": icon,
        "variables_values": {
            "Uptime (%)": avg_up, "MTBF (horas)": avg_mb,
            "MTTR (Min)": avg_mt, "Taxa de Erros (%)": avg_er,
            "Uptime Normalizado": up_norm, "MTBF Normalizado": mb_norm,
            "MTTR Normalizado": mt_norm, "Erros Normalizado": er_norm,
            "Peso Uptime": W_UP, "Peso MTBF": W_MB,
            "Peso MTTR": W_MT, "Peso Erros": W_ER,
        },
    }

# ======================================================================
# KPI: Nível de Serviço  (map: ["eshows", "ocorrencias"])
# ======================================================================
def get_nivel_servico_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None, # Adicionado custom_range
    df_eshows_global=None,
    df_ocorrencias_global=None,
) -> dict:
    """
    KPI – Nível de Serviço

    Fórmula: (1 − Ocorrências relevantes / Nº de Shows) × 100
        • Ocorrências relevantes = todas exceto TIPO "Leve".
        • Se não houver ocorrências → 100 % (desde que haja shows).
    """
    # ------------------------------------------------------------------ #
    # 1) Carrega base Eshows e remove colunas duplicadas
    # ------------------------------------------------------------------ #
    df_eshows = (df_eshows_global.copy()
                 if df_eshows_global is not None
                 else carregar_base_eshows().copy())

    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    # ------------------------------------------------------------------ #
    # 2) Filtra período principal
    # ------------------------------------------------------------------ #
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range) # Passa custom_range
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 3) Carrega ocorrências e trata duplicadas
    # ------------------------------------------------------------------ #
    df_ocorrencias = (df_ocorrencias_global.copy()
                      if df_ocorrencias_global is not None
                      else carregar_ocorrencias().copy())

    if df_ocorrencias is not None:
        df_ocorrencias = df_ocorrencias.loc[:, ~df_ocorrencias.columns.duplicated()]

    # ------------------------------------------------------------------ #
    # 4) Se não houver ocorrências → nível de serviço máximo
    # ------------------------------------------------------------------ #
    num_shows = df_principal["Id do Show"].nunique()

    if df_ocorrencias is None or df_ocorrencias.empty:
        if num_shows == 0:
            return {
                "periodo": label_periodo,
                "resultado": "0.00%",
                "status": "controle",
                "variables_values": {},
            }
        return {
            "periodo": label_periodo,
            "resultado": "100.00%",
            "status": "bom",
            "variables_values": {
                "Ocorrências (excl. leves)": 0,
                "Shows": num_shows,
            },
        }

    # ------------------------------------------------------------------ #
    # 5) Filtra ocorrências no mesmo período
    # ------------------------------------------------------------------ #
    df_occ_temp = df_ocorrencias.rename(columns={"DATA": "Data"}).copy()
    df_occ_princ = filtrar_periodo_principal(df_occ_temp, ano, periodo, mes, custom_range) # Passa custom_range

    # descarta TIPO = "Leve"
    if "TIPO" in df_occ_princ.columns:
        df_occ_princ = df_occ_princ[df_occ_princ["TIPO"] != "Leve"]

    ocorr_count = (
        df_occ_princ["ID_OCORRENCIA"].nunique()
        if not df_occ_princ.empty and "ID_OCORRENCIA" in df_occ_princ.columns
        else 0
    )

    if num_shows <= 0:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {
                "Ocorrências (excl. leves)": ocorr_count,
                "Shows": 0,
            },
        }

    # ------------------------------------------------------------------ #
    # 6) Calcula nível de serviço
    # ------------------------------------------------------------------ #
    ns_pct = (1.0 - (ocorr_count / num_shows)) * 100.0

    if ns_pct < 80:
        st = "ruim"
    elif ns_pct < 95:
        st = "controle"
    else:
        st = "bom"

    return {
        "periodo": label_periodo,
        "resultado": f"{ns_pct:.2f}%",
        "status": st,
        "variables_values": {
            "Ocorrências (excl. leves)": ocorr_count,
            "Shows": num_shows,
        },
    }

# ======================================================================
# KPI: Turn Over  (map: ["pessoas"])
# ======================================================================
def get_turnover_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_pessoas_global=None,
) -> dict:
    """
    Turn Over = desligamentos / funcionários-iniciais × 100
    Funcionários-iniciais = quadro ativo NA VÉSPERA do período.
    """
    # 1) base Pessoas
    df_p = (
        df_pessoas_global.copy()
        if df_pessoas_global is not None
        else carregar_pessoas().copy()
    )
    if df_p is None or df_p.empty:
        return {
            "periodo": "n/d",
            "valor": 0.0,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # 2) datas em datetime
    df_p["DataInicio"] = pd.to_datetime(df_p.get("DataInicio"), errors="coerce")
    df_p["DataFinal"]  = pd.to_datetime(df_p.get("DataFinal"),  errors="coerce")

    # 3) intervalo de análise
    if periodo == "custom-range" and custom_range and len(custom_range) == 2:
        start_date, end_date = [pd.to_datetime(d).normalize() for d in custom_range]
        label_periodo = f"{start_date:%d/%m/%Y} – {end_date:%d/%m/%Y}"
    else:
        start_date = get_period_start(ano, periodo, mes, custom_range)
        end_date   = get_period_end  (ano, periodo, mes, custom_range)
        label_periodo = mes_nome_intervalo(
            pd.DataFrame({"Data": [start_date]}), periodo
        )

    # 4) funcionários -iniciais (ativos na véspera)
    cond_iniciais = (
        (df_p["DataInicio"] < start_date)
        & (df_p["DataFinal"].isna() | (df_p["DataFinal"] >= start_date))
    )
    n_iniciais = int(cond_iniciais.sum())

    # 5) desligamentos dentro do período
    cond_desl = (
        (~df_p["DataFinal"].isna())
        & (df_p["DataFinal"] >= start_date)
        & (df_p["DataFinal"] <= end_date)
    )
    n_deslig = int(cond_desl.sum())

    turnover_pct = 0 if n_iniciais == 0 else round(n_deslig / n_iniciais * 100, 2)
    status = "bom" if turnover_pct < 5 else "controle" if turnover_pct < 10 else "ruim"

    return {
        "periodo": label_periodo,
        "valor": turnover_pct,
        "resultado": f"{turnover_pct:.2f}%",
        "status": status,
        "variables_values": {
            "Desligamentos": n_deslig,
            "Funcionários Iniciais": n_iniciais,
        },
    }

# ======================================================================
# KPI: Palcos Vazios
# ======================================================================
def get_palcos_vazios_variables(
    ano,
    periodo,
    mes,
    custom_range=None,  # Novo parâmetro
    df_ocorrencias_global=None,
    comparar_opcao=None,
    datas_comparacao=None,
    start_date_main=None,
    end_date_main=None,
    start_date_compare=None,
    end_date_compare=None
):
    """
    Conta 'Palco vazio' no período principal e calcula variação se houver comparação.
    """
    # --> Ajustar custom_range
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    if df_ocorrencias_global is not None:
        df_ocorrencias = df_ocorrencias_global
    else:
        df_ocorrencias = carregar_ocorrencias()

    if df_ocorrencias is None or df_ocorrencias.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0",
            "status": "controle",
            "variables_values": {"Palcos Vazios": 0}
        }

    df_occ_temp = df_ocorrencias.rename(columns={"DATA": "Data"}).copy()
    date_range_main = custom_range if custom_range else (start_date_main, end_date_main)

    df_occ_princ = filtrar_periodo_principal(df_occ_temp, ano, periodo, mes, date_range_main)
    label_periodo = mes_nome_intervalo(df_occ_princ, periodo)

    if df_occ_princ.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0",
            "status": "controle",
            "variables_values": {"Palcos Vazios": 0}
        }

    if "TIPO" not in df_occ_princ.columns:
        return {
            "periodo": label_periodo,
            "resultado": "0",
            "status": "controle",
            "variables_values": {"Palcos Vazios": 0}
        }

    df_occ_princ_pv = df_occ_princ[df_occ_princ["TIPO"] == "Palco vazio"].copy()
    if "ID_OCORRENCIA" in df_occ_princ_pv.columns:
        palcos_vazios = df_occ_princ_pv["ID_OCORRENCIA"].nunique()
    else:
        palcos_vazios = len(df_occ_princ_pv)

    palcos_vazios_comp = 0
    var_palcosvazios = None

    if comparar_opcao is not None:
        date_range_compare_ = custom_range if (custom_range and periodo == "custom-range") else (start_date_compare, end_date_compare)
        df_occ_comp = filtrar_periodo_comparacao(
            df_occ_temp,
            ano, periodo, mes,
            comparar_opcao,
            date_range_compare_
        )
        if not df_occ_comp.empty and "TIPO" in df_occ_comp.columns:
            df_occ_comp_pv = df_occ_comp[df_occ_comp["TIPO"] == "Palco vazio"]
            if "ID_OCORRENCIA" in df_occ_comp_pv.columns:
                palcos_vazios_comp = df_occ_comp_pv["ID_OCORRENCIA"].nunique()
            else:
                palcos_vazios_comp = len(df_occ_comp_pv)

            if palcos_vazios_comp > 0:
                var_palcosvazios = ((palcos_vazios - palcos_vazios_comp) / palcos_vazios_comp) * 100

    if var_palcosvazios is not None:
        if var_palcosvazios > 0:
            status = "ruim"
        elif var_palcosvazios < 0:
            status = "bom"
        else:
            status = "controle"
    else:
        status = "controle"

    return {
        "periodo": label_periodo,
        "resultado": str(palcos_vazios),
        "status": status,
        "variables_values": {
            "Palcos Vazios": palcos_vazios,
            "Palcos Vazios (comp)": palcos_vazios_comp,
            "var_palcosvazios": var_palcosvazios
        }
    }

# ======================================================================
# KPI: Perdas Operacionais
# ======================================================================
def get_perdas_operacionais_variables(
    ano,
    periodo,
    mes,
    custom_range=None,
    df_eshows_global=None,
    df_base2_global=None
):
    """
    KPI: Perdas Operacionais = (Custos 'Op. Shows' / Faturamento) x 100
    """
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None
    df_eshows = df_eshows_global if df_eshows_global is not None else carregar_base_eshows()
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_principal, periodo)
    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }
    # Carrega base2 para "Op. Shows"
    df_base2_ = df_base2_global if df_base2_global is not None else carregar_base2()
    if df_base2_ is None or df_base2_.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }
    df_b2_filtrada = filtrar_periodo_principal(df_base2_, ano, periodo, mes, custom_range)

    # Calcula soma de "Op. Shows" no período principal
    erros_op = 0.0
    if not df_b2_filtrada.empty:
        if "Op. Shows" not in df_b2_filtrada.columns:
            alt_names = ["Op Shows", "Op_Shows", "OpShows"]
            for alt in alt_names:
                if alt in df_b2_filtrada.columns:
                    df_b2_filtrada.rename(columns={alt: "Op. Shows"}, inplace=True)
                    break
        if "Op. Shows" in df_b2_filtrada.columns:
            df_b2_filtrada["Op. Shows"] = pd.to_numeric(df_b2_filtrada["Op. Shows"], errors='coerce').fillna(0)
            erros_op = df_b2_filtrada["Op. Shows"].sum()

    # Calcula faturamento (soma das colunas de receita) no período principal
    for c in COLUNAS_FATURAMENTO:
        if c not in df_principal.columns:
            df_principal[c] = 0
        else:
            df_principal[c] = pd.to_numeric(df_principal[c], errors='coerce').fillna(0)
    fat_df = df_principal[COLUNAS_FATURAMENTO]
    fat = fat_df.sum().sum() if not fat_df.empty else 0.0

    if fat <= 0:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {
                "Erros Operacionais (Op. Shows)": float(erros_op),
                "Faturamento": 0
            }
        }

    perdas_pct = (erros_op / fat) * 100.0
    if perdas_pct < 1:
        st = "bom"
    elif perdas_pct < 3:
        st = "controle"
    else:
        st = "ruim"

    return {
        "periodo": label_periodo,
        "resultado": f"{perdas_pct:.2f}%",
        "status": st,
        "variables_values": {
            "Erros Operacionais (Op. Shows)": float(erros_op),
            "Faturamento": float(fat)
        }
    }

# ------------------------------------------------------------------
# HELPER • get_inadimplencia_real_variables
# ------------------------------------------------------------------
def get_inadimplencia_real_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
    df_inad_casas=None,
    df_inad_artistas=None,
) -> dict:
    """
    Inadimplência Real = (Valor Adiantado inadimplente / Faturamento) × 100
    """
    # ------------------------------------------------------------------ #
    # 1) Intervalo customizado?
    # ------------------------------------------------------------------ #
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    # ------------------------------------------------------------------ #
    # 2) Base Eshows + período
    # ------------------------------------------------------------------ #
    df_eshows = df_eshows_global if df_eshows_global is not None else carregar_base_eshows()
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 3) Faturamento no período
    # ------------------------------------------------------------------ #
    for c in COLUNAS_FATURAMENTO:
        if c not in df_principal.columns:
            df_principal[c] = 0
        else:
            df_principal[c] = pd.to_numeric(df_principal[c], errors="coerce").fillna(0)
    fat = df_principal[COLUNAS_FATURAMENTO].sum().sum()

    # Datas do período
    df_principal["DataTemp"] = pd.to_datetime(
        df_principal["Data do Show"], errors="coerce"
    )
    dt_min = df_principal["DataTemp"].min()
    dt_max = df_principal["DataTemp"].max()
    if pd.isna(dt_min) or pd.isna(dt_max):
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 4) Carrega boletos
    # ------------------------------------------------------------------ #
    if df_inad_casas is None or df_inad_artistas is None:
        casas, artistas = carregar_base_inad()
    else:
        casas, artistas = df_inad_casas.copy(), df_inad_artistas.copy()

    if casas.empty or artistas.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # ------------------------------------------------------------------ #
    # 5) Boletos das casas no período
    # ------------------------------------------------------------------ #
    casas["DataVenc"] = pd.to_datetime(casas["Data Vencimento"], errors="coerce")
    mask_periodo = (casas["DataVenc"] >= dt_min) & (casas["DataVenc"] <= dt_max)
    df_casas_periodo = casas[mask_periodo].copy()

    status_inad = ["vencido", "dunning_requested"]
    cutoff_date = dt_max - pd.Timedelta(days=22)
    df_inad = df_casas_periodo[
        (df_casas_periodo["Status"].isin(status_inad)) &
        (df_casas_periodo["DataVenc"] <= cutoff_date)
    ].copy()

    # ------------------------------------------------------------------ #
    # 6) Boletos de artistas adiantados relacionados
    # ------------------------------------------------------------------ #
    artistas["Adiantamento"] = artistas["Adiantamento"].astype(str).str.lower().fillna("")
    df_adiant = artistas[
        (artistas["Adiantamento"] == "sim") &
        (artistas["ID_Boleto"].isin(df_inad["ID_Boleto"]))
    ].copy()

    df_adiant["Valor Bruto"] = pd.to_numeric(df_adiant["Valor Bruto"], errors="coerce").fillna(0)
    df_inad["Valor Real"]    = pd.to_numeric(df_inad["Valor Real"], errors="coerce").fillna(0)

    df_adiant_grouped = (
        df_adiant.groupby("ID_Boleto")["Valor Bruto"].sum().reset_index()
        .merge(df_inad[["ID_Boleto", "Valor Real"]], on="ID_Boleto", how="left")
    )

    def ajusta_adiant(row):
        vb = row["Valor Bruto"]
        vr = row["Valor Real"]
        return vr if vb > vr else vb

    df_adiant_grouped["Valor Adiantado Ajustado"] = df_adiant_grouped.apply(ajusta_adiant, axis=1)
    valor_adiantado_inad = df_adiant_grouped["Valor Adiantado Ajustado"].sum()

    # ------------------------------------------------------------------ #
    # 7) Percentual
    # ------------------------------------------------------------------ #
    if fat <= 0:
        inad_real = 0.0
    else:
        inad_real = (valor_adiantado_inad / fat) * 100

    if inad_real < 1:
        st = "bom"
    elif inad_real < 2:
        st = "controle"
    else:
        st = "ruim"

    return {
        "periodo": label_periodo,
        "resultado": f"{inad_real:.2f}%",
        "status": st,
        "variables_values": {
            "Adiantado Inadimplente": float(valor_adiantado_inad),
            "Faturamento": float(fat),
        },
    }

# ======================================================================
# KPI: Crescimento Sustentável
# ======================================================================
def get_crescimento_sustentavel_variables(
    ano,
    periodo,
    mes,
    custom_range=None,
    df_eshows_global=None,
    df_base2_global=None
):
    """
    Crescimento Sustentável = (Variação Faturamento %) − (Variação Custos %)
    """
    import pandas as pd

    # —————————————————— sanity check do custom_range ——————————————————
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    # —————————————————— bases --------------------------------------------------
    df_eshows = df_eshows_global if df_eshows_global is not None else carregar_base_eshows()
    df_base2  = df_base2_global  if df_base2_global  is not None else carregar_base2()

    if (
        df_eshows is None or df_eshows.empty or
        df_base2 is None  or df_base2.empty
    ):
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # —————————————————— período atual -----------------------------------------
    df_fat_atual = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range).copy()
    df_cus_atual = filtrar_periodo_principal(df_base2,  ano, periodo, mes, custom_range).copy()
    label_periodo = mes_nome_intervalo(df_fat_atual, periodo)

    if df_fat_atual.empty or df_cus_atual.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    for c in COLUNAS_FATURAMENTO:
        df_fat_atual[c] = pd.to_numeric(df_fat_atual.get(c, 0), errors="coerce").fillna(0)
    faturamento_atual_val = df_fat_atual[COLUNAS_FATURAMENTO].sum().sum()

    df_cus_atual["Custos"] = pd.to_numeric(df_cus_atual.get("Custos", 0), errors="coerce").fillna(0)
    custos_atual_val = df_cus_atual["Custos"].sum()

    # —————————————————— período anterior (ano-1) -------------------------------
    ano_prev = ano - 1
    custom_prev = None
    if custom_range and periodo == "custom-range":
        ini, fim = custom_range
        custom_prev = (ini.replace(year=ini.year - 1), fim.replace(year=fim.year - 1))

    df_fat_prev = filtrar_periodo_principal(df_eshows, ano_prev, periodo, mes, custom_prev).copy()
    df_cus_prev = filtrar_periodo_principal(df_base2,  ano_prev, periodo, mes, custom_prev).copy()

    for c in COLUNAS_FATURAMENTO:
        df_fat_prev[c] = pd.to_numeric(df_fat_prev.get(c, 0), errors="coerce").fillna(0)
    faturamento_prev_val = df_fat_prev[COLUNAS_FATURAMENTO].sum().sum()

    df_cus_prev["Custos"] = pd.to_numeric(df_cus_prev.get("Custos", 0), errors="coerce").fillna(0)
    custos_prev_val = df_cus_prev["Custos"].sum()

    # —————————————————— variações --------------------------------------------
    variacao_fat_pct    = ((faturamento_atual_val - faturamento_prev_val) / faturamento_prev_val * 100
                           if faturamento_prev_val else 0.0)
    variacao_custos_pct = ((custos_atual_val      - custos_prev_val)  / custos_prev_val      * 100
                           if custos_prev_val else 0.0)

    crescimento_val   = variacao_fat_pct - variacao_custos_pct
    resultado_texto   = formatar_valor_utils(crescimento_val, "percentual")
    status_kpi        = get_kpi_status("Crescimento Sustentável", crescimento_val, kpi_descriptions)[0]

    return {
        "variables_values": {
            f"Faturamento {ano_prev}":              float(faturamento_prev_val),
            f"Faturamento {ano}":                  float(faturamento_atual_val),
            "Variação do Faturamento (%)":         float(variacao_fat_pct),
            f"Custos {ano_prev}":                  float(custos_prev_val),
            f"Custos {ano}":                       float(custos_atual_val),
            "Variação dos Custos (%)":             float(variacao_custos_pct),
        },
        "periodo":   label_periodo,
        "resultado": resultado_texto,
        "status":    status_kpi,
    }


# ======================================================================
# KPI: Perfis Completos
# ======================================================================
def get_perfis_completos_variables(
    ano,
    periodo,
    mes,
    custom_range=None, # Adicionado custom_range
    df_base2_global=None
):
    """
    KPI: Perfis Completos (["base2"])
    Exemplo de cálculo:
      - 'Base Acumulada Completa' / 'Base Acumulada Total' * 100
    """
    # 1) Carrega base2
    if df_base2_global is not None:
        df_base2 = df_base2_global
    else:
        df_base2 = carregar_base2()

    if df_base2 is None or df_base2.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # 2) Filtrar
    df_principal = filtrar_periodo_principal(df_base2, ano, periodo, mes, custom_range) # Passa custom_range
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # 3) Garante colunas
    for col_ in ["Base Acumulada Completa", "Base Acumulada Total"]:
        if col_ not in df_principal.columns:
            df_principal[col_] = 0
        else:
            df_principal[col_] = pd.to_numeric(df_principal[col_], errors="coerce").fillna(0)

    # 4) Soma
    completos = df_principal["Base Acumulada Completa"].sum()
    total_ = df_principal["Base Acumulada Total"].sum()

    if total_ > 0:
        perfis_pct = (completos / total_) * 100.0
    else:
        perfis_pct = 0.0

    # 5) Status
    st, icon = get_kpi_status("Perfis Completos", perfis_pct, kpi_descriptions)

    return {
        "variables_values": {
            "Base Acumulada Completa": float(completos),
            "Base Acumulada Total": float(total_)
        },
        "periodo": label_periodo,
        "resultado": formatar_valor_utils(perfis_pct, "percentual"),
        "status": st,
        "icon": icon
    }

# ======================================================================
# KPI: Take Rate
# ======================================================================
def get_take_rate_variables(
    ano,
    periodo,
    mes,
    custom_range=None, # Adicionado custom_range
    df_eshows_global=None
):
    """
    KPI: Take Rate = (Comissão B2B / GMV) x 100
    - GMV = soma de "Valor Total do Show" no período
    - Comissão B2B = soma da coluna "Comissão B2B" no período
    """
    import pandas as pd
    df_eshows = df_eshows_global if df_eshows_global is not None else carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range) # Passa custom_range
    label_periodo = mes_nome_intervalo(df_principal, periodo)
    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # 1) Calcula GMV (soma de Valor Total do Show)
    if "Valor Total do Show" not in df_principal.columns:
        alt_names = ["ValorTotaldoShow", "Valor_Total_do_Show"]
        for alt in alt_names:
            if alt in df_principal.columns:
                df_principal.rename(columns={alt: "Valor Total do Show"}, inplace=True)
                break
        if "Valor Total do Show" not in df_principal.columns:
            df_principal["Valor Total do Show"] = 0
    df_principal["Valor Total do Show"] = pd.to_numeric(
        df_principal["Valor Total do Show"], errors='coerce'
    ).fillna(0)
    gmv = df_principal["Valor Total do Show"].sum()

    # 2) Calcula Comissão B2B total no período
    if "Comissão B2B" not in df_principal.columns:
        alt_name = "Comissao B2B"
        if alt_name in df_principal.columns:
            df_principal.rename(columns={alt_name: "Comissão B2B"}, inplace=True)
        if "Comissão B2B" not in df_principal.columns:
            df_principal["Comissão B2B"] = 0
    df_principal["Comissão B2B"] = pd.to_numeric(
        df_principal["Comissão B2B"], errors='coerce'
    ).fillna(0)
    soma_b2b = df_principal["Comissão B2B"].sum()

    # 3) Calcula Take Rate (%)
    if gmv <= 0:
        take_rate = 0.0
    else:
        take_rate = (soma_b2b / gmv) * 100

    st, icon = get_kpi_status("Take Rate", take_rate, kpi_descriptions)
    return {
        "periodo": label_periodo,
        "resultado": f"{take_rate:.2f}%",
        "status": st,
        "icon": icon,
        "variables_values": {
            "Comissão B2B (R$)": float(soma_b2b),
            "GMV (R$)": float(gmv)
        }
    }

# ======================================================================
# KPI: Autonomia do Usuário
# ======================================================================
def get_autonomia_usuario_variables(
    ano,
    periodo,
    mes,
    custom_range=None,  # Novo parâmetro
    df_base2_global=None
):
    """
    KPI: Autonomia do Usuário.
    Args:
        ano, periodo, mes
        custom_range (tuple) ou None
    """
    # --> Ajuste
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    if df_base2_global is not None:
        df_base2 = df_base2_global
    else:
        df_base2 = carregar_base2()

    if df_base2 is None or df_base2.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    df_principal = filtrar_periodo_principal(df_base2, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    for col_ in ["Propostas Lancadas Usuários", "Propostas Lancadas Internas"]:
        if col_ not in df_principal.columns:
            df_principal[col_] = 0
        else:
            df_principal[col_] = pd.to_numeric(df_principal[col_], errors="coerce").fillna(0)

    soma_usuarios = df_principal["Propostas Lancadas Usuários"].sum()
    soma_internas = df_principal["Propostas Lancadas Internas"].sum()
    total = soma_usuarios + soma_internas

    if total > 0:
        autonomia_val = (soma_usuarios / total) * 100.0
    else:
        autonomia_val = 0.0

    st, icon = get_kpi_status("Autonomia do Usuário", autonomia_val, kpi_descriptions)

    return {
        "variables_values": {
            "Propostas Lançadas Usuários": float(soma_usuarios),
            "Propostas Lançadas Internas": float(soma_internas)
        },
        "periodo": label_periodo,
        "resultado": formatar_valor_utils(autonomia_val, "percentual"),
        "status": st,
        "icon": icon
    }

# --------------------------------------------------------------------------- #
# KPI: NPS Artistas                                                           #
# --------------------------------------------------------------------------- #
def get_nps_artistas_variables(
    ano: int,
    periodo: str,
    mes: int | None,
    custom_range=None,
    df_nps_global:  pd.DataFrame | None = None,
    df_base2_global: pd.DataFrame | None = None,   # compat legado
) -> dict:
    from .modulobase import carregar_npsartistas

    COL_NPS_NOTAS = "NPS Eshows"

    # ------------------------------------------------------------------
    # 1) escolhe o DataFrame correto
    # ------------------------------------------------------------------
    if df_nps_global is not None and COL_NPS_NOTAS in df_nps_global.columns:
        df_nps_base = df_nps_global.copy()
    elif df_base2_global is not None and COL_NPS_NOTAS in df_base2_global.columns:
        df_nps_base = df_base2_global.copy()       # raro, mas cobre fallback
    else:
        df_nps_base = carregar_npsartistas().copy()

    if "Data" in df_nps_base.columns:
        df_nps_base["Data"] = pd.to_datetime(df_nps_base["Data"], errors="coerce")

    COL_NPS_NOTAS = "NPS Eshows" # Nome da coluna com as notas 0-10

    if df_nps_base.empty or COL_NPS_NOTAS not in df_nps_base.columns:
        return {"periodo": "Sem dados", "resultado": "0", "status": "controle", "variables_values": {}}

    # _buscar_periodo_valido_nps retorna df com notas originais (0-10)
    df_ok_com_notas, label = _buscar_periodo_valido_nps(
        df_nps_base,
        ano,
        periodo,
        mes,
        COL_NPS_NOTAS,
        custom_range=custom_range
    )

    if df_ok_com_notas.empty:
        return {"periodo": label, "resultado": "0", "status": "controle", "variables_values": {}}

    notas = pd.to_numeric(df_ok_com_notas[COL_NPS_NOTAS], errors='coerce').dropna()
    
    if notas.empty:
        return {"periodo": label, "resultado": "0", "status": "controle", "variables_values": {}}

    total_respostas = len(notas)
    promotores_count = notas[notas >= 9].count()
    detratores_count = notas[notas <= 6].count()
    
    prom_pct = (promotores_count / total_respostas) * 100 if total_respostas > 0 else 0
    det_pct = (detratores_count / total_respostas) * 100 if total_respostas > 0 else 0
    pas_pct = 100 - prom_pct - det_pct

    nps_score = prom_pct - det_pct
    
    st, icon = get_kpi_status("NPS Artistas", nps_score, kpi_descriptions)

    return {
        "variables_values": {
            "%Promotores": prom_pct,
            "%Detratores": det_pct,
            "%Passivos": pas_pct,
            "Total Respostas": total_respostas
        },
        "periodo": label,
        "resultado": formatar_valor_utils(nps_score, "numero"), 
        "status": st,
        "icon": icon,
    }

# --------------------------------------------------------------------------- #
# KPI: NPS Equipe                                                             #
# --------------------------------------------------------------------------- #
def get_nps_equipe_variables(
    ano: int,
    periodo: str,
    mes: int | None,
    custom_range=None,  # mantido para compatibilidade
    df_nps_global: pd.DataFrame | None = None, 
) -> dict:
    from .modulobase import carregar_npsartistas 
    df_nps_base = df_nps_global.copy() if df_nps_global is not None else carregar_npsartistas().copy()

    if "Data" in df_nps_base.columns:
        df_nps_base["Data"] = pd.to_datetime(df_nps_base["Data"], errors="coerce")

    COL_NPS_NOTAS = "NPS Equipe" # Nome da coluna com as notas 0-10

    if df_nps_base.empty or COL_NPS_NOTAS not in df_nps_base.columns:
        return {"periodo": "Sem dados", "resultado": "0", "status": "controle", "variables_values": {}}

    df_ok_com_notas, label = _buscar_periodo_valido_nps(df_nps_base, ano, periodo, mes, COL_NPS_NOTAS)

    if df_ok_com_notas.empty:
        return {"periodo": label, "resultado": "0", "status": "controle", "variables_values": {}}

    notas = pd.to_numeric(df_ok_com_notas[COL_NPS_NOTAS], errors='coerce').dropna()

    if notas.empty:
        return {"periodo": label, "resultado": "0", "status": "controle", "variables_values": {}}
        
    total_respostas = len(notas)
    promotores_count = notas[notas >= 9].count()
    detratores_count = notas[notas <= 6].count()

    prom_pct = (promotores_count / total_respostas) * 100 if total_respostas > 0 else 0
    det_pct = (detratores_count / total_respostas) * 100 if total_respostas > 0 else 0
    pas_pct = 100 - prom_pct - det_pct

    nps_score = prom_pct - det_pct

    st, icon = get_kpi_status("NPS Equipe", nps_score, kpi_descriptions)

    return {
        "variables_values": {
            "%Promotores": prom_pct,
            "%Detratores": det_pct,
            "%Passivos": pas_pct,
            "Total Respostas": total_respostas
        },
        "periodo": label,
        "resultado": formatar_valor_utils(nps_score, "numero"),
        "status": st,
        "icon": icon,
    }

# ======================================================================
# KPI: Conformidade Jurídica
# ======================================================================
def get_conformidade_juridica_variables(
    ano,
    periodo,
    mes,
    custom_range=None, # Adicionado custom_range
    df_base2_global=None
):
    """
    KPI: Conformidade Jurídica (["base2"])
    Exemplo de cálculo:
      - 'Casas Contrato' vs. 'Casas Ativas'
      - Conformidade = (Casas Contrato / Casas Ativas) * 100
    """
    # 1) Carrega base2
    if df_base2_global is not None:
        df_base2 = df_base2_global
    else:
        df_base2 = carregar_base2()

    if df_base2 is None or df_base2.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # 2) Filtrar
    df_principal = filtrar_periodo_principal(df_base2, ano, periodo, mes, custom_range) # Passa custom_range
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # 3) Garante colunas
    for col_ in ["Casas Contrato", "Casas Ativas"]:
        if col_ not in df_principal.columns:
            df_principal[col_] = 0
        else:
            df_principal[col_] = pd.to_numeric(df_principal[col_], errors="coerce").fillna(0)

    # 4) Soma
    casas_contrato = df_principal["Casas Contrato"].sum()
    casas_ativas = df_principal["Casas Ativas"].sum()

    if casas_ativas > 0:
        cj_val = (casas_contrato / casas_ativas) * 100.0
    else:
        cj_val = 0.0

    # 5) get_kpi_status
    st, icon = get_kpi_status("Conformidade Jurídica", cj_val, kpi_descriptions)

    return {
        "variables_values": {
            "Casas Contrato": float(casas_contrato),
            "Casas Ativas": float(casas_ativas)
        },
        "periodo": label_periodo,
        "resultado": formatar_valor_utils(cj_val, "percentual"),
        "status": st,
        "icon": icon
    }

# ======================================================================
# KPI: Eficiência do Atendimento
# ======================================================================
def get_eficiencia_atendimento_variables(
    ano,
    periodo,
    mes,
    custom_range=None,  # Novo parâmetro
    df_base2_global=None
):
    """
    KPI: Eficiência de Atendimento (["base2"])
    
    Args:
        ano (int): Ano de referência
        periodo (str): Período selecionado ('1° Trimestre', 'Mês Aberto', etc.)
        mes (int, optional): Mês específico para 'Mês Aberto'
        custom_range (tuple, optional): (data_inicial, data_final) para período personalizado
        df_base2_global (DataFrame, optional): DataFrame base2 se já carregado
    """
    # 1) Carrega base2
    if df_base2_global is not None:
        df_base2 = df_base2_global
    else:
        df_base2 = carregar_base2()

    if df_base2 is None or df_base2.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # 2) Filtrar (passando custom_range)
    df_principal = filtrar_periodo_principal(df_base2, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # 3) Garante colunas
    for col_ in ["Tempo Resposta", "Tempo Resolução"]:
        if col_ not in df_principal.columns:
            df_principal[col_] = 0
        else:
            df_principal[col_] = pd.to_numeric(df_principal[col_], errors="coerce").fillna(0)

    tempo_resposta_medio = df_principal["Tempo Resposta"].mean()
    tempo_resolucao_medio = df_principal["Tempo Resolução"].mean()

    # ---------------------------------------------------------
    # Exemplo simples de "eficiência": quanto MENOR tempo, melhor
    # Uma das formas de se criar um índice (0..100), ajustado a limites
    # Abaixo fixamos limites arbitrários: 30min para resposta, 120min para resolução
    # Ajuste conforme sua necessidade real.
    # ---------------------------------------------------------
    LIM_RESPOSTA = 30.0
    LIM_RESOLUCAO = 120.0

    # Score de Resposta = max(0, 100 - (tempo_resposta_medio/LIM_RESPOSTA*100))
    # Score de Resolução = idem
    # Eficiência = média desses scores
    score_resp = 100.0 - (tempo_resposta_medio / LIM_RESPOSTA * 100.0) if LIM_RESPOSTA > 0 else 0
    score_resp = max(min(score_resp, 100), 0)

    score_resol = 100.0 - (tempo_resolucao_medio / LIM_RESOLUCAO * 100.0) if LIM_RESOLUCAO > 0 else 0
    score_resol = max(min(score_resol, 100), 0)

    ef_val = (score_resp + score_resol) / 2.0  # média

    st, icon = get_kpi_status("Eficiência de Atendimento", ef_val, kpi_descriptions)

    return {
        "variables_values": {
            "Tempo Resposta Médio": float(tempo_resposta_medio),
            "Tempo Resolução Médio": float(tempo_resolucao_medio)
        },
        "periodo": label_periodo,
        "resultado": formatar_valor_utils(ef_val, "percentual"),
        "status": st,
        "icon": icon
    }

# ======================================================================
# KPI: Sucesso da Implantação
# ======================================================================
def get_sucesso_implantacao_variables(ano, periodo, mes, dashboard=None):
    """
    Mock aleatório: 10 a 95%
    """
    import random
    val = random.uniform(10,95)
    if val < 30:
        status = 'critico'
    elif val < 50:
        status = 'ruim'
    elif val < 70:
        status = 'controle'
    elif val < 90:
        status = 'bom'
    else:
        status = 'excelente'
    return {
        'resultado': f"{val:.1f}%",
        'periodo': f"{periodo} de {ano}",
        'status': status,
        'variables_values': {}
    }

# ======================================================================
# KPI: Churn %
# ======================================================================
def get_churn_variables(
    ano,
    periodo,
    mes,
    custom_range=None,
    df_eshows_global=None,
    start_date=None,
    end_date=None,
    uf=None,
    dias_sem_show=45
):
    """
    Churn %  =  (Estabelecimentos Perdidos / Estabelecimentos Ativos) × 100
    """
    # —————————————————— sanity check do custom_range ——————————————————
    if not isinstance(custom_range, (list, tuple)) or len(custom_range) != 2:
        custom_range = None

    # —————————————————— carrega / clona a base ——————————————————
    if df_eshows_global is not None:
        df_eshows = df_eshows_global.copy()
    else:
        df_eshows = carregar_base_eshows().copy()

    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    if df_eshows is None or df_eshows.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # —————————————————— recorte do período ——————————————————
    date_range_to_use = custom_range if custom_range else (start_date, end_date)
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, date_range_to_use)
    label_periodo = mes_nome_intervalo(df_principal, periodo)

    if df_principal.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {}
        }

    # —————————————————— métricas ——————————————————
    num_clientes_ativos = df_principal["Id da Casa"].nunique()

    churn_count = calcular_churn(
        ano=ano,
        periodo=periodo,
        mes=mes,
        start_date=start_date,
        end_date=end_date,
        uf=uf,
        dias_sem_show=dias_sem_show,
        custom_range=custom_range
    )

    churn_pct = (churn_count / num_clientes_ativos) * 100 if num_clientes_ativos else 0.0

    # —————————————————— status / cor / ícone ——————————————————
    st, _icon = get_kpi_status("Churn %", churn_pct, kpi_descriptions)

    # —————————————————— payload ——————————————————
    return {
        "variables_values": {
            "Estabelecimentos Perdidos": churn_count,
            "Estabelecimentos Ativos no Período": num_clientes_ativos
        },
        "periodo": label_periodo,
        "resultado": f"{churn_pct:.2f}%",
        "status": st
    }

# ======================================================================
# KPI: CAC (Customer Acquisition Cost)
# ======================================================================
def get_cac_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_custosabertos_global=None,
    df_eshows_global=None,        # NOVO
    df_pessoas_global=None,       # NOVO
    df_casas_earliest_global=None # NOVO
) -> dict:
    """
    Calcula o Custo de Aquisição de Cliente (CAC).
    CAC = (Total de Custos de Marketing e Vendas) / (Número de Novos Clientes Adquiridos)

    Custos de Marketing e Vendas são compostos por:
    1. Soma de "Valor" de fornecedores mapeados para "Comercial" no SUPPLIER_TO_SETOR (período por "Data Competencia").
    2. Soma de "Valor" onde "Nivel 1" é 'Visitas a Clientes' (período por "Data Vencimento").
    3. Custo de alimentação proporcional para o comercial:
       ((Soma "Valor" de TEMPUS FUGIT e Flash) / Total Funcionários Ativos) * Funcionários do Comercial.
       (Alimentação por "Data Competencia", Funcionários do Comercial por "Data Competencia").
    """
    from .modulobase import (
        carregar_custosabertos,
        carregar_base_eshows, # <<< CORRIGIDO AQUI
        carregar_pessoas
    )
    from .utils import (
        filtrar_periodo_principal,
        get_period_start,
        get_period_end,
        mes_nome_intervalo,
        filtrar_novos_palcos_por_periodo
    )
    from .column_mapping import SUPPLIER_TO_SETOR
    from dateutil.relativedelta import relativedelta # Para cálculo de funcionários ativos
    import pandas as pd
    import numpy as np # Para np.mean em funcionários ativos

    # ------------------------------------------------------------------ #
    # 1) Carrega bases (ou usa as injetadas)                             #
    # ------------------------------------------------------------------ #
    df_custos = (
        df_custosabertos_global.copy()
        if df_custosabertos_global is not None
        else carregar_custosabertos().copy()
    )
    df_eshows = (
        df_eshows_global.copy()
        if df_eshows_global is not None
        else carregar_base_eshows().copy() # <<< E AQUI
    )
    df_pessoas = (
        df_pessoas_global.copy()
        if df_pessoas_global is not None
        else carregar_pessoas().copy()
    )

    if df_custos is not None and not df_custos.empty:
        df_custos = df_custos.loc[:, ~df_custos.columns.duplicated()]
    if df_eshows is not None and not df_eshows.empty:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]
        # df_casas_earliest é derivado de df_eshows
        df_casas_earliest = (
            df_casas_earliest_global.copy()
            if df_casas_earliest_global is not None
            else df_eshows.groupby("Id da Casa")["Data do Show"].min().reset_index().rename(columns={"Data do Show": "EarliestShow"})
        )
    else: # df_eshows está vazio
        df_casas_earliest = pd.DataFrame(columns=["Id da Casa", "EarliestShow"])


    if df_pessoas is not None and not df_pessoas.empty:
        df_pessoas = df_pessoas.loc[:, ~df_pessoas.columns.duplicated()]
        # Converte colunas de data em df_pessoas para datetime
        df_pessoas["DataInicio"] = pd.to_datetime(df_pessoas.get("DataInicio"), errors='coerce')
        df_pessoas["DataSaida"] = pd.to_datetime(df_pessoas.get("DataSaida"), errors='coerce')


    # Label do período (usado no retorno)
    # Tenta criar um label a partir do df_eshows (mais provável ter datas representativas)
    # ou df_custos se df_eshows estiver vazio.
    df_para_label = df_eshows if not df_eshows.empty else df_custos
    label_periodo_calculado = "Sem dados suficientes para determinar período"
    if not df_para_label.empty:
        # Precisamos de um df minimamente filtrado para mes_nome_intervalo funcionar
        # Se custom_range for fornecido, usamos ele diretamente.
        # Caso contrário, fazemos um filtro genérico apenas para obter o label.
        if custom_range:
             # Para custom_range, o ideal é formatar as datas diretamente, se possível
            try:
                label_periodo_calculado = f"{pd.to_datetime(custom_range[0]):%d/%m/%y} a {pd.to_datetime(custom_range[1]):%d/%m/%y}"
            except: # Fallback se custom_range não for datelike
                 df_temp_label = filtrar_periodo_principal(df_para_label.copy(), ano, periodo, mes, custom_range)
                 label_periodo_calculado = mes_nome_intervalo(df_temp_label, periodo)
        else:
            df_temp_label = filtrar_periodo_principal(df_para_label.copy(), ano, periodo, mes, custom_range)
            label_periodo_calculado = mes_nome_intervalo(df_temp_label, periodo)


    # Se a base de custos estiver vazia, não há como calcular CAC.
    if df_custos is None or df_custos.empty:
        return {
            "periodo": label_periodo_calculado,
            "resultado": "R$0.00",
            "status": "controle",
            "variables_values": {
                "Total Custos Mkt & Vendas": 0,
                "Novos Clientes": 0,
                "Debug": "Base de custos vazia ou não carregada."
            }
        }

    # Garante que as colunas de valor e data existam e sejam do tipo correto em df_custos
    df_custos["Valor"] = pd.to_numeric(df_custos.get("Valor"), errors='coerce').fillna(0)
    df_custos["Data Competencia"] = pd.to_datetime(df_custos.get("Data Competencia"), errors='coerce')
    df_custos["Data Vencimento"] = pd.to_datetime(df_custos.get("Data Vencimento"), errors='coerce')

    # ------------------------------------------------------------------ #
    # 2) Filtra df_custos pelo período principal (separado por data)     #
    # ------------------------------------------------------------------ #
    # Preserva o df_custos original para diferentes filtros de data
    df_custos_original = df_custos.copy()

    # Filtro por "Data Competencia"
    # Renomeia temporariamente para "Data" para usar filtrar_periodo_principal
    df_custos_para_filtro_competencia = df_custos_original.rename(columns={"Data Competencia": "Data"}).copy() # Adicionado .copy()
    # Garante que a coluna "Data" seja datetime, não categórica, e remove NaTs
    df_custos_para_filtro_competencia["Data"] = pd.to_datetime(df_custos_para_filtro_competencia["Data"], errors='coerce')
    if pd.api.types.is_categorical_dtype(df_custos_para_filtro_competencia["Data"]):
        df_custos_para_filtro_competencia["Data"] = df_custos_para_filtro_competencia["Data"].astype(object)
        df_custos_para_filtro_competencia["Data"] = pd.to_datetime(df_custos_para_filtro_competencia["Data"], errors='coerce')
    df_custos_para_filtro_competencia.dropna(subset=["Data"], inplace=True)

    df_custos_filtrado_competencia = filtrar_periodo_principal(
        df_custos_para_filtro_competencia, ano, periodo, mes, custom_range
    )

    # Filtro por "Data Vencimento"
    # Renomeia temporariamente para "Data" para usar filtrar_periodo_principal
    df_custos_para_filtro_vencimento = df_custos_original.rename(columns={"Data Vencimento": "Data"}).copy() # Adicionado .copy()
    # Garante que a coluna "Data" seja datetime, não categórica, e remove NaTs
    df_custos_para_filtro_vencimento["Data"] = pd.to_datetime(df_custos_para_filtro_vencimento["Data"], errors='coerce')
    if pd.api.types.is_categorical_dtype(df_custos_para_filtro_vencimento["Data"]):
        df_custos_para_filtro_vencimento["Data"] = df_custos_para_filtro_vencimento["Data"].astype(object)
        df_custos_para_filtro_vencimento["Data"] = pd.to_datetime(df_custos_para_filtro_vencimento["Data"], errors='coerce')
    df_custos_para_filtro_vencimento.dropna(subset=["Data"], inplace=True)

    df_custos_filtrado_vencimento = filtrar_periodo_principal(
        df_custos_para_filtro_vencimento, ano, periodo, mes, custom_range
    )
    
    # Inicializa variáveis de custo
    custo_fornecedores_comercial_valor = 0.0
    custo_visitas_clientes_valor = 0.0
    custo_alimentacao_proporcional_comercial_valor = 0.0
    
    # Debugging outputs
    debug_info = {
        "Filtro_Competencia_Linhas": len(df_custos_filtrado_competencia),
        "Filtro_Vencimento_Linhas": len(df_custos_filtrado_vencimento),
    }

    # Adiciona DataFrames ao debug_info (completos)
    debug_info["df_custos_filtrado_competencia_full_df"] = df_custos_filtrado_competencia.to_dict('records') if not df_custos_filtrado_competencia.empty else []
    debug_info["df_custos_filtrado_vencimento_full_df"] = df_custos_filtrado_vencimento.to_dict('records') if not df_custos_filtrado_vencimento.empty else []


    # ------------------------------------------------------------------ #
    # 3.1) Custo de Fornecedores do Setor Comercial                      #
    # ------------------------------------------------------------------ #
    fornecedores_comerciais = [
        f for f, setor in SUPPLIER_TO_SETOR.items() if setor == "Comercial"
    ]
    debug_info["Fornecedores_Comerciais_Mapeados"] = fornecedores_comerciais

    if not df_custos_filtrado_competencia.empty and fornecedores_comerciais:
        custos_fornec_comercial_df = df_custos_filtrado_competencia[
            df_custos_filtrado_competencia["Fornecedor"].isin(fornecedores_comerciais)
        ]
        custo_fornecedores_comercial_valor = custos_fornec_comercial_df["Valor"].sum()
        debug_info["Custo_Fornecedores_Comercial_DF_Linhas"] = len(custos_fornec_comercial_df)
        debug_info["custos_fornec_comercial_full_df"] = custos_fornec_comercial_df.to_dict('records') if not custos_fornec_comercial_df.empty else []
    
    debug_info["Custo_Fornecedores_Comercial_Soma"] = custo_fornecedores_comercial_valor

    # ------------------------------------------------------------------ #
    # 3.2) Custo de "Visitas a Clientes"                                 #
    # ------------------------------------------------------------------ #
    if not df_custos_filtrado_vencimento.empty and "Nivel 1" in df_custos_filtrado_vencimento.columns:
        custos_visitas_df = df_custos_filtrado_vencimento[
            df_custos_filtrado_vencimento["Nivel 1"] == "Visitas a Clientes"
        ]
        custo_visitas_clientes_valor = custos_visitas_df["Valor"].sum()
        debug_info["Custo_Visitas_Clientes_DF_Linhas"] = len(custos_visitas_df)
        debug_info["custos_visitas_full_df"] = custos_visitas_df.to_dict('records') if not custos_visitas_df.empty else []

    debug_info["Custo_Visitas_Clientes_Soma"] = custo_visitas_clientes_valor
    
    # ------------------------------------------------------------------ #
    # 3.3) Alimentação proporcional — cálculo mês a mês                  #
    # ------------------------------------------------------------------ #
    df_alim = df_custos_filtrado_competencia[
        df_custos_filtrado_competencia["Nivel 2"] == "MDO Alimentação Funcionário"
    ].copy()

    # ───────────────────────── NORMALIZA NOMES DE COLUNAS ───────────────────────
    df_alim.columns = df_alim.columns.str.strip()

    # Corrige fornecedor se vier digitado errado
    if "Forneceedor" in df_alim.columns and "Fornecedor" not in df_alim.columns:
        df_alim.rename(columns={"Forneceedor": "Fornecedor"}, inplace=True)

    # Descobre/renomeia a coluna de data
    if "Data Competencia" in df_alim.columns:
        date_col_alim = "Data Competencia"
    elif "Data Competência" in df_alim.columns:
        df_alim.rename(columns={"Data Competência": "Data Competencia"}, inplace=True)
        date_col_alim = "Data Competencia"
    elif "Data" in df_alim.columns:
        df_alim.rename(columns={"Data": "Data Competencia"}, inplace=True)
        date_col_alim = "Data Competencia"
    else:
        # Sem coluna de data legível — registra e zera custos
        debug_info["Alimentacao_Erro"] = "Coluna de data não encontrada em df_alim"
        debug_info["Alimentacao_Mensal_Detalhe"] = []
        custo_alimentacao_proporcional_comercial_valor = 0.0
        date_col_alim = None

    if date_col_alim and not df_alim.empty:
        # Prepara datas
        df_alim[date_col_alim] = pd.to_datetime(df_alim[date_col_alim], errors="coerce")
        df_alim["Mês"] = df_alim[date_col_alim].dt.to_period("M")

        # ─ Headcount total por mês ────────────────────────────────────────────
        df_p_tmp = df_pessoas.copy()
        df_p_tmp["DataInicio"] = pd.to_datetime(df_p_tmp["DataInicio"], errors="coerce")
        df_p_tmp["DataSaida"]  = pd.to_datetime(df_p_tmp["DataSaida"],  errors="coerce")

        def headcount_mes(mes: pd.Period) -> int:
            last_day = (mes.to_timestamp() + relativedelta(months=1)) - pd.DateOffset(days=1)
            ativos = (df_p_tmp["DataInicio"] <= last_day) & (
                df_p_tmp["DataSaida"].isna() | (df_p_tmp["DataSaida"] > last_day)
            )
            return int(ativos.sum())

        # ─ Funcionários do Comercial por mês ────────────────────────────────
        comercial_fornec = ["MDO PJ Fixo", "MDO Pró-Labore"]
        df_comercial = df_custos_filtrado_competencia[
            (df_custos_filtrado_competencia["Fornecedor"].isin(fornecedores_comerciais))
            & (df_custos_filtrado_competencia["Nivel 2"].isin(comercial_fornec))
        ].copy()

        # Normaliza nomes de coluna
        df_comercial.columns = df_comercial.columns.str.strip()

        # Detecta/renomeia a coluna de data
        if "Data Competencia" in df_comercial.columns:
            date_col_com = "Data Competencia"
        elif "Data Competência" in df_comercial.columns:
            df_comercial.rename(columns={"Data Competência": "Data Competencia"}, inplace=True)
            date_col_com = "Data Competencia"
        elif "Data" in df_comercial.columns:
            df_comercial.rename(columns={"Data": "Data Competencia"}, inplace=True)
            date_col_com = "Data Competencia"
        else:
            debug_info["Comercial_Erro"] = "Coluna de data não encontrada em df_comercial"
            date_col_com = None

        # Converte para datetime e gera a coluna Mês (Period[M])
        if date_col_com:
            df_comercial[date_col_com] = pd.to_datetime(df_comercial[date_col_com], errors="coerce")
            df_comercial["Mês"] = df_comercial[date_col_com].dt.to_period("M")
            func_comercial_mes = (
                df_comercial.groupby("Mês")["Fornecedor"].nunique().to_dict()
            )
        else:
            df_comercial["Mês"] = pd.NaT
            func_comercial_mes = {}

        # ─ Alimentação proporcional mês a mês ───────────────────────────────
        detalhes_alim = []
        alim_comercial_total = 0.0

        for mes, df_mes in df_alim.groupby("Mês"):
            alim_total_mes = df_mes["Valor"].sum()
            hc_total_mes   = headcount_mes(mes)
            hc_com_mes     = func_comercial_mes.get(mes, 0)

            alim_pp_mes    = alim_total_mes / hc_total_mes if hc_total_mes else 0
            alim_com_mes   = alim_pp_mes * hc_com_mes

            detalhes_alim.append({
                "Mes": mes.strftime("%b/%y"),
                "Alimentacao_Total": float(alim_total_mes),
                "Headcount_Total": hc_total_mes,
                "Alim_por_Pessoa": float(alim_pp_mes),
                "Headcount_Comercial": hc_com_mes,
                "Alimentacao_Comercial": float(alim_com_mes),
            })
            alim_comercial_total += alim_com_mes

        # ------------------------------------------------------------------ #
        # Consolida valores para facilitar o resumo e outros relatórios      #
        # ------------------------------------------------------------------ #
        debug_info["Alimentacao_Mensal_Detalhe"] = detalhes_alim
        debug_info["Custo_Alimentacao_Proporcional_Comercial_Soma"] = alim_comercial_total
        debug_info["Custo_Alimentacao_TempusFlash_Soma"] = float(df_alim["Valor"].sum())
        debug_info["Custo_Alimentacao_Por_Pessoa_Total_Calculado"] = (
            float(np.mean([d["Alim_por_Pessoa"] for d in detalhes_alim])) if detalhes_alim else 0.0
        )
        debug_info["Num_Total_Funcionarios_Ativos_Media"] = (
            int(np.mean([d["Headcount_Total"] for d in detalhes_alim])) if detalhes_alim else 0
        )
        debug_info["Num_Funcionarios_Comercial_Contagem"] = (
            int(np.mean([d["Headcount_Comercial"] for d in detalhes_alim])) if detalhes_alim else 0
        )

        # Valor final que entra no CAC
        custo_alimentacao_proporcional_comercial_valor = alim_comercial_total

    # ------------------------------------------------------------------ #
    # 4) Total Custos de Marketing e Vendas                              #
    # ------------------------------------------------------------------ #
    total_custos_mkt_vendas = (
        custo_fornecedores_comercial_valor +
        custo_visitas_clientes_valor +
        custo_alimentacao_proporcional_comercial_valor
    )
    debug_info["Total_Custos_Mkt_Vendas_Soma"] = total_custos_mkt_vendas

    # ------------------------------------------------------------------ #
    # 5) Número de Novos Clientes Adquiridos                             #
    # ------------------------------------------------------------------ #
    novos_clientes_df = filtrar_novos_palcos_por_periodo(
        df_casas_earliest, ano, periodo, mes, custom_range
    )
    numero_novos_clientes = 0
    if novos_clientes_df is not None and not novos_clientes_df.empty:
        numero_novos_clientes = novos_clientes_df["Id da Casa"].nunique()
    debug_info["Novos_Clientes_DF_Linhas"] = len(novos_clientes_df) if novos_clientes_df is not None else 0
    debug_info["Novos_Clientes_Contagem"] = numero_novos_clientes
    debug_info["novos_clientes_full_df"] = novos_clientes_df.to_dict('records') if novos_clientes_df is not None and not novos_clientes_df.empty else []
    
    # ------------------------------------------------------------------ #
    # 6) Cálculo do CAC                                                  #
    # ------------------------------------------------------------------ #
    cac_valor = 0.0
    if numero_novos_clientes > 0:
        cac_valor = total_custos_mkt_vendas / numero_novos_clientes
    else:
        # Se não houver novos clientes, o CAC é indefinido ou infinito.
        # Para exibição, podemos mostrar 0 ou o próprio custo total se ele for > 0.
        # Por ora, se custo > 0 e clientes = 0, CAC pode ser o próprio custo.
        # Se custo = 0 e clientes = 0, CAC = 0.
        if total_custos_mkt_vendas > 0:
            cac_valor = total_custos_mkt_vendas # Ou float('inf') dependendo da interpretação
            debug_info["CAC_Calculo_Observacao"] = "CAC igual ao custo total pois não houve novos clientes."
        else:
            cac_valor = 0.0
            debug_info["CAC_Calculo_Observacao"] = "CAC zero pois não houve custos nem novos clientes."


    status_cac = "controle" # Adicionar lógica de status se necessário
    # Exemplo:
    # if cac_valor > X: status_cac = "ruim"
    # elif cac_valor < Y: status_cac = "bom"

    return {
        "periodo": label_periodo_calculado,
        "resultado": formatar_valor_utils(cac_valor, "monetario"),
        "status": status_cac,
        "variables_values": {
            "Total Custos Mkt & Vendas": float(total_custos_mkt_vendas),
            "Novos Clientes": int(numero_novos_clientes),
            "CAC Calculado Raw": float(cac_valor),
            "Debug Info": debug_info # Inclui todas as variáveis de debug
        }
    }

# --------------------------------------------------------------------------- #
# _compute_ltv_cac  •  calcula LTV/CAC p/ um único intervalo                  #
# --------------------------------------------------------------------------- #
def _compute_ltv_cac(
    ano: int,
    periodo: str,
    mes: int,
    custom_range,
    df_eshows: pd.DataFrame,
    df_base2: pd.DataFrame, # Mantido por enquanto, mas o CAC virá de get_cac_variables
    df_first: pd.DataFrame,   # EarliestShow  por casa
    df_last:  pd.DataFrame,   # LastShow      por casa
    df_custosabertos: pd.DataFrame, # NOVO para get_cac_variables
    df_pessoas: pd.DataFrame,       # NOVO para get_cac_variables
) -> tuple[dict, bool]:
    """
    Retorna (resultado_dict, ok_bool).
    • ok_bool = False  ➜  caller tenta o próximo período de fallback.
    """
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    import gc

    # ------------------------------------------------------------------ #
    # 1) Período + novos palcos                                          #
    # ------------------------------------------------------------------ #
    df_per  = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    
    # TASK D: Construir label_periodo legível
    if custom_range:
        try:
            ini, fim = custom_range
            label_periodo_calc = f"{pd.to_datetime(ini):%d/%m/%y} – {pd.to_datetime(fim):%d/%m/%y}"
        except Exception as e:
            logger.debug("Erro ao formatar custom_range para label em _compute_ltv_cac: %s", e)
            label_periodo_calc = mes_nome_intervalo(df_per, periodo)  # Fallback
    else:
        label_periodo_calc = mes_nome_intervalo(df_per, periodo)
    # Fim TASK D

    # label original era: label = mes_nome_intervalo(df_per, periodo)

    df_new  = filtrar_novos_palcos_por_periodo(df_first, ano, periodo, mes, custom_range)
    novos_ct= 0 if df_new is None else len(df_new)
    if (novos_ct == 0) or df_per.empty or df_first.empty or df_last.empty:
        return ({"periodo": label_periodo_calc, "resultado": "0", "status": "controle", # Usa label_periodo_calc
                 "variables_values": {"Novos Palcos": 0}}, False)

    novos_ids = df_new["Id da Casa"].unique()

    # ------------------------------------------------------------------ #
    # 2) Faturamento do período                                          #
    # ------------------------------------------------------------------ #
    df_shows = df_per[df_per["Id da Casa"].isin(novos_ids)].copy()
    df_shows[COLUNAS_FATURAMENTO] = df_shows[COLUNAS_FATURAMENTO].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0)
    df_shows["Faturamento"] = df_shows[COLUNAS_FATURAMENTO].sum(axis=1)
    if df_shows["Faturamento"].sum() == 0:
        return ({"periodo": label_periodo_calc, "resultado": "0", "status": "controle",
                 "variables_values": {"Novos Palcos": novos_ct}}, False)

    # ------------------------------------------------------------------ #
    # 3) Churn técnico                                                   #
    # ------------------------------------------------------------------ #
    def churn_ids(df_earliest, df_all_shows, df_new, dias=45, cutoff=None):
        if df_earliest.empty or df_all_shows.empty or df_new.empty:
            return []
        rel = df_all_shows[df_all_shows["Id da Casa"].isin(df_new["Id da Casa"])]
        last = rel.groupby("Id da Casa")["Data do Show"].max().reset_index(name="LastShow")
        last["churn_date"] = last["LastShow"] + timedelta(days=dias)
        cutoff = pd.Timestamp.today().normalize() if cutoff is None else pd.Timestamp(cutoff)
        cand = last[last["churn_date"] <= cutoff]
        if cand.empty:
            return []
        merged = pd.merge(
            cand[["Id da Casa", "LastShow"]],
            rel[["Id da Casa", "Data do Show"]],
            on="Id da Casa", how="left"
        )
        merged["Retornou"] = merged["Data do Show"] > merged["LastShow"]
        return merged.groupby("Id da Casa")["Retornou"].any().loc[lambda s: ~s].index.tolist()

    churn_list = churn_ids(df_first, df_eshows, df_new,
                           dias=45,
                           cutoff=custom_range[1] if custom_range else None)

    # ------------------------------------------------------------------ #
    # 4) Lifetime real, histórico e ajustado                             #
    # ------------------------------------------------------------------ #
    df_life = (
        df_first[["Id da Casa", "EarliestShow"]]
        .merge(df_last[["Id da Casa", "LastShow"]], on="Id da Casa", how="inner")
        .loc[lambda d: d["Id da Casa"].isin(novos_ids)]
    )
    df_life["LifetimeDays"]   = (df_life["LastShow"] - df_life["EarliestShow"]).dt.days.clip(lower=0)
    df_life["LifetimeMonths"] = df_life["LifetimeDays"] / 30.0
    df_life["IsChurned"]      = df_life["Id da Casa"].isin(churn_list)

    df_hist = df_first[df_first["EarliestShow"] >= "2022-04-01"] \
        .merge(df_last, on="Id da Casa")
    df_hist["LifetimeMonths"] = (
        (df_hist["LastShow"] - df_hist["EarliestShow"]).dt.days / 30.0
    )
    lifetime_hist = df_hist["LifetimeMonths"].mean() if not df_hist.empty else 0

    df_life["AdjLifetime"] = df_life.apply(
        lambda r: r["LifetimeMonths"] if r["IsChurned"]
        else max(r["LifetimeMonths"], lifetime_hist),
        axis=1
    )

    # ------------------------------------------------------------------ #
    # 5) Faturamento mensal + LTV por palco                              #
    # ------------------------------------------------------------------ #
    def full_months(s, e):
        rd = relativedelta(e, s)
        months = rd.years * 12 + rd.months
        return max(months - (e.day < s.day), 0)

    df_dates = (
        df_per[df_per["Id da Casa"].isin(novos_ids)]
        .groupby("Id da Casa")["Data do Show"]
        .agg(["min", "max"]).reset_index()
        .rename(columns={"min": "FirstShow", "max": "LastShow"})
    )

    df_fat = (
        df_shows.groupby("Id da Casa")["Faturamento"].sum().reset_index()
        .merge(df_dates, on="Id da Casa", how="left")
        .merge(df_life,  on="Id da Casa", how="inner", suffixes=("", "_life"))
    )

    # ---------- salvaguarda: garante FirstShow / LastShow ---------------
    for col in ["FirstShow", "LastShow"]:
        if col not in df_fat.columns:
            # pega a primeira coluna que contenha o nome (ex.: 'LastShow_life')
            matches = [c for c in df_fat.columns if c.lower().startswith(col.lower())]
            df_fat[col] = df_fat[matches[0]] if matches else pd.NaT
    # --------------------------------------------------------------------

    df_fat["MesesDiv"] = df_fat.apply(
        lambda r: max(full_months(r["FirstShow"], r["LastShow"]), 1),
        axis=1
    )
    df_fat["FatMensal"] = df_fat["Faturamento"] / df_fat["MesesDiv"]

    def _ltv(row):
        if row["IsChurned"] and row["LifetimeMonths"] < 0.1:
            return row["Faturamento"]
        return row["FatMensal"] * row["AdjLifetime"]

    df_fat["LTV"] = df_fat.apply(_ltv, axis=1)

    ltv_mean   = df_fat["LTV"].mean()
    fat_mensal = df_fat["FatMensal"].mean()
    life_adj   = df_fat["AdjLifetime"].mean()

    # ------------------------------------------------------------------ #
    # 6) CAC                                                             #
    # ------------------------------------------------------------------ #
    # O CAC agora virá de get_cac_variables
    cac_vars = get_cac_variables(
        ano=ano,
        periodo=periodo,
        mes=mes,
        custom_range=custom_range,
        df_custosabertos_global=df_custosabertos,
        df_eshows_global=df_eshows,
        df_pessoas_global=df_pessoas,
        df_casas_earliest_global=df_first # df_first é o df_casas_earliest
    )

    cac_total_calculado = cac_vars.get("variables_values", {}).get("Total Custos Mkt & Vendas", 0.0)
    # cac_medio_mensal_calculado = cac_vars.get("variables_values", {}).get("CAC Médio Mensal", 0.0) # Não existe mais no retorno de get_cac_variables
    
    # Mantemos a lógica de novos_ct para o denominador do CAC por cliente
    if novos_ct == 0:
        # Se não há novos palcos, LTV/CAC não pode ser calculado de forma significativa
        # ou o CAC por cliente seria infinito. Retornamos False para fallback.
        return ({"periodo": label_periodo_calc, "resultado": "0", "status": "controle",
                 "variables_values": {"Novos Palcos": novos_ct, "LTV": float(ltv_mean), "CAC Por Cliente": 0}}, False)

    cac_por_cliente = cac_total_calculado / novos_ct if novos_ct > 0 else 0.0
    
    # Verifica se o CAC total é zero, indicando dados insuficientes para o cálculo do CAC.
    if cac_total_calculado == 0 and novos_ct > 0 : # Se tem novos clientes mas CAC é zero, pode ser falta de dados de custo
        return ({"periodo": label_periodo_calc, "resultado": "0", "status": "controle",
                 "variables_values": {
                     "Novos Palcos": novos_ct, 
                     "LTV": float(ltv_mean), 
                     "CAC Por Cliente": float(cac_por_cliente),
                     "Debug": "CAC total foi zero, indicando possível falta de dados de custos."
                     }}, False)


    # ------------------------------------------------------------------ #
    # 7) LTV/CAC + status                                                #
    # ------------------------------------------------------------------ #
    ratio  = ltv_mean / cac_por_cliente if cac_por_cliente else 0
    status = "bom" if ratio >= 3 else "ruim" if ratio < 1 else "controle"

    resultado = {
        "periodo": label_periodo_calc,
        "resultado": formatar_valor_utils(ratio, "numero_2f"),
        "status": status,
        "variables_values": {
            "LTV": float(ltv_mean),
            "CAC Por Cliente": float(cac_por_cliente),
            "CAC Total Acumulado": float(cac_total_calculado), # Usando o CAC de get_cac_variables
            # "CAC Médio Mensal": float(cac_medio_mensal_calculado), # Removido pois não está mais no get_cac_variables
            "LTV/CAC": float(ratio),
            "Novos Palcos": int(novos_ct),
            "Churn": int(len(churn_list)),
            "Lifetime Médio Histórico (meses)": float(lifetime_hist),
            "Lifetime Médio Ajustado (meses)": float(life_adj),
            "Faturamento Médio Mensal": float(fat_mensal),
        },
    }
    gc.collect()
    return resultado, True

# --------------------------------------------------------------------------- #
# 2) Função pública – com fallback                                            #
# --------------------------------------------------------------------------- #
def get_ltv_cac_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
    df_base2_global=None, # Mantido para compatibilidade, mas CAC não vem mais daqui diretamente
    df_casas_earliest_global=None,
    df_casas_latest_global=None,
    df_custosabertos_global=None, # NOVO
    df_pessoas_global=None      # NOVO
) -> dict:
    """
    Mesma assinatura de antes, mas agora:
      • Tenta o intervalo original.
      • Se faltar dados, recua seguindo:
          Trimestre → Bimestre → Mês → Trimestre anterior → …
          YTD       → recua mês a mês até encontrar dados.
          Mês Aberto→ recua mês a mês.
      • Para evitar loop infinito, limita a 24 tentativas.
    """
    MAX_TENTATIVAS = 24

    # Carrega bases apenas uma vez para reutilizar
    df_eshows = df_eshows_global if df_eshows_global is not None else carregar_base_eshows()
    df_base2  = df_base2_global  if df_base2_global  is not None else carregar_base2() # Mantido, pode ser usado por outras partes do fallback ou debug
    df_custosabertos = df_custosabertos_global if df_custosabertos_global is not None else carregar_custosabertos() # NOVO
    df_pessoas = df_pessoas_global if df_pessoas_global is not None else carregar_pessoas() # NOVO


    df_casas_earliest = (
        df_casas_earliest_global
        if df_casas_earliest_global is not None
        else df_eshows.groupby("Id da Casa")["Data do Show"]
             .min()
             .reset_index()
             .rename(columns={"Data do Show": "EarliestShow"})
    )

    df_casas_latest = (
        df_casas_latest_global
        if df_casas_latest_global is not None
        else df_eshows.groupby("Id da Casa")["Data do Show"]
             .max()
             .reset_index()
             .rename(columns={"Data do Show": "LastShow"})
    )

    tentativas = 0
    ano_cur, periodo_cur, mes_cur = ano, periodo, mes
    custom_range_cur = custom_range # Mantém o custom_range original para a primeira tentativa
    label_final = "Sem dados" # Label padrão caso nada seja encontrado

    # Para a primeira tentativa, se custom_range for fornecido, ele tem precedência para o label.
    if custom_range_cur:
        try:
            label_final = f"{pd.to_datetime(custom_range_cur[0]):%d/%m/%y} – {pd.to_datetime(custom_range_cur[1]):%d/%m/%y}"
        except: # Fallback se custom_range não for datelike
            # Cria um DataFrame temporário apenas para obter o nome do período
            temp_df_label = pd.DataFrame({'Data': [pd.to_datetime(custom_range_cur[0])]}) if custom_range_cur and custom_range_cur[0] else pd.DataFrame()
            label_final = mes_nome_intervalo(temp_df_label, periodo_cur if periodo_cur != "custom-range" else "Mês Aberto")


    elif periodo_cur: # Se não há custom_range, usa o período nominal
         # Cria um DataFrame temporário apenas para obter o nome do período
        temp_start_date = get_period_start(ano_cur, periodo_cur, mes_cur)
        temp_df_label = pd.DataFrame({'Data': [temp_start_date]}) if temp_start_date else pd.DataFrame()
        label_final = mes_nome_intervalo(temp_df_label, periodo_cur)


    periodo_original = periodo # Guarda o tipo de período original para lógica de fallback

    while tentativas < MAX_TENTATIVAS:
        # ---------- tenta cálculo ------------------------------------------------
        # Na primeira tentativa (tentativas == 0), custom_range_cur é o custom_range original (pode ser None).
        # Nas tentativas subsequentes, custom_range_cur será definido pela lógica de fallback.
        
        # Atualiza label_final ANTES da chamada, refletindo o que será tentado
        if custom_range_cur:
             try:
                label_final = f"{pd.to_datetime(custom_range_cur[0]):%d/%m/%y} – {pd.to_datetime(custom_range_cur[1]):%d/%m/%y}"
             except:
                # Usa o ano_cur e mes_cur do fallback para gerar o label
                temp_start_date = get_period_start(ano_cur, periodo_cur, mes_cur)
                temp_df_label = pd.DataFrame({'Data': [temp_start_date]}) if temp_start_date else pd.DataFrame()
                label_final = mes_nome_intervalo(temp_df_label, periodo_cur)
        elif periodo_cur:
            temp_start_date = get_period_start(ano_cur, periodo_cur, mes_cur) # Recalcula com ano_cur, mes_cur atuais
            temp_df_label = pd.DataFrame({'Data': [temp_start_date]}) if temp_start_date else pd.DataFrame()
            label_final = mes_nome_intervalo(temp_df_label, periodo_cur)


        resultado, ok = _compute_ltv_cac(
            ano_cur, periodo_cur, mes_cur, custom_range_cur, # Passa custom_range_cur
            df_eshows, df_base2, df_casas_earliest, df_casas_latest,
            df_custosabertos, df_pessoas
        )
        if ok:
            resultado["periodo"] = label_final # Garante que o label do resultado seja o que foi efetivamente testado e deu certo
            return resultado

        # ---------- fallback só acontece se 'ok' for False ---------------------
        tentativas += 1 # Incrementa tentativas aqui, pois a tentativa atual falhou.
        
        # Lógica de fallback original restaurada
        if "Trimestre" in periodo_original: # Usa periodo_original para guiar o tipo de fallback
            tri_str = periodo_cur.split("°")[0]
            if not tri_str.isdigit(): # Checagem de segurança
                break # Sai do loop se o formato do trimestre for inesperado
            tri = int(tri_str)
            
            if custom_range_cur is None: # Estava tentando o trimestre nominal completo
                m1_tri = (tri - 1) * 3 + 1
                m2_tri = m1_tri + 1
                custom_range_cur = (date(ano_cur, m1_tri, 1), _last_day(ano_cur, m2_tri))
                # Atualiza periodo_cur para refletir o bimestre, para que o label seja gerado corretamente
                periodo_cur = f"{calendar.month_abbr[m1_tri]}-{calendar.month_abbr[m2_tri]} {ano_cur}"
            else:
                current_start, current_end = custom_range_cur
                m1_tri_nominal = (tri - 1) * 3 + 1 # Mês inicial do trimestre nominal original
                m2_tri_nominal = m1_tri_nominal + 1
                m3_tri_nominal = m1_tri_nominal + 2

                # Verifica se estava tentando o bimestre do trimestre nominal
                if current_start == date(ano_cur, m1_tri_nominal, 1) and current_end == _last_day(ano_cur, m2_tri_nominal):
                    custom_range_cur = (date(ano_cur, m3_tri_nominal, 1), _last_day(ano_cur, m3_tri_nominal))
                    periodo_cur = f"{calendar.month_abbr[m3_tri_nominal]} {ano_cur}" # Atualiza para o mês individual
                else: # Estava tentando o mês individual ou um custom_range não padrão, ou o trimestre completo falhou antes
                      # Recua para o trimestre anterior completo
                    if tri == 1:
                        tri = 4
                        ano_cur -= 1
                    else:
                        tri -= 1
                    periodo_cur = f"{tri}° Trimestre" # Mantém periodo_cur como tipo Trimestre para label
                    custom_range_cur = None # Tentar o trimestre nominal completo na próxima iteração
            
        elif periodo_original.upper() in {"YTD", "Y T D", "ANO CORRENTE"}:
            if mes_cur is None or mes_cur <= 1: # Trata mes_cur None como se fosse Janeiro para recuo
                ano_cur -= 1
                mes_cur = 12
            else:
                mes_cur -= 1
            custom_range_cur = (date(ano_cur, 1, 1), _last_day(ano_cur, mes_cur))
            periodo_cur = "YTD" # Mantém o tipo de período para o label ser gerado corretamente
            
        elif periodo_original == "custom-range":
            break # Falha em custom-range original, não há fallback padrão

        else:  # Mês Aberto ou Ano Completo
            if periodo_original == "Ano Completo":
                ano_cur -= 1
                custom_range_cur = (date(ano_cur, 1, 1), date(ano_cur, 12, 31))
                periodo_cur = "Ano Completo" # Mantém o tipo de período para label
            elif periodo_original == "Mês Aberto":
                 if mes_cur is None: 
                     ano_cur -=1
                     mes_cur = 12
                 else:
                    mes_cur -= 1
                    if mes_cur == 0:
                        ano_cur -= 1
                        mes_cur = 12
                 custom_range_cur = (date(ano_cur, mes_cur, 1), _last_day(ano_cur, mes_cur))
                 periodo_cur = "Mês Aberto" # Mantém o tipo de período para label

        if ano_cur < datetime.now().year - 10: # Limite arbitrário para evitar loops muito longos
            break

    # Se chegar aqui, não encontrou dados
    return {
        "periodo": label_final, # Usa o último label de tentativa que foi configurado
        "resultado": "0",
        "status": "controle",
        "variables_values": {
            "LTV": 0,
            "CAC Por Cliente": 0,
            "LTV/CAC": 0,
            "Novos Palcos": 0,
            "Debug": "Máximo de tentativas de fallback atingido sem dados suficientes."
        },
    }

# ======================================================================
# KPI: Score Médio do Show  (["eshows"])
# ======================================================================
def get_score_medio_show_variables(      # ← nome agora bate com o import
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
) -> dict:
    """
    • Score Médio = (Soma das notas) / (Total de shows avaliados)
    • Considera apenas registros cujo campo 'Avaliação' (ou 'NOTA') não seja nulo.
    """
    # --- 1) Carrega base -------------------------------------------------
    df_eshows = (
        df_eshows_global.copy()
        if df_eshows_global is not None
        else carregar_base_eshows().copy()
    )
    if df_eshows is not None:
        df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    # --- 2) Filtra período principal ------------------------------------
    df_periodo = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    label_periodo = mes_nome_intervalo(df_periodo, periodo)

    if df_periodo.empty or "Avaliação" not in df_periodo.columns:
        return {
            "periodo": label_periodo,
            "resultado": "0.00",
            "status": "controle",
            "variables_values": {
                "Soma das Avaliações": 0,
                "Total de Shows Avaliados": 0,
                "Score Médio": 0
            },
        }

    # --- 3) Limpa e calcula ---------------------------------------------
    aval = pd.to_numeric(df_periodo["Avaliação"], errors="coerce")
    aval_validas = aval.dropna()
    total_shows = len(aval_validas)

    media = 0.0 if total_shows == 0 else aval_validas.sum() / total_shows
    status, icon = get_kpi_status("Score Médio do Show", media, kpi_descriptions)

    return {
        "periodo": label_periodo,
        "resultado": f"{media:.2f}",
        "status": status,
        "icon": icon,
        "variables_values": {
            "Soma das Avaliações": float(aval_validas.sum()),
            "Total de Shows Avaliados": total_shows,
            "Score Médio": float(media)
        },
    }

# ======================================================================
# KPI: Churn $
# ======================================================================
def _churn_ids(df_eshows: pd.DataFrame,
               dias_sem_show: int,
               start_periodo: pd.Timestamp,
               end_periodo: pd.Timestamp,
               uf: str | None = None) -> list[str]:
    """
    Devolve lista de Id da Casa que churnaram dentro do intervalo analisado.
    Reaproveita a mesma lógica que já usa no LTV/CAC.
    """
    if uf and uf != "BR":
        df_eshows = df_eshows[df_eshows["Estado"] == uf]

    df_last = (
        df_eshows
        .groupby("Id da Casa")["Data do Show"]
        .max()
        .reset_index(name="LastShow")
    )
    df_last["churn_date"] = df_last["LastShow"] + timedelta(days=dias_sem_show)

    # Candidatos cujo churn_date caiu até o fim do período
    df_cand = df_last[df_last["churn_date"] <= end_periodo]
    if df_cand.empty:
        return []

    # Verifica se o cliente voltou
    df_shows_cand = df_eshows[df_eshows["Id da Casa"].isin(df_cand["Id da Casa"])]
    merged = pd.merge(
        df_cand[["Id da Casa", "LastShow"]],
        df_shows_cand[["Id da Casa", "Data do Show"]],
        on="Id da Casa", how="left"
    )
    merged["Retornou"] = merged["Data do Show"] > merged["LastShow"]
    df_status = merged.groupby("Id da Casa")["Retornou"].any().reset_index()

    churn_ids = df_status[~df_status["Retornou"]]["Id da Casa"].tolist()

    # Mantém só os churns cujo churn_date caiu dentro do intervalo analisado
    churn_final = df_last[df_last["Id da Casa"].isin(churn_ids)]
    churn_final = churn_final[
        (churn_final["churn_date"] >= start_periodo) &
        (churn_final["churn_date"] <= end_periodo)
    ]
    return churn_final["Id da Casa"].tolist()

def get_churn_valor_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
    start_date=None,
    end_date=None,
    uf: str | None = None,
    dias_sem_show: int = 45,
    janela_media_meses: int = 3,
):
    """
    KPI – Churn Valor %
    (valor perdido ÷ faturamento do período) × 100
    """
    # --------------------------------------------------------- #
    # 1) Carrega base                                           #
    # --------------------------------------------------------- #
    if df_eshows_global is not None:
        df_eshows = df_eshows_global.copy()
    else:
        df_eshows = carregar_base_eshows().copy()

    if df_eshows is None or df_eshows.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    # --------------------------------------------------------- #
    # 2) Define intervalo                                       #
    # --------------------------------------------------------- #
    date_range     = custom_range if custom_range else (start_date, end_date)
    start_periodo  = get_period_start(ano, periodo, mes, date_range)
    end_periodo    = get_period_end  (ano, periodo, mes, date_range)

    df_periodo = filtrar_periodo_principal(df_eshows, ano, periodo, mes, date_range)
    label_periodo = mes_nome_intervalo(df_periodo, periodo)

    if df_periodo.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00%",
            "status": "controle",
            "variables_values": {},
        }

    # --------------------------------------------------------- #
    # 3) Valor total faturado no período                        #
    # --------------------------------------------------------- #
    df_periodo[COLUNAS_FATURAMENTO] = (
        df_periodo[COLUNAS_FATURAMENTO]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )
    df_periodo["Faturamento"] = df_periodo[COLUNAS_FATURAMENTO].sum(axis=1)
    faturamento_periodo = df_periodo["Faturamento"].sum()

    if faturamento_periodo == 0:
        faturamento_periodo = 1e-9  # evita divisão por zero, mas mantém lógica

    # --------------------------------------------------------- #
    # 4) Identifica churns e calcula valor perdido              #
    # --------------------------------------------------------- #
    churn_ids = _churn_ids(
        df_eshows=df_eshows,
        dias_sem_show=dias_sem_show,
        start_periodo=start_periodo,
        end_periodo=end_periodo,
        uf=uf,
    )

    if not churn_ids:
        churn_valor_pct = 0.0
        receita_perdida = 0.0
    else:
        df_churn = df_eshows[df_eshows["Id da Casa"].isin(churn_ids)].copy()
        df_churn = df_churn[df_churn["Data do Show"] < end_periodo]

        df_churn[COLUNAS_FATURAMENTO] = (
            df_churn[COLUNAS_FATURAMENTO]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
        )
        df_churn["Faturamento"] = df_churn[COLUNAS_FATURAMENTO].sum(axis=1)

        def _run_rate(sub: pd.DataFrame) -> float:
            last_show = sub["Data do Show"].max()
            ini_win   = last_show - relativedelta(months=janela_media_meses)
            rec       = sub[sub["Data do Show"] >= ini_win]
            total     = rec["Faturamento"].sum()
            meses     = max(
                (last_show.year - ini_win.year) * 12 + (last_show.month - ini_win.month) + 1,
                1,
            )
            return total / meses if total else 0.0

        run_rate = (
            df_churn.groupby("Id da Casa")
                    .apply(_run_rate)
                    .rename("RunRateMensal")
                    .reset_index()
        )
        receita_perdida = run_rate["RunRateMensal"].sum()
        churn_valor_pct = (receita_perdida / faturamento_periodo) * 100

    # --------------------------------------------------------- #
    # 5) Status                                                 #
    # --------------------------------------------------------- #
    status, _icon = get_kpi_status("Churn em Valor", churn_valor_pct, kpi_descriptions)

    # --------------------------------------------------------- #
    # 6) Payload                                                #
    # --------------------------------------------------------- #
    return {
        "variables_values": {
            "Estabelecimentos Perdidos": len(churn_ids),
            "Churn em Valor (R$)": receita_perdida,     # ← total perdido, sem divisão
            "Faturamento no Período": faturamento_periodo,
            "Churn em Valor (%)": churn_valor_pct,      # ← guardado para o modal
        },
        "periodo": label_periodo,
        "resultado": f"{churn_valor_pct:.2f}%",         # ← card mostra só o %
        "status": status,
    }

# --------------------------------------------------------------------------- #
# KPI: Receita por Pessoal  •  Faturamento ÷ Custo Total de Pessoas           #
# --------------------------------------------------------------------------- #
def get_receita_pessoal_variables(
    ano: int,
    periodo: str,
    mes: int,
    custom_range=None,
    df_eshows_global=None,
    df_base2_global=None,
    start_date=None,
    end_date=None,
):
    """
    KPI – Receita por Pessoal
    (Faturamento do período) ÷ (Custo total de Equipe interna no período)
    """
    # --------------------------------------------------------- #
    # 1) Bases                                                  #
    # --------------------------------------------------------- #
    df_eshows = df_eshows_global.copy() if df_eshows_global is not None else carregar_base_eshows().copy()
    df_base2  = df_base2_global.copy()  if df_base2_global  is not None else carregar_base2().copy()

    if df_eshows.empty or df_base2.empty:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00",
            "status": "controle",
            "variables_values": {},
        }

    df_eshows = df_eshows.loc[:, ~df_eshows.columns.duplicated()]

    # --------------------------------------------------------- #
    # 2) Intervalo analisado                                    #
    # --------------------------------------------------------- #
    date_range     = custom_range if custom_range else (start_date, end_date)
    start_periodo  = get_period_start(ano, periodo, mes, date_range)
    end_periodo    = get_period_end  (ano, periodo, mes, date_range)

    df_periodo = filtrar_periodo_principal(df_eshows, ano, periodo, mes, date_range)
    label_periodo = mes_nome_intervalo(df_periodo, periodo)

    if df_periodo.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00",
            "status": "controle",
            "variables_values": {},
        }

    # --------------------------------------------------------- #
    # 3) Faturamento total do período                           #
    # --------------------------------------------------------- #
    df_periodo[COLUNAS_FATURAMENTO] = (
        df_periodo[COLUNAS_FATURAMENTO]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )
    df_periodo["Faturamento"] = df_periodo[COLUNAS_FATURAMENTO].sum(axis=1)
    faturamento_total = df_periodo["Faturamento"].sum()

    # --------------------------------------------------------- #
    # 4) Custo total de pessoas (Equipe)                        #
    # --------------------------------------------------------- #
    df_b2_per = filtrar_periodo_principal(df_base2, ano, periodo, mes, date_range)
    if df_b2_per.empty or "Equipe" not in df_b2_per.columns:
        custo_pessoas_total = 0.0
    else:
        df_b2_per["Equipe"] = pd.to_numeric(df_b2_per["Equipe"], errors="coerce").fillna(0)
        custo_pessoas_total = df_b2_per["Equipe"].sum()

    # --------------------------------------------------------- #
    # 5) Receita por Pessoal                                    #
    # --------------------------------------------------------- #
    receita_por_pessoal = faturamento_total / custo_pessoas_total if custo_pessoas_total else 0.0

    # --------------------------------------------------------- #
    # 6) Status                                                 #
    # --------------------------------------------------------- #
    status, _icon = get_kpi_status("Receita por Pessoal", receita_por_pessoal, kpi_descriptions)

    # --------------------------------------------------------- #
    # 7) Payload                                                #
    # --------------------------------------------------------- #
    return {
        "variables_values": {
            "Faturamento no Período": faturamento_total,
            "Custo Equipe no Período": custo_pessoas_total,
            "Receita por Pessoal": receita_por_pessoal,
        },
        "periodo": label_periodo,
        "resultado": formatar_valor_utils(receita_por_pessoal, "numero_2f"),
        "status": status,
    }

# ===========================================================================
# KPI: CSAT Artistas (base: npsartistas)
# ===========================================================================
def get_csat_artistas_variables(
    ano: int,
    periodo: str,
    mes: int | None,
    custom_range=None,
    df_nps_global=None,
) -> dict:
    """
    • CSAT médio dos artistas (escala 1-5, duas casas decimais)
    • Usa rollback até encontrar um intervalo com dados, como no NPS.
    """
    from .modulobase import carregar_npsartistas
    COL_CSAT = "CSAT Eshows"          # nome exato da coluna na base
    df_nps = df_nps_global.copy() if df_nps_global is not None else carregar_npsartistas().copy()

    # Garantir que a coluna Data está em datetime
    if "Data" in df_nps.columns:
        df_nps["Data"] = pd.to_datetime(df_nps["Data"], errors="coerce")

    if df_nps.empty or COL_CSAT not in df_nps.columns:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00",
            "status": "controle",
            "variables_values": {"CSAT Artistas": 0.0},
        }

    # --- tentativa de achar período válido --------------------------------
    df_sel, label_periodo = _buscar_periodo_valido_nps(
        df_nps, ano, periodo, mes, COL_CSAT
    )

    if df_sel.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00",
            "status": "controle",
            "variables_values": {"CSAT Artistas": 0.0},
        }

    media = pd.to_numeric(df_sel[COL_CSAT], errors="coerce").dropna().mean()
    media = float(round(media, 2))  # duas casas
    st, icon = get_kpi_status("CSAT Artistas", media, kpi_descriptions)

    return {
        "periodo": label_periodo,
        "resultado": f"{media:.2f}",
        "status": st,
        "icon": icon,
        "variables_values": {"CSAT Artistas": media},
    }

# ===========================================================================
# KPI: CSAT Operação (base: npsartistas)
# ===========================================================================
def get_csat_operacao_variables(
    ano: int,
    periodo: str,
    mes: int | None,
    custom_range=None,
    df_nps_global=None,
) -> dict:
    """
    • CSAT médio da operação (escala 1-5, duas casas decimais)
    • Soma as notas de operadores válidos (1 e 2), ignora \'Nenhum\', \'Não\', etc.
    • Usa rollback até encontrar um intervalo com dados, como no NPS.
    """
    from .modulobase import carregar_npsartistas
    COL_CSAT1 = "CSAT Operador 1"
    COL_CSAT2 = "CSAT Operador 2"
    COL_OP1 = "Operador 1"
    COL_OP2 = "Operador 2"
    IGNORAR = {"Nenhum", "Não", "Outro", "Não me Lembro", "", None}

    df_nps = df_nps_global.copy() if df_nps_global is not None else carregar_npsartistas().copy()

    # Garantir que a coluna Data está em datetime
    if "Data" in df_nps.columns:
        df_nps["Data"] = pd.to_datetime(df_nps["Data"], errors="coerce")

    if df_nps.empty or COL_CSAT1 not in df_nps.columns or COL_CSAT2 not in df_nps.columns:
        return {
            "periodo": "Sem dados",
            "resultado": "0.00",
            "status": "controle",
            "variables_values": {"CSAT Operação": 0.0},
        }

    # Cria coluna auxiliar com todos os CSATs válidos
    csat_todos = []

    for _, row in df_nps.iterrows():
        op1 = str(row.get(COL_OP1, "")).strip()
        op2 = str(row.get(COL_OP2, "")).strip()
        csat1 = row.get(COL_CSAT1)
        csat2 = row.get(COL_CSAT2)

        if op1 not in IGNORAR and pd.notnull(csat1):
            csat_todos.append(float(csat1))
        if op2 not in IGNORAR and pd.notnull(csat2):
            csat_todos.append(float(csat2))

    # Cria DataFrame auxiliar para o rollback
    df_aux = pd.DataFrame({"Data": df_nps["Data"], "CSAT Operação": None})
    df_aux["CSAT Operação"] = None

    idx_validos = []

    for i, (_, row) in enumerate(df_nps.iterrows()):
        op1 = str(row.get(COL_OP1, "")).strip()
        op2 = str(row.get(COL_OP2, "")).strip()
        csat1 = row.get(COL_CSAT1)
        csat2 = row.get(COL_CSAT2)

        if op1 not in IGNORAR and pd.notnull(csat1):
            idx_validos.append(i)
        elif op2 not in IGNORAR and pd.notnull(csat2):
            idx_validos.append(i)

    df_aux = df_nps.loc[idx_validos, ["Data"]].copy()
    df_aux["CSAT"] = [
        float(row[COL_CSAT1]) if str(row[COL_OP1]).strip() not in IGNORAR and pd.notnull(row[COL_CSAT1])
        else float(row[COL_CSAT2]) if str(row[COL_OP2]).strip() not in IGNORAR and pd.notnull(row[COL_CSAT2])
        else None
        for _, row in df_nps.loc[idx_validos].iterrows()
    ]

    # Rollback: procurar o período com CSATs válidos
    df_sel, label_periodo = _buscar_periodo_valido_nps(
        df_aux.rename(columns={"CSAT": "CSAT Operação"}),  # adapta coluna
        ano,
        periodo,
        mes,
        "CSAT Operação"
    )

    if df_sel.empty:
        return {
            "periodo": label_periodo,
            "resultado": "0.00",
            "status": "controle",
            "variables_values": {"CSAT Operação": 0.0},
        }

    media = pd.to_numeric(df_sel["CSAT Operação"], errors="coerce").dropna().mean()
    media = float(round(media, 2))
    st, icon = get_kpi_status("CSAT Operação", media, kpi_descriptions)

    return {
        "periodo": label_periodo,
        "resultado": f"{media:.2f}",
        "status": st,
        "icon": icon,
        "variables_values": {
            "CSAT Operação": media,
            "Total Avaliações": len(df_sel)
        },
    }

