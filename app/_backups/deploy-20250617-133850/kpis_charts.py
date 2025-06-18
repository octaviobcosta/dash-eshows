# kpi_charts.py
# --------------------------------------------------------------------------- #
# Gráficos de evolução mensal dos KPIs                                        #
# --------------------------------------------------------------------------- #
import calendar
from datetime import datetime
import plotly.graph_objects as go
import pandas as pd
import logging
from .utils import parse_valor_formatado      # ← função única, já corrigida
from .hist import _format_tempo_casa # << IMPORTADO DE HIST
from .config_data import HIST_KPI_MAP
from .mem_utils import log_mem
import numpy as np

logger = logging.getLogger(__name__)

# --- paleta mínima de apoio --------------------------------------------------
COLOR_POS   = "#29B388"   # verde
COLOR_NEG   = "#F57C7C"   # vermelho
COLOR_NEUTR = "#FC4F22"   # laranja principal
BG_COLOR    = "rgba(0,0,0,0)"


# --------------------------------------------------------------------------- #
# 1) Captura dos dados históricos (até 12 pontos)                              #
# --------------------------------------------------------------------------- #
@log_mem("kpi_hist_data")
def kpi_hist_data(kpi_name: str):
    """
    Retorna (labels, values) dos 12 últimos pontos históricos do KPI.
    """
    logger.debug("\n--- [kpi_hist_data] INICIANDO para KPI: '%s' ---", kpi_name)
    
    if HIST_KPI_MAP is None:
        logger.debug("[kpi_hist_data] ERRO FATAL: HIST_KPI_MAP importado de config_data é None.")
        return None, None
    if not isinstance(HIST_KPI_MAP, dict):
        logger.debug("[kpi_hist_data] ERRO FATAL: HIST_KPI_MAP importado de config_data não é um dicionário, é %s.", type(HIST_KPI_MAP))
        return None, None
    if not HIST_KPI_MAP:
        logger.debug("[kpi_hist_data] ERRO FATAL: HIST_KPI_MAP importado de config_data está VAZIO.")
        return None, None

    hist = HIST_KPI_MAP.get(kpi_name)
    
    # Log para verificar se o KPI específico foi encontrado e algumas chaves do mapa
    logger.debug("[kpi_hist_data] Verificando '%s'. Encontrado em HIST_KPI_MAP (de config_data): %s. Algumas chaves do mapa: %s",
                 kpi_name, hist is not None, list(HIST_KPI_MAP.keys())[:5])

    if not hist:
        logger.debug("[kpi_hist_data] KPI '%s' não encontrado no HIST_KPI_MAP importado de config_data. Retornando None, None.", kpi_name)
        return None, None

    raw = hist.get("raw_data")
    if not raw:
        logger.debug("[kpi_hist_data] KPI: '%s', 'raw_data' não encontrado ou vazio em hist. Verificando 'series' como fallback.", kpi_name)
        raw = hist.get("series")

    if not raw or not isinstance(raw, dict):
        logger.debug("[kpi_hist_data] KPI: '%s', nem 'raw_data' nem 'series' encontrados ou não são dict. Conteúdo de hist: %s. Retornando None, None.", kpi_name, hist)
        return None, None
    
    logger.debug("[kpi_hist_data] KPI: '%s', raw_data obtido: %s, %s items.", kpi_name, type(raw), len(raw) if isinstance(raw, dict) else 'N/A')

    items  = list(raw.items())[-12:]
    if not items:
        logger.debug("[kpi_hist_data] KPI: '%s', raw_data foi encontrado mas está vazio após pegar os últimos 12 items. Retornando None, None.", kpi_name)
        return None, None
        
    labels = [pd.to_datetime(d).strftime("%b/%y") for d, _ in items]
    
    values = []
    for i, (date_str, v_orig) in enumerate(items):
        current_value = None
        if v_orig is None:
            current_value = None
        elif isinstance(v_orig, str) and v_orig.strip().upper() == 'N/A':
            current_value = None
        elif isinstance(v_orig, (int, float)) and pd.isna(v_orig):
            current_value = None
        elif isinstance(v_orig, (int, float)):
            current_value = float(v_orig)
        elif isinstance(v_orig, str):
            parsed = parse_valor_formatado(v_orig)
            if isinstance(parsed, (int, float)):
                current_value = float(parsed)
        values.append(current_value)

    logger.debug("[kpi_hist_data] FINAL - KPI: '%s', Labels: %s, Values: %s\n---", kpi_name, labels, values)
    return labels, values


# --------------------------------------------------------------------------- #
# 2) Função principal: generate_kpi_figure                                     #
# --------------------------------------------------------------------------- #
@log_mem("generate_kpi_figure")
def generate_kpi_figure(
    kpi_name: str,
    ano: int,
    mes: int,
    dashboard,
    chart_type: str = "auto",
    format_type: str = "numero",
    height: int = 540,
    custom_color: str | None = None,
    animated: bool = False
):
    """
    Gráfico evolutivo (até 12 meses) do KPI.
    1º) Usa dados prontos em HIST_KPI_MAP; se não houver, calcula on-the-fly.
    2º) Se format_type ficar em "numero", tenta inferir:
        · palavras–chave de dinheiro → "monetario"
        · contém '%' ou 'taxa/rate' → "percentual"
    """
    # ------------------------------------------------------------------ #
    # 0) Inferir formato quando não especificado                         #
    # ------------------------------------------------------------------ #
    if format_type == "numero":
        nome_low = kpi_name.lower()
        if 'ticket' in nome_low or any(p in nome_low for p in (
            "custo", "fatur", "lucro", "gmv",
            "erro", "perda", "inadimpl", "receita"
        )):
            format_type = "monetario"
        elif "%" in kpi_name or any(p in nome_low for p in ("taxa", "rate")):
            format_type = "percentual"

    # <<<<<<< FORÇAR FORMATO PARA KPIS ESPECÍFICOS >>>>>>>>>
    if kpi_name == "Ticket Médio":
        format_type = "monetario"
    elif kpi_name == "Take Rate GMV":
        format_type = "percentual"
    # Adicionar outros elifs se necessário para outros KPIs com problemas
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    # ------------------------------------------------------------------ #
    # 1) Histórico pronto?                                               #
    # ------------------------------------------------------------------ #
    labels, values = kpi_hist_data(kpi_name)
    if not labels or not values:
        # Retorna figura vazia com mensagem
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados disponíveis para o gráfico",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#888")
        )
        fig.update_layout(paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR, height=height)
        return fig
    df_hist = pd.DataFrame({"label": labels, "valor": values})

    # <<<< MODIFICAÇÃO IMPORTANTE AQUI >>>>
    if format_type == "percentual":
        df_hist["valor"] = df_hist["valor"] * 100
    # <<<< FIM DA MODIFICAÇÃO >>>>

    # ------------------------------------------------------------------ #
    # 3) Cálculos de variação M/M                                        #
    # ------------------------------------------------------------------ #
    df_hist["prev_val"]  = df_hist["valor"].shift(1) # Agora prev_val também estará na escala 0-100 para percentuais
    df_hist["cres_abs"]  = (df_hist["valor"] - df_hist["prev_val"]).fillna(0)
    
    # Recalcular cres_pct com base nos valores possivelmente escalados (0-100)
    # Se o valor e prev_val forem ambos 0, cres_pct é 0.
    # Se prev_val for 0 e valor não, é infinito (tratado como NaN -> 0 com fillna).
    # Se prev_val não for 0, cálculo normal.
    cres_pct_np_array = np.where(
        df_hist["prev_val"] == 0,
        np.where(df_hist["valor"] == 0, 0, np.nan), # Trata 0/0 como 0, X/0 como NaN
        (df_hist["valor"] - df_hist["prev_val"]) / df_hist["prev_val"].abs()
    )
    df_hist["cres_pct"] = pd.Series(cres_pct_np_array, index=df_hist.index).fillna(0)
    
    df_hist["cres_color"] = df_hist["cres_pct"].apply(
        lambda x: COLOR_POS if x >= 0 else COLOR_NEG
    )

    # --- Formatação --- #
    if kpi_name == "Tempo Médio de Casa":
        fmt_val = _format_tempo_casa
        df_hist["val_fmt"]      = df_hist["valor"].apply(fmt_val)
        df_hist["prev_fmt"]     = df_hist["prev_val"].apply(lambda v: fmt_val(v) if pd.notna(v) else "-")
        df_hist["cres_abs_fmt"] = df_hist["cres_abs"].apply(lambda x: f"{x:+.1f} dias")
        df_hist["cres_pct_fmt"] = df_hist["cres_pct"].apply(lambda x: dashboard.formatar_valor(x * 100 if pd.notna(x) else None, "percentual"))

    else:
        # format_type já foi inferido ou passado como argumento
        # dashboard.formatar_valor é um wrapper para formatar_valor_utils

        if format_type == "percentual":
            # df_hist["valor"] e df_hist["prev_val"] AGORA ESTÃO NA ESCALA 0-100
            # formatar_valor_utils para "percentual" espera essa escala.
            df_hist["val_fmt"]  = df_hist["valor"].apply(lambda v: dashboard.formatar_valor(v if pd.notna(v) else None, "percentual"))
            df_hist["prev_fmt"] = df_hist["prev_val"].apply(lambda v: dashboard.formatar_valor(v if pd.notna(v) else None, "percentual") if pd.notna(v) else "-")
            # cres_abs para percentuais é a diferença de pontos percentuais (já está na escala correta, ex: 0.5 para 0.5 p.p)
            df_hist["cres_abs_fmt"] = df_hist["cres_abs"].apply(lambda x: f"{x:+.1f} p.p." if pd.notna(x) else "-") 
            # cres_pct é uma fração (variação da variação), então multiplicamos por 100 para formatar.
            df_hist["cres_pct_fmt"] = df_hist["cres_pct"].apply(lambda x: dashboard.formatar_valor(x * 100 if pd.notna(x) else None, "percentual"))
        else: # Para monetário e outros tipos 'numero'
            df_hist["val_fmt"]      = df_hist["valor"].apply(lambda v: dashboard.formatar_valor(v, format_type))
            df_hist["prev_fmt"]     = df_hist["prev_val"].apply(lambda v: dashboard.formatar_valor(v, format_type) if pd.notna(v) else "-")
            df_hist["cres_abs_fmt"] = df_hist["cres_abs"].apply(lambda x: dashboard.formatar_valor(x, format_type if format_type != 'numero' else 'monetario')) # Delta abs monetário se KPI for número geral
            df_hist["cres_pct_fmt"] = df_hist["cres_pct"].apply(lambda x: dashboard.formatar_valor(x * 100 if pd.notna(x) else None, "percentual"))

    # ------------------------------------------------------------------ #
    # 4) Tipo de gráfico                                                 #
    # ------------------------------------------------------------------ #
    if chart_type == "auto":
        chart_type = "bar" if df_hist["valor"].abs().sum() == 0 else "line"

    main_color      = custom_color or COLOR_NEUTR
    secondary_color = "#FFFFFF"

    # AJUSTE HOVERTEMPLATE PARA TEMPO MÉDIO
    hover_template = (
        "<b style='font-size:16px; color:#4A4A4A; font-family:Inter;'>%{x}</b><br><br>"
        "<span style='font-size:14px; font-family:Inter;'>Valor: <b>%{text}</b></span><br>"
        "<span style='font-size:14px; font-family:Inter;'>Anterior: <b>%{customdata[0]}</b></span><br>"
        "<span style='color:%{customdata[3]}; font-weight:bold; font-size:14px; font-family:Inter;'>Variação: %{customdata[1]}</span><br>"
        "<span style='font-size:14px; font-family:Inter;'>Δ Absoluto: <b>%{customdata[2]}</b></span><extra></extra>"
    )

    if chart_type == "bar":
        trace = go.Bar(
            x=df_hist["label"], y=df_hist["valor"],
            marker=dict(color=main_color, opacity=0.9),
            text=df_hist["val_fmt"],
            textposition='none', # Texto virá das anotações
            customdata=df_hist[["prev_fmt", "cres_pct_fmt", "cres_abs_fmt", "cres_color"]],
            hovertemplate=hover_template
        )
    else: # line
        trace = go.Scatter(
            x=df_hist["label"], y=df_hist["valor"],
            mode="lines+markers",
            line=dict(shape="linear", color=main_color, width=3),
            marker=dict(size=8, color=main_color),
            text=df_hist["val_fmt"],
            customdata=df_hist[["prev_fmt", "cres_pct_fmt", "cres_abs_fmt", "cres_color"]],
            hovertemplate=hover_template
        )

    fig = go.Figure(trace)

    # ------------------------------------------------------------------ #
    # 5) Ajustes visuais                                                 #
    # ------------------------------------------------------------------ #
    fig.update_yaxes(
        showgrid=True, gridcolor="#E0E0E0", gridwidth=1.2,
        zeroline=False, showticklabels=False
    )

    fig.update_layout(
        hoverlabel=dict(
            bgcolor=secondary_color,
            bordercolor="#DDDDDD",
            font_size=14,
            font_family="Inter",
            font_color="#333333",
            align="left"
        )
    )

    # Rótulos sobre cada ponto (com sombra)
    for _, r in df_hist.iterrows():
        if pd.isna(r["valor"]) or r["valor"] == 0:
            continue

        # Garante que o texto formatado seja tratado como string
        text_to_display = str(r["val_fmt"])

        # sombra
        fig.add_annotation(
            x=r["label"], y=r["valor"], text=text_to_display, # Usa a string explícita
            showarrow=False, yshift=16, xshift=2,
            font=dict(size=15, color="rgba(0,0,0,0.3)", family="Inter Medium"),
            bgcolor="rgba(0,0,0,0.2)", bordercolor="rgba(0,0,0,0)",
            borderwidth=0, borderpad=4, opacity=0.7, align="center",
            width=84, height=28
        )
        # principal
        fig.add_annotation(
            x=r["label"], y=r["valor"], text=text_to_display, # Usa a string explícita
            showarrow=False, yshift=18, yanchor="middle",
            font=dict(size=15, color="#FFFFFF", family="Inter Medium"),
            bgcolor=main_color, bordercolor=main_color,
            borderwidth=1, borderpad=4, opacity=0.95, align="center",
            width=80, height=25
        )

    # padding vertical
    min_v, max_v = df_hist["valor"].min(), df_hist["valor"].max()
    # Trata caso onde min_v ou max_v podem ser NaN
    if pd.isna(min_v) or pd.isna(max_v):
        pad = 1 # Define um padding padrão se houver NaNs
        min_v = df_hist["valor"].dropna().min() if pd.notna(df_hist["valor"].dropna().min()) else 0
        max_v = df_hist["valor"].dropna().max() if pd.notna(df_hist["valor"].dropna().max()) else 1
    else:
        pad = (max_v - min_v) * 0.15 if max_v != min_v else abs(max_v) * 0.2 # Aumentei padding
        pad = max(pad, 1) # Garante padding mínimo

    fig.update_layout(
        title=None, height=height,
        paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR,
        margin=dict(l=60, r=40, t=20, b=40),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=14, family="Inter", color="#4A4A4A"),
            tickangle=-30
        ),
        yaxis=dict(
            range=[(min_v - pad) if pd.notna(min_v) else -pad, (max_v + pad) if pd.notna(max_v) else pad],
            showticklabels=False,
            showgrid=True, gridwidth=1.2, gridcolor="#E0E0E0"
        ),
        showlegend=False,
        transition=dict(duration=600, easing="cubic-in-out") if animated else None
    )

    return fig
