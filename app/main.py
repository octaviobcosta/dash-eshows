"""
app.py – Entry point do Dash da Eshows
====================================
Organizado em blocos lógicos, com títulos claros e comentários de contexto.  
Comentários extensos e código morto foram removidos para facilitar a leitura.
"""

# ==============================================================================
# 1) IMPORTS
# ==============================================================================
# ― Padrão ---------------------------------------------------------------------
import os
import sys
import gc
import json
import logging
from dotenv import load_dotenv
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta
import calendar

# ― Terceiros -------------------------------------------------------------------

import pandas as pd
import numpy as np
import dash
import dash_bootstrap_components as dbc
from dash import Dash, html, dcc, Input, Output, State, ALL, callback_context
from dash.exceptions import PreventUpdate
import plotly.express as px
import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta
import colorsys  # usado em funções de contraste e gráficos
from dash import callback
from flask import session

load_dotenv()
import logging_config  # noqa: F401

# ― Módulos internos ------------------------------------------------------------
from .auth_improved import (
    create_login_layout,
    init_auth_callbacks,
    init_logout_callback,
    init_client_side_callbacks,
    add_logout_button,
    require_auth
)
from app.config_data import HIST_KPI_MAP, get_hist_kpi_map
from .modulobase import (
    carregar_base_eshows,
    carregar_eshows_excluidos,  # para exportar registros descartados
    carregar_base2,
    carregar_ocorrencias,
)
from .utils import (
    formatar_range_legivel,
    formatar_valor_utils,
    floatify_hist_data,
    filtrar_periodo_principal,
    filtrar_periodo_comparacao,
    get_period_start,
    get_period_end,
    mes_nome,
    mes_nome_intervalo,
    calcular_periodo_anterior,
    filtrar_base2,
    filtrar_base2_comparacao,
    filtrar_base2_op_shows,
    filtrar_base2_op_shows_compare,
    faturamento_dos_grupos,
    obter_top5_grupos_ano_anterior,
    novos_palcos_dos_grupos,
    get_churn_ka_for_period,
    get_period_range,
    calcular_churn,
    filtrar_novos_palcos_por_comparacao,
    filtrar_novos_palcos_por_periodo,
    calcular_churn_novos_palcos,
    calcular_variacao_percentual,
    ensure_grupo_col
)
from .kpis_charts import generate_kpi_figure

# ==============================================================================
# 2) CONFIGURAÇÕES GLOBAIS
# ==============================================================================
# ― Encoding de saída -----------------------------------------------------------
sys.stdout.reconfigure(encoding="utf-8")

# ― Logger ----------------------------------------------------------------------
logger = logging.getLogger(__name__)

from .mem_utils import log_memory_usage

log_memory_usage("inicio")

# ― Warnings & Pandas -----------------------------------------------------------


# ― Constantes visuais ----------------------------------------------------------
TEXT_COLOR = "#122046"

# ==============================================================================
# 3) FUNÇÕES DE FORMATAÇÃO E AUXÍLIO
# ==============================================================================

def formatar_valor_custom(valor, tipo: str = "numero") -> str:
    """Wrapper simples para formatar_valor_utils."""
    return formatar_valor_utils(valor, tipo)


def ajustar_cor_contraste(hex_cor: str) -> str:
    """Retorna cor (#FFFFFF ou #4A4A4A) que contrasta com o hex recebido."""
    hex_cor = hex_cor.lstrip("#")
    r, g, b = (int(hex_cor[i : i + 2], 16) for i in (0, 2, 4))
    _, l, _ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return "#4A4A4A" if l > 0.6 else "#FFFFFF"

# ==============================================================================
# 4) GRÁFICO WATERFALL (com donut opcional)
# ==============================================================================
def create_waterfall_chart(
    categories,
    values,
    *,
    periodo: str = "YTD",
    ano: int = datetime.now().year,
    categories_donut=None,
    values_donut=None,
):
    """Gera o Waterfall + donut opcional.
       • seta/arrow só aparece se o donut for renderizado.
    """

    cost_categories = {
        "Imposto","Ocupação","Equipe","Terceiros","Op. Shows",
        "D.Cliente","Softwares","Mkt","D.Finan",
    }

    # ------------------------------------------------------------------
    # 4.1) dados básicos
    # ------------------------------------------------------------------
    max_abs = max(abs(v) for v in values) if values else 0
    fraction_for_image = 0.5

    cumulative = [0]
    for val in values:
        cumulative.append(cumulative[-1] + val)
    cumulative = cumulative[1:]
    base = [0] + cumulative[:-1]

    sum_costs = sum(abs(v) for c, v in zip(categories, values) if c in cost_categories)

    # ------------------------------------------------------------------
    # 4.2) cores / textos / anotações
    # ------------------------------------------------------------------
    bar_colors, text_colors, text_values = [], [], []
    hover_texts, annotations, images    = [], [], []

    def format_value(val: float) -> str:
        abs_val = abs(val)
        if abs_val >= 1_000_000: return f"R${abs_val/1_000_000:,.2f}M"
        if abs_val >= 1_000:     return f"R${abs_val/1_000:.1f}k"
        return f"R${abs_val:,.0f}"

    for idx, (cat, val) in enumerate(zip(categories, values)):
        # cor “padrão” da barra
        if cat == "Faturamento":    bar_color, img_src = "#29B388", "assets/barrafat.png"
        elif cat == "Lucro Líquido":
            if val >= 0:            bar_color, img_src = "#2ECC71", "assets/barralucro.png"
            else:                   bar_color, img_src = "#E74C3C", "assets/barrapreju.png"
        else:                       bar_color, img_src = "#F47D7C", "assets/barracust.png"

        # texto da barra
        sign = "-" if val < 0 else ""
        text_values.append(sign + format_value(abs(val)))

        # anotação com nome da categoria
        shift  = max(cumulative) * 0.095 if cumulative else 0
        y_val  = base[idx] + val
        y_anno = y_val + shift if val >= 0 else y_val - shift
        y_anchor = "bottom" if val >= 0 else "top"
        annotations.append(dict(
            x=idx, y=y_anno, text=cat, showarrow=False,
            xanchor="center", yanchor=y_anchor,
            font=dict(size=15, color=bar_color),
        ))

        # hover extra: participação no total de custos
        if cat in cost_categories and sum_costs:
            pct = (abs(val) / sum_costs) * 100
            hover_texts.append(f"<b>Part. Custos</b><br>{pct:.2f}%")
        else:
            hover_texts.append(None)

        # barra com textura apenas se “grande” o suficiente
        x_left, x_right = idx - .4, idx + .4
        y_bottom, y_top = min(base[idx], y_val), max(base[idx], y_val)
        if max_abs and abs(val) >= fraction_for_image * max_abs:
            bar_colors.append("rgba(0,0,0,0)")
            images.append(dict(
                source=img_src, xref="x", yref="y",
                x=x_left, y=y_bottom, sizex=x_right-x_left, sizey=y_top-y_bottom,
                xanchor="left", yanchor="bottom",
                sizing="stretch", layer="above",
            ))
        else:
            bar_colors.append(bar_color)
        text_colors.append(bar_color)

    # ------------------------------------------------------------------
    # 4.3) Waterfall
    # ------------------------------------------------------------------
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(len(categories))), y=values, base=base,
        marker_color=bar_colors,
        text=text_values, textposition="outside",
        textfont=dict(size=15, color=text_colors),
        hovertext=hover_texts, hoverinfo="text",
    ))
    fig.update_layout(
        annotations=annotations,
        hoverlabel=dict(bgcolor="#FC4F22", bordercolor="rgba(0,0,0,0)",
                        font=dict(color="white")),
    )
    for im in images:
        fig.add_layout_image(im)

    # ------------------------------------------------------------------
    # 4.4) donut opcional – só se houver dados
    # ------------------------------------------------------------------
    if categories_donut and values_donut and sum(values_donut) != 0 and "Equipe" in categories:
        _add_cost_donut(fig, categories, values, categories_donut, values_donut)

    # layout final
    fig.update_layout(
        title=dict(
            text=f"Período Apurado - {periodo} de {ano}",
            x=0.975, y=1, xanchor="right", yanchor="top",
            font=dict(family="Inter", style="italic", size=18, color="#4A4A4A"),
        ),
        showlegend=False, height=420,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        font=dict(family="Inter Medium", size=13, color="#2e2e2e"),
        template="none",
    )
    return fig

def _add_cost_donut(fig, categories, values, labels, vals):
    """Adiciona donut de custos no gráfico já criado (helper interno)."""
    eq_idx = categories.index("Equipe")
    n_cat = len(categories)
    eq_rel = (eq_idx + 0.5) / n_cat
    pie_w = 0.15
    offset = 0.01

    px_start = min(max(eq_rel + pie_w / 2 + offset, 0), 1 - pie_w)
    px_end = px_start + pie_w
    pie_x_domain = [px_start, px_end]
    pie_y_domain = [0.45, 1.0]

    # ― Cores gradientes para as fatias ----------------------------------------
    grad_colors = [
        "#FF4C29",
        "#FF6B2A",
        "#FF8A2B",
        "#FFA92C",
        "#FFC92D",
        "#FDD94E",
        "#E6E133",
        "#C8E031",
        "#9DD929",
    ]
    data_z = sorted(zip(vals, labels), reverse=True, key=lambda x: x[0])
    c_map = {label: grad_colors[i] if i < len(grad_colors) else "#CCCCCC" for i, (__, label) in enumerate(data_z)}
    color_seq = [c_map.get(lb, "#CCCCCC") for lb in labels]

    def _val_fmt(v):
        a = abs(v)
        if a >= 1_000_000:
            return f"R${a / 1_000_000:,.2f}M"
        if a >= 1_000:
            return f"R${a / 1_000:.1f}k"
        return f"R${a:,.0f}"

    vals_fmt = [_val_fmt(x) for x in vals]

    # ― Desenha três camadas para efeito anel + borda --------------------------
    for i, (hole, line_w, alpha) in enumerate([(0.88, 10, 0.2), (0.63, 8, 0.15), (0.60, 5, 1.0)]):
        fig.add_trace(
            go.Pie(
                labels=labels,
                values=vals,
                hole=hole,
                marker=dict(
                    colors=[f"rgba(0,0,0,{alpha})"] * len(vals) if i < 2 else color_seq,
                    line=dict(color="#FAF6F1", width=line_w),
                ),
                textinfo="none" if i < 2 else "percent+label",
                textposition="inside" if i == 2 else "none",
                insidetextfont=dict(size=12) if i == 2 else None,
                pull=[0.06] * len(vals) if i == 0 else ([0.04] * len(vals) if i == 1 else None),
                hoverinfo="skip" if i < 2 else "label+text",
                text=vals_fmt if i == 2 else None,
                domain=dict(x=pie_x_domain, y=pie_y_domain),
                showlegend=False,
            )
        )

    # Flecha ligando anel à coluna "Equipe" ------------------------------------
    x0 = pie_x_domain[0]
    y0 = sum(pie_y_domain) / 2
    x1 = (eq_idx + 0.5) / n_cat
    fig.add_annotation(
        x=x0,
        y=y0,
        xref="x domain",
        yref="y domain",
        ax=x1,
        ay=y0,
        axref="x domain",
        ayref="y domain",
        text="",
        showarrow=True,
        arrowhead=1,
        arrowsize=1,
        arrowwidth=2,
        arrowcolor="#F57D7C",
    )

# ==============================================================================
# 5) ASSETS E ESTILOS EXTERNOS
# ==============================================================================
external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
]

# ==============================================================================
# 6) CARREGAMENTO DAS BASES PRINCIPAIS
# ==============================================================================
# Carregar dados normalmente (reloader já está desabilitado)
logger.info("Carregando bases do Supabase…")
log_memory_usage("antes_bases")
df_eshows = carregar_base_eshows()
log_memory_usage("apos_df_eshows")
df_base2 = carregar_base2()
log_memory_usage("apos_df_base2")
df_ocorrencias = carregar_ocorrencias()
log_memory_usage("apos_df_ocorrencias")
logger.info("Bases carregadas com sucesso.")
log_memory_usage("bases_carregadas")

# ― Ajustes auxiliares para Novos Clientes -------------------------------------
if df_eshows is not None and not df_eshows.empty:
    df_casas_earliest = (
        df_eshows.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")
    )
    df_casas_latest = (
        df_eshows.groupby("Id da Casa")["Data do Show"].max().reset_index(name="LastShow")
    )
else:
    df_casas_earliest = df_casas_latest = None

# ==============================================================================
# 7) UTILITÁRIO DE ESTADOS (UF → Nome/Bandeira)
# ==============================================================================
with open(Path(__file__).resolve().parent / "data" / "uf.json", "r", encoding="utf-8") as fp:
    data_uf = json.load(fp)

SIGLA_TO_NOME = {uf["sigla"]: uf["nome"] for uf in data_uf["UF"]}


def get_nome_estado(sigla: str) -> str:
    """Converte sigla (SP) em nome do estado (São Paulo)."""
    return SIGLA_TO_NOME.get(sigla, sigla)


def estado_para_arquivo_bandeira(nome_estado: str) -> str:
    """Normaliza nome para arquivo PNG da bandeira."""
    if nome_estado.lower() == "brasil":
        return "brasil.png"
    nome_limpo = "".join(
        c
        for c in unicodedata.normalize("NFD", nome_estado.lower())
        if unicodedata.category(c) != "Mn"
    )
    return f"{nome_limpo}.png"

# ==============================================================================
# 8) EXPOSIÇÃO GLOBAL DO HIST_KPI_MAP (para kpis_charts.py)
# ==============================================================================
import flask

try:
    flask.current_app.HIST_KPI_MAP = HIST_KPI_MAP  # dentro de app Flask
except RuntimeError:  # sem contexto Flask – fallback
    globals()["HIST_KPI_MAP"] = HIST_KPI_MAP

# ==============================================================================
# 9) GC PREVENTIVO (opcional)
# ==============================================================================
gc.collect()
logger.info("Coleta de lixo executada.")


# =================================================================================
# CRIAR CARD KPI
# =================================================================================
def criar_card_kpi_shows(
    titulo,
    valor,
    variacao,
    periodo_comp,
    format_type: str = "numero",
    is_negative: bool = False,
    icon_path: str = "/assets/kpiicon.png",
):
    """
    Monta um cartão de KPI.

    Parâmetros
    ----------
    titulo : str
        Título exibido no topo do card.
    valor : float | int | str
        Valor atual do indicador.
    variacao : float | None
        Variação percentual relativa ao período de comparação.
    periodo_comp : str
        Rótulo exibido abaixo (ex.: 'vs. Ano Anterior').
    format_type : str
        'numero', 'monetario', 'porcentagem', **'tempo' (novo)**.
        Quando 'tempo', assume que `valor` já é string formatada
        ("25 dias", "7,2 meses", "1,5 anos").
    is_negative : bool
        Quando True, inverte a cor (ex.: churn maior é ruim).
    icon_path : str
        Caminho do ícone exibido à direita do título.
    """
    # -------------------------------------------------------------- #
    # 1) Formatação do valor principal
    # -------------------------------------------------------------- #
    if format_type == "tempo":
        # Valor já vem como string amigável
        valor_formatado = str(valor)
    elif isinstance(valor, str):
        valor_formatado = valor
    else:
        if valor is None:
            valor_formatado = "-"
        else:
            # Garante que `valor` é numérico antes de formatar
            if not isinstance(valor, (int, float)):
                try:
                    valor = float(valor)
                except Exception:
                    valor = 0
            valor_formatado = formatar_valor_custom(valor, format_type)

    # -------------------------------------------------------------- #
    # 2) Variação (%)
    # -------------------------------------------------------------- #
    var_str = "N/A"
    is_positive = False
    if variacao is not None:
        is_positive = variacao > 0
        var_str = f"{'+' if is_positive else ''}{variacao:.1f}%"

    cor = "danger" if (is_positive == is_negative) else "success"
    arrow_icon_class = (
        "fa-solid fa-arrow-trend-up" if is_positive else "fa-solid fa-arrow-trend-down"
    )
    arrow_color = "#198754" if cor == "success" else "#dc3545"

    # -------------------------------------------------------------- #
    # 3) Card
    # -------------------------------------------------------------- #
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span(titulo, className="card-kpi-title-text"),
                                html.Img(
                                    src=icon_path,
                                    id={"type": "kpi-dash-icon", "index": titulo},
                                    n_clicks=0,
                                    className="card-kpi-icon",
                                    alt="Ícone do KPI",
                                    height="16px",
                                    style={"margin-left": "auto"},
                                ),
                            ],
                            className="card-kpi-title",
                            style={
                                "display": "flex",
                                "align-items": "center",
                                "justify-content": "space-between",
                                "margin-bottom": "0.25rem",
                            },
                        ),
                        html.H3(
                            valor_formatado,
                            className="card-kpi-value",
                            style={"margin-bottom": "0.25rem"},
                        ),
                        html.Div(
                            [
                                html.Div(style={"flex": "1"}),
                                html.Div(
                                    [
                                        html.I(
                                            className=f"{arrow_icon_class} me-1",
                                            style={
                                                "color": arrow_color,
                                                "font-size": "1rem",
                                            },
                                        ),
                                        html.Span(
                                            var_str,
                                            style={
                                                "color": arrow_color,
                                                "font-size": "1rem",
                                            },
                                        ),
                                    ],
                                    className="card-kpi-variation",
                                ),
                            ],
                            style={
                                "display": "flex",
                                "align-items": "center",
                                "margin-bottom": "0.25rem",
                            },
                        ),
                        html.Div(f"vs {periodo_comp}", className="card-kpi-period"),
                    ],
                    className="card-kpi-inner",
                )
            ]
        ),
        className="card-kpi h-100",
    )

# ----------------------------------------------------------------------
# metricas_rh_quick  –  KPIs da seção Pessoas
# ----------------------------------------------------------------------
from datetime import datetime
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd

from .modulobase import (
    carregar_pessoas,
    carregar_base2,
    carregar_base_eshows,
)
from .variacoes  import get_churn_variables, get_rpc_variables
from .utils      import (
    get_period_start,
    get_period_end,
    calcular_periodo_anterior,
)

# ----------------------------------------------------------------------
def metricas_rh_quick(
    ano: int,
    periodo: str,
    mes: int | None,
    *,
    comparar_opcao: str | None = None,
    custom_range=None,
    df_pessoas_global: pd.DataFrame | None = None,
    df_base2_global:   pd.DataFrame | None = None,
    df_eshows_global:  pd.DataFrame | None = None,   #  <<< NOVO parâmetro opcional
):
    """
    Retorna (principal, comparacao) com chaves:
      n_func, salario_medio,
      tempo_medio_casa, tempo_medio_casa_fmt,
      receita_por_colaborador, rpc_fmt
    """

    # ---------------------------------------------------------------
    # 1) Bases
    # ---------------------------------------------------------------
    df_p = (
        df_pessoas_global.copy()
        if df_pessoas_global is not None and not df_pessoas_global.empty
        else carregar_pessoas()
    )
    if df_p is None or df_p.empty:
        vazio = dict(
            n_func=0,
            salario_medio=0.0,
            tempo_medio_casa=0.0,
            tempo_medio_casa_fmt="0 dias",
            receita_por_colaborador=0.0,
            rpc_fmt="R$0",
        )
        return vazio, (vazio if comparar_opcao else None)

    df_b2 = (
        df_base2_global.copy()
        if df_base2_global is not None and not df_base2_global.empty
        else carregar_base2()
    )
    df_e  = (
        df_eshows_global.copy()
        if df_eshows_global is not None and not df_eshows_global.empty
        else carregar_base_eshows()
    )

    _to_dt = lambda s: pd.to_datetime(s, errors="coerce")
    df_p["DataInicio"] = _to_dt(df_p["DataInicio"])
    df_p["DataSaida"]  = _to_dt(df_p.get("DataSaida"))

    if "Data" not in df_b2.columns and {"Ano", "Mês"}.issubset(df_b2.columns):
        df_b2["Data"] = pd.to_datetime(
            dict(year=df_b2["Ano"], month=df_b2["Mês"], day=1), errors="coerce"
        )
    df_b2["Data"]   = _to_dt(df_b2["Data"]).dt.normalize()
    df_b2["Equipe"] = pd.to_numeric(df_b2["Equipe"], errors="coerce").fillna(0.0)

    # ---------------------------------------------------------------
    # 2) Helpers
    # ---------------------------------------------------------------
    def _headcount_mes(ref_month: pd.Timestamp) -> int:
        last_day = (ref_month + relativedelta(months=1)) - pd.DateOffset(days=1)
        ativos = (df_p["DataInicio"] <= last_day) & (
            df_p["DataSaida"].isna() | (df_p["DataSaida"] > last_day)
        )
        return int(ativos.sum())

    def _tempo_medio(dt_fim: pd.Timestamp) -> tuple[float, str]:
        dias = [
            (min(row["DataSaida"], dt_fim) if pd.notna(row["DataSaida"]) else dt_fim)
            - row["DataInicio"]
            for _, row in df_p.iterrows()
            if pd.notna(row["DataInicio"])
        ]
        dias = [d.days for d in dias if d.days >= 0]
        if not dias:
            return 0.0, "0 dias"
        media = float(np.mean(dias))
        if media < 30:
            fmt = f"{int(round(media))} dias"
        elif media < 365:
            fmt = f"{media/30.0:.1f}".replace(".", ",") + " meses"
        else:
            fmt = f"{media/365.0:.1f}".replace(".", ",") + " anos"
        return media, fmt

    def _rpc(ano_x, per_x, mes_x, dt_ini, dt_fim) -> tuple[float, str]:
        """
        Usa variacoes.get_rpc_variables; devolve (valor_numerico, string_fmt).
        Se a função retornar dict vazio → 0.
        """
        try:
            res = get_rpc_variables(
                ano_x,
                per_x,
                mes_x,
                custom_range=None,
                df_eshows_global=df_e,
                df_pessoas_global=df_p,
            )
            if isinstance(res, dict):
                valor_num = res.get("variables_values", {}).get(
                    "Receita Colaborador Mensal", 0
                )
                valor_fmt = res.get("resultado", "R$0")
                return float(valor_num), valor_fmt
            # se vier direto numérico
            return float(res), f"R${res:,.0f}"
        except Exception:
            return 0.0, "R$0"

    # ---------------------------------------------------------------
    # 3) Bloco KPI
    # ---------------------------------------------------------------
    def _kpis(dt_ini, dt_fim, ano_ref, per_ref, mes_ref):
        if dt_ini is None or dt_fim is None:
            return dict(
                n_func=0,
                salario_medio=0.0,
                tempo_medio_casa=0.0,
                tempo_medio_casa_fmt="0 dias",
                receita_por_colaborador=0.0,
                rpc_fmt="R$0",
            )

        # ---> INÍCIO DA ALTERAÇÃO: Calcular Média de Headcount <----
        # Gerar range de meses (início de cada mês) dentro do período
        months_in_period = pd.date_range(start=dt_ini.replace(day=1), end=dt_fim.replace(day=1), freq='MS')
        headcounts_mensais = []
        for month_start in months_in_period:
            headcount_do_mes = _headcount_mes(month_start) # Usa a função helper existente
            headcounts_mensais.append(headcount_do_mes)

        # Calcula a média e arredonda para o inteiro mais próximo
        n_func_avg = 0
        if headcounts_mensais: # Evita divisão por zero se a lista estiver vazia
            n_func_avg = round(np.mean(headcounts_mensais))
        # ---> FIM DA ALTERAÇÃO <----

        # Remove a linha antiga que pegava só o headcount do último mês:
        # n_func = _headcount_mes(dt_fim.replace(day=1))

        mask = (df_b2["Data"] >= dt_ini.replace(day=1)) & (
            df_b2["Data"] <= dt_fim.replace(day=1)
        )
        df_custo = df_b2.loc[mask].copy()
        if df_custo.empty:
            salario_medio = 0.0
        else:
            df_custo["Head"] = df_custo["Data"].apply(_headcount_mes)
            df_custo = df_custo[df_custo["Head"] > 0]
            total_custo = df_custo["Equipe"].sum()
            total_head  = df_custo["Head"].sum()
            salario_medio = (total_custo / total_head) if total_head else 0.0

        media_dias, media_fmt = _tempo_medio(dt_fim)
        rpc_val, rpc_fmt = _rpc(ano_ref, per_ref, mes_ref, dt_ini, dt_fim)

        return dict(
            n_func=n_func_avg, # <<< USA A MÉDIA CALCULADA
            salario_medio=float(salario_medio),
            tempo_medio_casa=media_dias,
            tempo_medio_casa_fmt=media_fmt,
            receita_por_colaborador=rpc_val,
            rpc_fmt=rpc_fmt,
        )

    # ---------------------------------------------------------------
    # 4) Período principal
    # ---------------------------------------------------------------
    dt_ini = get_period_start(ano, periodo, mes, custom_range)
    dt_fim = get_period_end(ano, periodo, mes, custom_range)
    met_principal = _kpis(dt_ini, dt_fim, ano, periodo, mes)

    # ---------------------------------------------------------------
    # 5) Período de comparação (opcional)
    # ---------------------------------------------------------------
    if not comparar_opcao:
        return met_principal, None

    if comparar_opcao == "ano_anterior":
        ano_c, per_c, mes_c = ano - 1, periodo, mes
        dt_ini_c = dt_ini - relativedelta(years=1)
        dt_fim_c = dt_fim - relativedelta(years=1)
    elif comparar_opcao == "periodo_anterior":
        per_c, ano_c, mes_c = calcular_periodo_anterior(ano, periodo, mes)
        dt_ini_c = get_period_start(ano_c, per_c, mes_c, None)
        dt_fim_c = get_period_end(ano_c, per_c, mes_c, None)
    else:  # custom
        if isinstance(custom_range, (list, tuple)) and len(custom_range) == 2:
            dt_ini_c, dt_fim_c = map(pd.to_datetime, custom_range)
        else:
            dt_ini_c = dt_fim_c = None
        ano_c, per_c, mes_c = ano, periodo, mes

    met_comp = _kpis(dt_ini_c, dt_fim_c, ano_c, per_c, mes_c)
    return met_principal, met_comp

###############################################################################
# Layouts: Sidebar, Dashboard, etc.
###############################################################################

# Alerta para recarregar base
alert_atualiza = dbc.Alert(
    id="alert-atualiza-base",
    children="Bases recarregadas com sucesso!",
    color="success",
    dismissable=True,
    is_open=False
)

# =================================================================================
# FUNÇÃO QUE CRIA O MODAL DO GRÁFICO KPI – "Evolução 12 meses"
# =================================================================================
def create_kpi_dashboard_modal():
    return dbc.Modal(
        [
            # ---------- Cabeçalho ----------
            dbc.ModalHeader(
                [
                    # título + ícone
                    html.Div(
                        [
                            html.Img(
                                id="kpi-dash-modal-icon",
                                src="/assets/kpiicon.png",
                                style={"marginRight": "12px", "width": "28px", "height": "28px"},
                            ),
                            html.H4(
                                id="kpi-dash-modal-title",
                                className="modal-title-text",
                                style={"margin": 0, "fontWeight": 600},
                            ),
                        ],
                        className="d-flex align-items-center",
                        style={"flex": 1},
                    ),

                    # botão de fechar — alinhado horizontal/verticalmente
                    html.Button(
                        "✕",
                        id="close-kpi-dash-modal",
                        className="kpi-dash-close-btn",
                        style={
                            "position": "absolute",
                            "right": "calc(2rem + 18px)",
                            "top": "50%",
                            "transform": "translateY(-50%)",
                            "width": "36px",
                            "height": "36px",
                            "backgroundColor": "rgba(252, 79, 34, 0.15)",
                            "color": "#FC4F22",
                            "borderRadius": "50%",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "border": "none",
                            "cursor": "pointer",
                            "zIndex": 9999,
                            "fontSize": "18px",
                            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                        },
                    ),
                ],
                className="modal-header-custom d-flex align-items-center",
                close_button=False,
            ),

            # ---------- Corpo ----------
            dbc.ModalBody(
                html.Div(
                    dbc.Card(
                        dbc.CardBody(
                            html.Div(
                                [
                                    html.H5(
                                        id="kpi-dash-card-title",
                                        className="card-title text-center",
                                    ),
                                    dcc.Graph(
                                        id="kpi-dash-modal-graph",
                                        config={"displayModeBar": False},
                                        style={"height": "480px"},
                                    ),
                                ],
                                className="inner-card",
                            ),
                            style={"backgroundColor": "#FFFFFF", "padding": "1.5rem"},
                        ),
                        className="shadow-sm graph-card-large",
                        style={
                            "backgroundColor": "#FFFFFF",
                            "borderRadius": "12px",
                            "border": "1px solid #E0E0E0",
                            "boxShadow": "0 4px 6px rgba(0,0,0,0.1)",
                            "overflow": "hidden",
                        },
                    ),
                    style={"height": "auto"},
                ),
            ),

            # ---------- Footer ----------
            dbc.ModalFooter(
                html.P(
                    "© 2025 Eshows | Dashboard Gerencial",
                    className="mb-0 text-center w-100",
                    style={
                        "fontSize": "12px",
                        "opacity": "0.7",
                        "color": TEXT_COLOR,       # mesma variável já usada no layout principal
                        "margin": "0 auto",
                    },
                ),
                style={
                    "borderTop": "1px solid rgba(18,32,70,0.1)",
                    "backgroundColor": "#FAF8F4",  # cor de fundo areia
                    "width": "100%",
                },
            ),
        ],
        id="kpi-dash-modal",
        is_open=False,
        size="xl",
        fullscreen=True,
        backdrop="static",
        scrollable=True,
        contentClassName="modal-content-areia",
    )

# SIDEBAR (a original, com logo e navlinks)
sidebar = html.Div(
    [
        html.Div(
            html.Img(src="/assets/logo.png", style={"width": "160px"}),
            className="sidebar-logo"
        ),
        html.Div([
            html.H6("Principal", className="nav-section-title"),
            dbc.Nav([
                dbc.NavLink([html.I(className="fa-solid fa-gauge"), "Dashboard"],
                            href="/dashboard", className="side-link", active="exact"),
                dbc.NavLink([html.I(className="fa-solid fa-bullseye"), "OKRs"],
                            href="/okrs", className="side-link", active="exact"),
            ], vertical=True, pills=True)
        ], className="nav-section"),

        html.Div([
            html.H6("Gestão", className="nav-section-title"),
            dbc.Nav([
                dbc.NavLink([html.I(className="fa-solid fa-chart-line"), "Painel de KPIs"],
                            href="/kpis", className="side-link", active="exact"),
                dbc.NavLink([html.I(className="fa-solid fa-handshake"), "Comercial"],
                            href="/comercial", className="side-link", active="exact"),
                dbc.NavLink([html.I(className="fa-solid fa-wallet"), "Financeiro"],
                            href="/financeiro", className="side-link", active="exact"),
            ], vertical=True, pills=True)
        ], className="nav-section"),

        html.Div([
            html.H6("Recursos", className="nav-section-title"),
            dbc.Nav([
                dbc.NavLink([html.I(className="fa-solid fa-user-friends"), "Pessoas"],
                            href="/pessoas", className="side-link", active="exact"),
                dbc.NavLink([html.I(className="fa-solid fa-microphone"), "Artistas"],
                            href="/artistas", className="side-link", active="exact"),
            ], vertical=True, pills=True)
        ], className="nav-section"),

        html.Div(
            [
                dbc.NavLink(
                    [html.I(className="fa-solid fa-right-from-bracket"), "Logout"],
                    href="/logout",
                    className="side-link mb-3",
                    active="exact"
                ),
                dbc.Button(
                    [
                        html.Img(
                            src="/assets/ref.png",
                            style={"width": "16px", "height": "16px", "marginRight": "8px"}
                        ),
                        "Atualizar Base"
                    ],
                    id="btn-atualiza-base",
                    className="btn-cleanup w-100 mb-3",
                    style={
                        "background": "linear-gradient(45deg, #fdb03d, #fdb03d)",
                        "border": "none",
                        "color": "#fff"
                    }
                ),
                dbc.Button(
                    [
                        html.Img(
                            src="/assets/exp.png",
                            style={"width": "16px", "height": "16px", "marginRight": "8px"}
                        ),
                        "Filtro Base"
                    ],
                    id="btn-limpeza",
                    className="btn-cleanup w-100"
                ),
            ],
            className="sidebar-footer"
        ),
        alert_atualiza,
    ],
    className="sidebar",
    style={"marginRight": "1rem"}
)

# ============================ DASHBOARD LAYOUT ==============================
dashboard_layout = dbc.Container(
    [
        dcc.Download(id="download-excluidos"),

        dbc.Row([
            dbc.Col([
                html.H1(
                    "Dashboard",
                    style={
                        'font-family': 'Inter',
                        'font-weight': '700',
                        'font-size': '56px',
                        'color': '#4A4A4A'
                    },
                    className="mb-0"
                ),
                html.Div(
                    id='current-date',
                    style={
                        'font-family': 'Inter',
                        'font-weight': '200',
                        'font-style': 'italic',
                        'font-size': '16px',
                        'color': '#4A4A4A'
                    },
                    className="current-date"
                )
            ], className="mb-4")
        ]),

        # -------------------------------------------------------
        # Seletor de período e comparações
        # -------------------------------------------------------
        dbc.Row([
            dbc.Col([
                html.Label("Ano:", className="mb-1"),
                dcc.Dropdown(
                    id='dashboard-ano-dropdown',  # <---- #ALTERACAO
                    options=[{'label': str(y), 'value': y} for y in [2025, 2024, 2023, 2022]],
                    value=datetime.now().year,
                    clearable=False,
                    style={
                        'border-radius': '4px',
                        'border': '1px solid #D1D1D1',
                        'box-shadow': 'none'
                    }
                )
            ], xs=6, sm=3, md=2, lg=1, style={'padding': '0 5px'}),

            dbc.Col([
                html.Label("Período:", className="mb-1"),
                dcc.Dropdown(
                    id='dashboard-periodo-dropdown',  # <---- #ALTERACAO
                    options=[
                        {'label': 'Year To Date', 'value': 'YTD'},
                        {'label': '1° Trimestre', 'value': '1° Trimestre'},
                        {'label': '2° Trimestre', 'value': '2° Trimestre'},
                        {'label': '3° Trimestre', 'value': '3° Trimestre'},
                        {'label': '4° Trimestre', 'value': '4° Trimestre'},
                        {'label': 'Mês Aberto',   'value': 'Mês Aberto'},
                        {'label': 'Ano Completo', 'value': 'Ano Completo'},
                        {'label': 'Selecionar Período', 'value': 'custom-range'}
                    ],
                    value='YTD',
                    clearable=False,
                    style={
                        'border-radius': '4px',
                        'border': '1px solid #D1D1D1',
                        'box-shadow': 'none'
                    }
                )
            ], xs=10, sm=6, md=4, lg=2, style={'padding': '0 5px'}),

            dbc.Col([
                html.Div([
                    html.Label("Mês:", className="mb-1"),
                    dcc.Dropdown(
                        id='dashboard-mes-dropdown',  # <---- #ALTERACAO
                        options=[{'label': m, 'value': i}
                                 for i,m in enumerate([
                                     'Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho',
                                     'Agosto','Setembro','Outubro','Novembro','Dezembro'
                                 ],1)],
                        value=datetime.now().month,
                        clearable=False,
                        style={
                            'border-radius': '4px',
                            'border': '1px solid #D1D1D1',
                            'box-shadow': 'none'
                        }
                    )
                ], id='mes-dropdown-container', style={'display': 'none'})
            ], xs=10, sm=6, md=4, lg=2, style={'padding': '0 5px'}),

            dbc.Col([], className="flex-grow-1"),

            dbc.Col([
                html.Label("Comparar com:", className="mb-1"),
                dcc.Dropdown(
                    id='dashboard-comparar-dropdown',
                    options=[
                        {'label': 'Ano Anterior', 'value': 'ano_anterior'},
                        {'label': 'Período Anterior', 'value': 'periodo_anterior'},
                        {'label': 'Selecionar Período', 'value': 'custom-compare'}
                    ],
                    value='ano_anterior',
                    clearable=False,
                    style={
                        'border-radius': '4px',
                        'border': '1px solid #D1D1D1',
                        'box-shadow': 'none'
                    }
                )
            ], xs=10, sm=6, md=4, lg=2, style={'padding': '0 5px'}),
        ], className="mb-2 g-1"),

        # -------------------------------------------------------
        # Períodos personalizados (principal e comparação)
        # -------------------------------------------------------
        dbc.Row(
            [
                # — Período Personalizado —
                dbc.Col(
                    html.Div(
                        [
                            html.Label("Período Personalizado:", className="mb-1"),
                            html.Div(
                                dcc.DatePickerRange(
                                    id="dashboard-date-range-picker",
                                    display_format="DD/MM/YYYY",
                                    first_day_of_week=1,
                                    day_size=36,
                                    min_date_allowed=datetime(2020, 1, 1),
                                    show_outside_days=True,
                                    persistence=True,
                                    clearable=True,
                                    calendar_orientation="horizontal",
                                    start_date=datetime(datetime.now().year, 1, 1).date(),
                                    end_date=datetime.now().date()
                                ),
                                className="date-picker-wrapper",
                            ),
                        ],
                        id="date-range-picker-container",
                        style={"display": "none"},
                    ),
                    width="auto",
                ),

                dbc.Col([], className="flex-grow-1"),

                # — Período de Comparação —
                dbc.Col(
                    html.Div(
                        [
                            html.Label("Período Comparação:", className="mb-1"),
                            html.Div(
                                dcc.DatePickerRange(
                                    id="dashboard-date-range-picker-compare",
                                    display_format="DD/MM/YYYY",
                                    first_day_of_week=1,
                                    day_size=36,
                                    min_date_allowed=datetime(2020, 1, 1),
                                    show_outside_days=True,
                                    persistence=True,
                                    clearable=True,
                                    calendar_orientation="horizontal",
                                    start_date=datetime(datetime.now().year - 1, 1, 1).date(),
                                    end_date=(datetime.now() - relativedelta(years=1)).date(),
                                ),
                                className="date-picker-wrapper",
                            ),
                        ],
                        id="date-range-picker-compare-container",
                        style={"display": "none"},
                    ),
                    width="auto",
                ),
            ],
            className="mb-2 g-1",
        ),

        dbc.Row([
            dbc.Col([
                html.Div(
                    className="toggle-switch-container",
                    children=[
                        html.Div(id="toggle-indicator", className="toggle-indicator"),
                        html.Div(
                            [html.I(className="fa-solid fa-th me-2"), "Cards"],
                            id="btn-cards",
                            className="toggle-btn",
                            n_clicks=0
                        ),
                        html.Div(
                            [html.I(className="fa-solid fa-chart-bar me-2"), "Charts"],
                            id="btn-charts",
                            className="toggle-btn",
                            n_clicks=0
                        ),
                    ]
                )
            ], width="auto"),
        ], className="mb-4", style={"margin-top": "15px", "margin-bottom": "15px"}),

        # -------------------------------------------------------
        # Informação do período analisado
        # -------------------------------------------------------
        html.Div([
            html.Span("Período Analisado: ",
                      style={
                          'font-family': 'Inter',
                          'font-weight': '300',
                          'font-style': 'italic',
                          'font-size': '16px',
                          'color': '#4A4A4A'
                      },
                      className='me-1'),
            html.Span(id='periodo-analisado',
                      style={
                          'font-family': 'Inter',
                          'font-weight': '300',
                          'font-style': 'italic',
                          'font-size': '16px',
                          'color': '#4A4A4A'
                      })
        ], className='mb-2 g-1'),

        # -------------------------------------------------------
        # Cards e Charts (toggle)
        # -------------------------------------------------------
        html.Div(
            className="container-switch",
            children=[
                # Cards container
                html.Div(
                    id="cards-container",
                    className="fade-container fade-enter",
                    children=[
                        html.H2("Números Gerais",
                                style={'font-family':'Inter','font-weight':'600','font-size':'28px','marginBottom':'8px'}),
                        dbc.Row([
                            dbc.Col(id='kpi-gmv-col', md=3),
                            dbc.Col(id='kpi-numshows-col', md=3),
                            dbc.Col(id='kpi-ticket-col', md=3),
                            dbc.Col(id='kpi-cidades-col', md=3),
                        ], className="mb-4 g-3"),

                        html.Div(style={"margin-top": "20px", "margin-bottom": "10px"}, children=[
                            html.H2("Resultados",
                                    style={'font-family':'Inter','font-weight':'600','font-size':'28px','marginBottom':'8px'}),
                            dbc.Row([
                                dbc.Col(id='kpi-fat-col', md=3),
                                dbc.Col(id='kpi-takerate-gmv-col', md=3),
                                dbc.Col(id='kpi-custos-col', md=3),
                                dbc.Col(id='kpi-lucro-col', md=3),
                            ], className="mb-4 g-3"),
                        ]),

                        html.Div(style={"margin-top": "20px", "margin-bottom": "10px"}, children=[
                            html.H2("Novos Clientes",
                                    style={'font-family':'Inter','font-weight':'600','font-size':'28px','marginBottom':'8px'}),
                            dbc.Row([
                                dbc.Col(id='kpi-novospalcos-col', md=3),
                                dbc.Col(id='kpi-fatnovospalcos-col', md=3),
                                dbc.Col(id='kpi-lifetimemedio-col', md=3),
                                dbc.Col(id='kpi-churn-novospalcos-col', md=3)
                            ], className="mb-4 g-3"),
                        ]),

                        html.Div([
                            html.H2([
                                "Contas Chave",
                                html.Img(
                                    src="/assets/per.png",
                                    id="btn-info-contas-chave",
                                    style={
                                        "cursor": "pointer",
                                        "marginLeft": "6px",
                                        "width": "20px",
                                        "height": "20px"
                                    }
                                )
                            ], style={
                                'font-family':'Inter',
                                'font-weight':'600',
                                'font-size':'28px',
                                'marginBottom':'8px'
                            }),

                            dbc.Row([
                                dbc.Col(id='kpi-ka-fat-col', md=3),
                                dbc.Col(id='kpi-ka-novospalcos-col', md=3),
                                dbc.Col(id='kpi-ka-takerate-col', md=3),
                                dbc.Col(id='kpi-ka-churn-col', md=3),
                            ], className="mb-4 g-3"),
                        ], style={"margin-top": "20px", "margin-bottom": "10px"}),

                        html.Div([
                            html.H2("Operações", style={
                                'font-family':'Inter',
                                'font-weight':'600',
                                'font-size':'28px',
                                'marginBottom':'8px'
                            }),
                            dbc.Row([
                                dbc.Col(id='kpi-palcos-ativos-col', md=3),
                                dbc.Col(id='kpi-artistas-ativos-col', md=3),
                                dbc.Col(id='kpi-palcosvazios-col', md=3),
                                dbc.Col(id='kpi-errosop-col', md=3),
                            ], className="mb-4 g-3"),
                        ], style={"margin-top": "20px", "margin-bottom": "10px"}),

                        # —————————————————————————
                        # Seção • Pessoas
                        # —————————————————————————
                        html.Div([
                            html.H2("Pessoas", style={
                                'font-family':'Inter',
                                'font-weight':'600',
                                'font-size':'28px',
                                'marginBottom':'8px'
                            }),
                            dbc.Row(id="cards-pessoas", className="mb-4 g-3"),
                        ], style={"margin-top": "20px", "margin-bottom": "10px"}),
                    ]
                ),

                # Charts container
                html.Div(
                    id="charts-container",
                    className="fade-container fade-exit",
                    children=[
                        html.H2(
                            "Gráficos",
                            style={
                                'font-family': 'Inter',
                                'font-weight': '600',
                                'font-size': '28px',
                                'marginBottom': '8px'
                            }
                        ),

                        # Card Mapa do Brasil
                        dbc.Row([
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Div(
                                                                    [
                                                                        html.Img(
                                                                            src="/assets/brazil.png",
                                                                            className="card-header-icon"
                                                                        ),
                                                                        html.H5(
                                                                            "Números Gerais por Região",
                                                                            className="card-title",
                                                                            style={"margin-bottom": "0.25rem"}
                                                                        ),
                                                                    ],
                                                                    className="d-flex align-items-center"
                                                                ),
                                                                html.Img(
                                                                    src="/assets/expandir.png",
                                                                    className="expand-icon",
                                                                    id="expand-mapa-brasil",
                                                                    style={
                                                                        'cursor': 'pointer',
                                                                        'width': '18px',
                                                                        'height': '18px',
                                                                        'margin-left': 'auto'
                                                                    }
                                                                )
                                                            ],
                                                            className="card-header d-flex justify-content-between align-items-center",
                                                            style={'margin-bottom': '0.5rem'}
                                                        ),

                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                    html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        id="bandeira-selecionada",
                                                                                        style={
                                                                                            "width": "34px",
                                                                                            "marginRight": "8px"
                                                                                        }
                                                                                    ),
                                                                                    html.H4(
                                                                                        id="titulo-selecionado",
                                                                                        style={
                                                                                            "margin-bottom": "0",
                                                                                            "font-weight": "600",
                                                                                            "font-size": "18px"
                                                                                        }
                                                                                    ),
                                                                                ],
                                                                                style={
                                                                                    "display": "flex",
                                                                                    "align-items": "center",
                                                                                    "margin-bottom": "1rem"
                                                                                }
                                                                            ),

                                                                            dbc.Row(
                                                                                [
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("N° de Cidades", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-cidades", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("GMV", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-gmv", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper indicator-wrapper-center p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Palcos Ativos", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-palcosativos", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper indicator-wrapper-right p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                ],
                                                                                className="gx-2 gy-1 mb-2"
                                                                            ),

                                                                            dbc.Row(
                                                                                [
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("N° de Shows", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-shows", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Faturamento", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-faturamento", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper indicator-wrapper-center p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Novos Palcos", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-novospalcos", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper indicator-wrapper-right p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                ],
                                                                                className="gx-2 gy-1 mb-2"
                                                                            ),

                                                                            dbc.Row(
                                                                                [
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Artistas Ativos", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-artistasativos", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Ticket Médio", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-ticketmedio", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper indicator-wrapper-center p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                    dbc.Col(
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Churn", className="indicator-title mb-1"),
                                                                                                html.P(id="indicador-churn", className="indicator-value mb-0")
                                                                                            ],
                                                                                            className="indicator-wrapper indicator-wrapper-right p-2"
                                                                                        ),
                                                                                        width=4
                                                                                    ),
                                                                                ],
                                                                                className="gx-2 gy-1 mb-2"
                                                                            ),
                                                                        ],
                                                                        className="inner-card"
                                                                    ),
                                                                    md=5
                                                                ),
                                                                dbc.Col(
                                                                    dcc.Graph(
                                                                        id='grafico-mapa-brasil',
                                                                        config={
                                                                            'displayModeBar': False,
                                                                            'scrollZoom': False
                                                                        },
                                                                        style={
                                                                            'width': '100%',
                                                                            'height': '400px'
                                                                        }
                                                                    ),
                                                                    md=7
                                                                ),
                                                            ],
                                                            className="gx-2 gy-1"
                                                        )
                                                    ],
                                                    className="inner-card"
                                                )
                                            ],
                                            style={'padding': '1rem'}
                                        )
                                    ],
                                    className="graph-card h-100 shadow-sm"
                                ),
                                xs=12,
                                className="mb-4"
                            )
                        ]),

                        # Card gráfico Receita x Custo
                        dbc.Row([
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Div(
                                                                    [
                                                                        html.Img(
                                                                            src="/assets/receitacusto.png",
                                                                            className="card-header-icon"
                                                                        ),
                                                                        html.H5(
                                                                            "Gráfico Receita x Custo",
                                                                            className="card-title",
                                                                            style={"margin-bottom": "0.25rem"}
                                                                        ),
                                                                    ],
                                                                    className="d-flex align-items-center"
                                                                ),
                                                                html.Img(
                                                                    src="/assets/expandir.png",
                                                                    className="expand-icon",
                                                                    id="expand-receita-custo",
                                                                    style={
                                                                        'cursor': 'pointer',
                                                                        'width': '18px',
                                                                        'height': '18px',
                                                                        'margin-left': 'auto'
                                                                    }
                                                                )
                                                            ],
                                                            className="card-header d-flex justify-content-between align-items-center",
                                                            style={'margin-bottom': '0.5rem'}
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Checkbox(
                                                                    id="check-ultimos-12-meses",
                                                                    value=True,  # Alterado de False para True
                                                                    className="custom-checkbox me-1",
                                                                    persistence=True
                                                                ),
                                                                html.Label(
                                                                    "Mostrar últimos 12 meses",
                                                                    htmlFor="check-ultimos-12-meses"
                                                                )
                                                            ],
                                                            className="d-flex align-items-center mb-2"
                                                        ),
                                                        dcc.Graph(
                                                            id='grafico-receita-custo',
                                                            config={'displayModeBar': False},
                                                            className='dash-graph',
                                                            style={'width': '100%', 'height': '100%'}
                                                        )
                                                    ],
                                                    className="inner-card"
                                                )
                                            ],
                                            style={'padding': '1rem'}
                                        )
                                    ],
                                    className="graph-card h-100 shadow-sm"
                                ),
                                xs=12,
                                className="mb-4"
                            ),
                        ]),

                        # Card Waterfall
                        dbc.Row([
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Div(
                                                                    [
                                                                        html.Img(
                                                                            src="/assets/waterfallicon.png",
                                                                            className="card-header-icon"
                                                                        ),
                                                                        html.H5(
                                                                            "Lucros e Perdas (Custos Detalhados)",
                                                                            className="card-title",
                                                                            style={"margin-bottom": "0.25rem"}
                                                                        ),
                                                                    ],
                                                                    className="d-flex align-items-center"
                                                                ),
                                                                html.Img(
                                                                    src="/assets/expandir.png",
                                                                    className="expand-icon",
                                                                    id="expand-waterfall-chart",
                                                                    style={
                                                                        'cursor': 'pointer',
                                                                        'width': '18px',
                                                                        'height': '18px',
                                                                        'margin-left': 'auto'
                                                                    }
                                                                )
                                                            ],
                                                            className="card-header d-flex justify-content-between align-items-center",
                                                            style={'margin-bottom': '0.5rem'}
                                                        ),
                                                        dcc.Graph(
                                                            id='grafico-waterfall',
                                                            config={'displayModeBar': False},
                                                            className='dash-graph',
                                                            style={'width': '100%', 'height': '100%'}
                                                        )
                                                    ],
                                                    className="inner-card"
                                                )
                                            ],
                                            style={'padding': '1rem'}
                                        )
                                    ],
                                    className="graph-card h-100 shadow-sm"
                                ),
                                xs=12,
                                className="mb-4"
                            ),
                        ])
                    ]
                ),
            ]
        ),

        dbc.Tooltip(
            id="tooltip-contas-chave",
            target="btn-info-contas-chave",
            placement="left",
            style={"zIndex": "1050"}
        ),
        
        # Modal para exibir o gráfico de KPI
        create_kpi_dashboard_modal(),
    ],
    fluid=True,
    style={'padding': '1rem'}
)

# Import do painel de KPIs
from .kpis import painel_kpis_layout
from .kpis import register_callbacks

#Import do modulo OKRs
from .okrs import okrs_layout
from .okrs import register_okrs_callbacks

# =================================================================================
# CRIAÇÃO DOS STORES
# =================================================================================
store_estado_selecionado = dcc.Store(id="estado-selecionado", data=None)
dummy_store = dcc.Store(id="dummy-store", data=None)

# OBS: Este store fica só para o DASHBOARD
all_indicators_store = dcc.Store(id='all-indicators-store', data={})

ano_store_kpis = dcc.Store(id='ano-store-painel-kpis', data=None)
periodo_store_kpis = dcc.Store(id='periodo-store-painel-kpis', data=None)
mes_store_kpis = dcc.Store(id='mes-store-painel-kpis', data=None)

# =================================================================================
# INSTÂNCIA PRINCIPAL DO DASH
# =================================================================================
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))   # pasta do projeto
assets_path = os.path.join(ROOT_DIR, "assets")

# ▼ crie (ou use) a lista completa de estilos externos
external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
]

app = Dash(
    __name__,
    external_stylesheets=external_stylesheets,   # ← passa a lista completa
    assets_folder=assets_path,
    suppress_callback_exceptions=True,
    title="Dashboard eShows",
    update_title=None,  # Remove "Updating..." do título
)

# Expor o servidor Flask para Gunicorn
server = app.server

# Configuração da chave secreta para sessões
app.server.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')

# Customizar o HTML index para remover "Loading..."
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        <div id="react-entry-point">
            {%app_entry%}
        </div>
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

#######################################
# DEFINIÇÃO DO LAYOUT PRINCIPAL
#######################################
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    # Stores
    all_indicators_store,
    store_estado_selecionado,
    dummy_store,
    ano_store_kpis,
    periodo_store_kpis,
    mes_store_kpis,
    
    # Container principal que será preenchido dinamicamente
    html.Div(id="main-container"),

    # Container oculto que garante que todos os componentes estejam presentes no DOM
    html.Div([dashboard_layout, painel_kpis_layout, okrs_layout], style={'display': 'none'})
])
    
#######################################
# VALIDATION_LAYOUT (Multi-página)
#######################################
app.validation_layout = html.Div([
    app.layout,
    dashboard_layout,
    painel_kpis_layout,
    okrs_layout
])

# ======================= Roteamento =======================
@app.callback(
    Output("main-container", "children"),
    [Input("url", "pathname")],
    prevent_initial_call=False
)
def render_main_layout(pathname):
    # Se for a página de login, mostra apenas o layout de login (sem sidebar)
    if pathname == "/login":
        return create_login_layout()
    
    # Verifica se o usuário está autenticado
    if 'access_token' not in session:
        return dcc.Location(pathname='/login', id='redirect-to-login')
    
    # Se pathname for None ou "/", redireciona para /dashboard
    if pathname is None or pathname == "/":
        return dcc.Location(pathname='/dashboard', id='redirect-to-dashboard')
    
    # Tratamento para logout
    if pathname == "/logout":
        session.clear()
        return dcc.Location(id='logout-redirect', pathname='/login', refresh=True)
    
    # Para páginas autenticadas, retorna layout com sidebar
    return html.Div([
        sidebar,
        html.Div(
            id="page-content",
            style={
                "margin-left": "260px",
                "padding": "1rem",
                "minHeight": "100vh",
                "overflowY": "auto",
                "paddingBottom": "0px"
            },
            children=render_page_content(pathname)
        )
    ])

# Função auxiliar para renderizar conteúdo das páginas
def render_page_content(pathname):
    # Define os estilos de exibição de cada página de acordo com a rota
    dashboard_style = {'display': 'block'} if pathname == "/dashboard" else {'display': 'none'}
    kpis_style = {'display': 'block'} if pathname == "/kpis" else {'display': 'none'}
    okrs_style = {'display': 'block'} if pathname == "/okrs" else {'display': 'none'}

    return html.Div([
        html.Div(dashboard_layout, style=dashboard_style),
        html.Div(painel_kpis_layout, style=kpis_style),
        html.Div(okrs_layout, style=okrs_style),

        # ---------- Footer (agora dentro) ----------
        html.Div(
            className="py-3 mt-5",
            style={"border-top": "1px solid rgba(18,32,70,0.1)"},
            children=[
                html.P(
                    "© 2025 Eshows | Dashboard Gerencial",
                    className="mb-0 text-center",
                    style={
                        "font-size": "12px",
                        "opacity": "0.7",
                        "color": TEXT_COLOR  # variável já usada no projeto
                    },
                )
            ],
        ),
    ])

# ================== Callback para atualizar base ==================
@app.callback(
    [Output("dummy-store", "data"),
     Output("alert-atualiza-base", "is_open")],
    Input("btn-atualiza-base", "n_clicks"),
    prevent_initial_call=True
)
def atualizar_base(n):
    if not n:
        raise dash.exceptions.PreventUpdate
    global df_eshows, df_base2, df_ocorrencias
    df_eshows = carregar_base_eshows()
    df_base2 = carregar_base2()
    df_ocorrencias = carregar_ocorrencias()
    return {"status": "Bases atualizadas com sucesso!"}, True

# ================== Callbacks de filtros (Dashboard) ==================
@app.callback(
    Output('mes-dropdown-container', 'style'),
    [Input('dashboard-periodo-dropdown', 'value'),
     Input('url', 'pathname')],
    prevent_initial_call=True
)
def exibir_ou_ocultar_mes(periodo, pathname):
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    if periodo == 'Mês Aberto':
        return {'display': 'block'}
    return {'display': 'none'}

@app.callback(
    Output('dashboard-periodo-dropdown','value'),
    [Input('dashboard-ano-dropdown','value'),
     State('dashboard-periodo-dropdown','value'),
     Input('url','pathname')],
    prevent_initial_call=True
)
def ajustar_periodo_ao_ano(ano_sel, periodo_atual, pathname):
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    ano_corrente = datetime.now().year
    if ano_sel < ano_corrente:
        return 'Ano Completo'
    elif ano_sel == ano_corrente:
        return 'YTD'
    else:
        return periodo_atual

@app.callback(
    Output('date-range-picker-container','style'),
    [Input('dashboard-periodo-dropdown','value'),
     Input('url','pathname')],
    prevent_initial_call=True
)
def toggle_custom_range(periodo_value, pathname):
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    if periodo_value == 'custom-range':
        return {'display':'block'}
    return {'display':'none'}

@app.callback(
    [Output("dashboard-date-range-picker", "start_date"),
     Output("dashboard-date-range-picker", "end_date")],
    [Input("dashboard-periodo-dropdown", "value")],
    prevent_initial_call=True
)
def defaultar_datas_custom(periodo):
    if periodo == "custom-range":
        hoje = datetime.now().date()
        return datetime(hoje.year, 1, 1).date(), hoje
    # Saiu do custom-range → limpa
    return None, None

@app.callback(
    Output('date-range-picker-compare-container','style'),
    [Input('dashboard-comparar-dropdown','value'),
     Input('url','pathname')],
    prevent_initial_call=True
)
def toggle_custom_range_compare(comp_value, pathname):
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    if comp_value == 'custom-compare':
        return {'display':'block'}
    return {'display':'none'}

@app.callback(
    [
        Output("toggle-indicator", "style"),
        Output("cards-container", "className"),
        Output("charts-container", "className")
    ],
    [
        Input("url", "pathname"),  # <--- Adicionamos aqui
        Input("btn-cards", "n_clicks"),
        Input("btn-charts", "n_clicks")
    ],
    prevent_initial_call=True
)
def toggle_switch(pathname, n_cards, n_charts):
    # 1) Se não estiver na página /dashboard => não faz nada
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    # 2) Lógica normal do seu callback
    ctx = dash.callback_context
    if not ctx.triggered:
        return (
            {"left": "4px"},
            "fade-container fade-enter",
            "fade-container fade-exit"
        )
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "btn-charts":
        return (
            {"left": "120px"},
            "fade-container fade-exit",
            "fade-container fade-enter"
        )
    else:
        return (
            {"left": "4px"},
            "fade-container fade-enter",
            "fade-container fade-exit"
        )

@app.callback(
    Output("tooltip-contas-chave", "children"),
    [
        Input("url", "pathname"),  # <--- Adicionamos também aqui
        Input('dashboard-ano-dropdown','value'),
        Input('dashboard-periodo-dropdown','value'),
        Input('dashboard-mes-dropdown','value'),
        Input('dashboard-date-range-picker','start_date'),
        Input('dashboard-date-range-picker','end_date'),
    ],
    prevent_initial_call=False
)
def atualizar_tooltip_contas_chave(
    pathname, ano, periodo, mes,
    start_date_main, end_date_main
):
    # 1) Se não estiver na página /dashboard => não faz nada
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    # 2) Resto da lógica original
    if df_eshows is None or df_eshows.empty or "Grupo" not in df_eshows.columns:
        return "Não há grupos / colunas."

    top5_info = obter_top5_grupos_ano_anterior(df_eshows, ano)
    if not top5_info:
        return "Nenhum grupo no ano anterior."

    tooltip_content = [
        html.Span("Top5 Grupos Aa", style={'color': '#FDB03D', 'font-weight': 'bold'}),
        html.Br()
    ]
    for i, (grp, fatg) in enumerate(top5_info):
        color = '#FFFFFF' if i % 2 == 0 else '#FC4F22'
        fatg_formatado = formatar_valor_utils(fatg, 'monetario')
        line_str = f"{grp} : {fatg_formatado}"
        tooltip_content.append(html.Span(line_str, style={'color': color}))
        tooltip_content.append(html.Br())

    return tooltip_content

# =================================================================================
# AQUI VAI O CONJUNTO DE CALLBACKS DO DASHBOARD (KPIs)
# =================================================================================
@app.callback(
    [
        Output('kpi-gmv-col','children'),
        Output('kpi-numshows-col','children'),
        Output('kpi-ticket-col','children'),
        Output('kpi-cidades-col','children'),

        Output('kpi-fat-col','children'),
        Output('kpi-takerate-gmv-col','children'),
        Output('kpi-custos-col','children'),
        Output('kpi-lucro-col','children'),

        Output('kpi-novospalcos-col','children'),
        Output('kpi-fatnovospalcos-col','children'),
        Output('kpi-lifetimemedio-col','children'),
        Output('kpi-churn-novospalcos-col','children'),

        Output('kpi-ka-fat-col','children'),
        Output('kpi-ka-novospalcos-col','children'),
        Output('kpi-ka-takerate-col','children'),
        Output('kpi-ka-churn-col','children'),

        Output('kpi-palcos-ativos-col','children'),
        Output('kpi-artistas-ativos-col','children'),
        Output('kpi-palcosvazios-col','children'),
        Output('kpi-errosop-col','children'),

        Output('cards-pessoas','children'),

        Output('periodo-analisado','children'),

        # Armazena todos os indicadores (simples + históricos)
        Output('all-indicators-store', 'data'),
    ],
    [
        Input('dashboard-ano-dropdown','value'),
        Input('dashboard-periodo-dropdown','value'),
        Input('dashboard-mes-dropdown','value'),
        Input('dashboard-date-range-picker','start_date'),
        Input('dashboard-date-range-picker','end_date'),
        Input('dashboard-comparar-dropdown','value'),
        Input('dashboard-date-range-picker-compare','start_date'),
        Input('dashboard-date-range-picker-compare','end_date'),
        Input("dummy-store","data"),   # para atualizar quando a base recarrega
        Input("url","pathname")        # para checar a rota atual
    ],
    [State('all-indicators-store','data')],  # Lê o store já existente
    prevent_initial_call=True
)
def atualizar_kpis(
    ano, periodo, mes,
    start_date_main, end_date_main,
    comparar_opcao, start_date_compare, end_date_compare,
    dummy_data,
    current_pathname,
    existing_indicators,
):
    # ————————————————————————————————————————————————————————————————
    # 0) Só roda no /dashboard
    # ————————————————————————————————————————————————————————————————
    if current_pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    # ————————————————————————————————————————————————————————————————
    # 1) Intervalo PRINCIPAL
    # ————————————————————————————————————————————————————————————————
    custom_principal = None
    if periodo == "custom-range":
        if not (start_date_main and end_date_main):
            raise dash.exceptions.PreventUpdate
        custom_principal = (
            pd.to_datetime(start_date_main).normalize(),
            pd.to_datetime(end_date_main).normalize(),
        )

    df_principal = filtrar_periodo_principal(
        df_eshows, ano, periodo, mes, custom_principal
    )
    if df_principal.empty:
        raise dash.exceptions.PreventUpdate

    label_princ = (
        formatar_range_legivel(*custom_principal)
        if custom_principal
        else mes_nome_intervalo(df_principal, periodo)
    )

    # ————————————————————————————————————————————————————————————————
    # 2) Intervalo de COMPARAÇÃO
    # ————————————————————————————————————————————————————————————————
    custom_comp = None
    ano_cmp, per_cmp, mes_cmp = ano - 1, periodo, mes        # default: ano-1

    if comparar_opcao == "periodo_anterior":
        ini_p = get_period_start(ano, periodo, mes, custom_principal)
        fim_p = get_period_end  (ano, periodo, mes, custom_principal)

        delta  = fim_p - ini_p            # mesma duração
        fim_c  = ini_p - timedelta(days=1)
        ini_c  = fim_c - delta

        custom_comp = (ini_c, fim_c)
        per_cmp     = "custom-range"
        ano_cmp, mes_cmp = ini_c.year, ini_c.month

    elif comparar_opcao == "custom-compare":
        if not (start_date_compare and end_date_compare):
            raise dash.exceptions.PreventUpdate
        custom_comp = (
            pd.to_datetime(start_date_compare).normalize(),
            pd.to_datetime(end_date_compare).normalize()
        )
        per_cmp = "custom-range"
        ano_cmp, mes_cmp = custom_comp[0].year, custom_comp[0].month
    # (caso 'ano_anterior' nada muda: ano_cmp = ano-1)

    # ─── aliases p/ partes de código que ainda usam os nomes antigos ──
    custom_range_principal_tuple  = custom_principal
    custom_range_comparacao_tuple = custom_comp
    # ------------------------------------------------------------------

    # ————————————————————————————————————————————————————————————————
    # 3) DataFrame comparativo
    # ————————————————————————————————————————————————————————————————
    df_comp = filtrar_periodo_principal(
        df_eshows, ano_cmp, per_cmp, mes_cmp, custom_comp
    )

    # rótulo do período comparado
    if custom_comp:
        label_comp = formatar_range_legivel(*custom_comp)
    elif comparar_opcao == "periodo_anterior":
        label_comp = mes_nome_intervalo(df_comp, per_cmp)
    else:                                  # ano_anterior (fallback)
        label_comp = f"{periodo} {ano-1}"

    # ————————————————————————————————————————————————————————————————
    # 4) Ajustes de coluna 'Grupo' e demais pré-requisitos
    # ————————————————————————————————————————————————————————————————
    df_principal = ensure_grupo_col(df_principal)
    df_comp      = ensure_grupo_col(df_comp)

    # -----------------------
    # Cálculos dos indicadores simples
    # -----------------------

    # Palcos Ativos
    palcos_ativos = df_principal["Id da Casa"].nunique() if not df_principal.empty else 0
    palcos_ativos_comp = df_comp["Id da Casa"].nunique() if not df_comp.empty else 0
    var_palcos_ativos = calcular_variacao_percentual(palcos_ativos, palcos_ativos_comp) if palcos_ativos_comp is not None else None

    # Artistas Ativos
    artistas_ativos = df_principal["Nome do Artista"].nunique() if not df_principal.empty and "Nome do Artista" in df_principal.columns else 0
    artistas_ativos_comp = df_comp["Nome do Artista"].nunique() if not df_comp.empty and "Nome do Artista" in df_comp.columns else 0
    var_artistas_ativos = calcular_variacao_percentual(artistas_ativos, artistas_ativos_comp) if artistas_ativos_comp is not None and artistas_ativos_comp > 0 else None

    # Ocorrências (excluindo "Leve")
    ocorrencias_count = 0
    var_ocorrencias = None
    if df_ocorrencias is not None and not df_ocorrencias.empty:
        df_occ_temp = df_ocorrencias.rename(columns={"DATA": "Data"}).copy()
        df_occ_princ = filtrar_periodo_principal(df_occ_temp, ano, periodo, mes, (start_date_main, end_date_main))
        if not df_occ_princ.empty and "TIPO" in df_occ_princ.columns:
            df_occ_princ = df_occ_princ[df_occ_princ["TIPO"] != "Leve"]
            ocorrencias_count = df_occ_princ["ID_OCORRENCIA"].nunique() if "ID_OCORRENCIA" in df_occ_princ.columns else 0

        df_occ_comp = filtrar_periodo_comparacao(df_occ_temp, ano, periodo, mes, comparar_opcao, (start_date_compare, end_date_compare))
        ocorrencias_comp = 0
        if not df_occ_comp.empty and "TIPO" in df_occ_comp.columns:
            df_occ_comp = df_occ_comp[df_occ_comp["TIPO"] != "Leve"]
            ocorrencias_comp = df_occ_comp["ID_OCORRENCIA"].nunique() if "ID_OCORRENCIA" in df_occ_comp.columns else 0

        if ocorrencias_comp is not None and ocorrencias_comp > 0:
            var_ocorrencias = calcular_variacao_percentual(ocorrencias_count, ocorrencias_comp)

    # Palcos Vazios
    palcos_vazios = 0
    var_palcosvazios = None
    logger.debug("[DEBUG] => Iniciando cálculo de Palcos Vazios")
    if df_ocorrencias is not None and not df_ocorrencias.empty:
        df_occ_temp2 = df_ocorrencias.rename(columns={"DATA": "Data"}).copy()
        df_occ_princ2 = filtrar_periodo_principal(df_occ_temp2, ano, periodo, mes, (start_date_main, end_date_main))
        if not df_occ_princ2.empty:
            if "TIPO" in df_occ_princ2.columns:
                df_occ_princ2 = df_occ_princ2[df_occ_princ2["TIPO"] == "Palco vazio"]
                if "ID_OCORRENCIA" in df_occ_princ2.columns:
                    palcos_vazios = df_occ_princ2["ID_OCORRENCIA"].nunique()
                else:
                    palcos_vazios = len(df_occ_princ2)
        df_occ_comp2 = filtrar_periodo_comparacao(df_occ_temp2, ano, periodo, mes, comparar_opcao, (start_date_compare, end_date_compare))
        palcos_vazios_comp = 0
        if not df_occ_comp2.empty:
            if "TIPO" in df_occ_comp2.columns:
                df_occ_comp2 = df_occ_comp2[df_occ_comp2["TIPO"] == "Palco vazio"]
                if "ID_OCORRENCIA" in df_occ_comp2.columns:
                    palcos_vazios_comp = df_occ_comp2["ID_OCORRENCIA"].nunique()
                else:
                    palcos_vazios_comp = len(df_occ_comp2)
        if palcos_vazios_comp is not None and palcos_vazios_comp > 0:
            var_palcosvazios = calcular_variacao_percentual(palcos_vazios, palcos_vazios_comp)
        logger.debug("[DEBUG] => Final palcos_vazios = %s, var_palcosvazios = %s", palcos_vazios, var_palcosvazios)
    else:
        logger.debug("[DEBUG] => df_ocorrencias está None ou vazio.")

    # Erros Operacionais (Op. Shows)
    erros_op = filtrar_base2_op_shows(df_base2, ano, periodo, mes)
    erros_op_comp = filtrar_base2_op_shows_compare(df_base2, ano, periodo, mes, comparar_opcao)
    var_errosop = calcular_variacao_percentual(erros_op, erros_op_comp) if erros_op_comp is not None else None

    # Pessoas / RH
    df_pessoas = carregar_pessoas()
    met_princ, met_comp_rh = metricas_rh_quick( # Renomeado met_comp para met_comp_rh para evitar conflito
        ano, periodo, mes,
        comparar_opcao=comparar_opcao,
        custom_range=custom_range_principal_tuple if periodo == 'custom-range' else None,
        df_pessoas_global=df_pessoas
    )

    def pct(a, b):
        return calcular_variacao_percentual(a, b) if (b not in (None, 0)) else None

    # GMV e Número de Shows
    df_principal["Valor Total do Show"] = pd.to_numeric(df_principal["Valor Total do Show"], errors='coerce').fillna(0)
    gmv = df_principal["Valor Total do Show"].sum() if not df_principal.empty else 0
    num_shows = df_principal["Id do Show"].nunique() if not df_principal.empty else 0
    if not df_comp.empty:
        df_comp["Valor Total do Show"] = pd.to_numeric(df_comp["Valor Total do Show"], errors='coerce').fillna(0)
    gmv_comp = df_comp["Valor Total do Show"].sum() if not df_comp.empty else 0
    num_shows_comp = df_comp["Id do Show"].nunique() if not df_comp.empty else 0
    var_gmv = calcular_variacao_percentual(gmv, gmv_comp) if gmv_comp is not None else None
    var_num = calcular_variacao_percentual(num_shows, num_shows_comp) if num_shows_comp is not None else None

    # Ticket Médio
    ticket = (gmv / num_shows) if num_shows > 0 else None
    ticket_comp = (gmv_comp / num_shows_comp) if num_shows_comp > 0 else None
    var_ticket = calcular_variacao_percentual(ticket, ticket_comp) if (ticket_comp is not None and ticket_comp != 0 and ticket is not None) else None

    # Cidades
    cidades = df_principal["Cidade"].nunique() if not df_principal.empty else 0
    cidades_comp = df_comp["Cidade"].nunique() if not df_comp.empty else 0
    var_cidades = calcular_variacao_percentual(cidades, cidades_comp) if cidades_comp is not None and cidades_comp > 0 else None

    # Faturamento
    colunas_fat = [
        "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
        "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    fat = 0.0
    if not df_principal.empty:
        valid_cols = [c for c in colunas_fat if c in df_principal.columns]
        if valid_cols:
            df_fat_f = df_principal[valid_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            fat = df_fat_f.sum().sum()
    fat_comp = 0.0
    if not df_comp.empty:
        valid_cols_c = [c for c in colunas_fat if c in df_comp.columns]
        if valid_cols_c:
            df_fat_c = df_comp[valid_cols_c].apply(pd.to_numeric, errors='coerce').fillna(0)
            fat_comp = df_fat_c.sum().sum()
    var_fat = calcular_variacao_percentual(fat, fat_comp) if fat_comp is not None and fat_comp != 0 else None

    # Take Rate GMV
    take_rate_gmv = None
    if gmv > 0 and "Comissão B2B" in df_principal.columns:
        soma_b2b = pd.to_numeric(df_principal["Comissão B2B"], errors='coerce').fillna(0).sum()
        take_rate_gmv = (soma_b2b / gmv)*100 if gmv > 0 else None
    take_rate_gmv_comp = None
    if gmv_comp > 0 and "Comissão B2B" in df_comp.columns:
        soma_b2b_c = pd.to_numeric(df_comp["Comissão B2B"], errors='coerce').fillna(0).sum()
        take_rate_gmv_comp = (soma_b2b_c / gmv_comp)*100 if gmv_comp > 0 else None
    var_takegmv = calcular_variacao_percentual(take_rate_gmv, take_rate_gmv_comp) if (take_rate_gmv_comp is not None and take_rate_gmv_comp != 0) else None

    # Custos Totais e Lucro
    custos_tot = filtrar_base2(df_base2, ano, periodo, mes, custom_range=custom_range_principal_tuple) # Passa custom_range
    custos_comp = filtrar_base2_comparacao(df_base2, ano, periodo, mes, comparar_opcao, custom_range_comparacao=custom_range_comparacao_tuple) # Passa custom_range_comparacao
    var_custos = calcular_variacao_percentual(custos_tot, custos_comp) if (custos_tot is not None and custos_comp is not None and custos_comp != 0) else None
    lucro_liquido = (fat - custos_tot) if (custos_tot is not None) else None
    lucro_liquido_comp = (fat_comp - custos_comp) if (custos_comp is not None) else None
    var_lucro = None
    if lucro_liquido is not None and lucro_liquido_comp is not None:
        var_lucro = calcular_variacao_percentual(lucro_liquido, lucro_liquido_comp)

    # KPIs de Novos Palcos
    df_new_period = filtrar_novos_palcos_por_periodo(df_casas_earliest, ano, periodo, mes, custom_range_principal_tuple)
    novos_palcos = df_new_period.shape[0] if not df_new_period.empty else 0
    
    df_new_period_comp = filtrar_novos_palcos_por_comparacao(df_casas_earliest, ano, periodo, mes, comparar_opcao, custom_range_comparacao_tuple)
    comp_np = df_new_period_comp.shape[0] if not df_new_period_comp.empty else 0
    var_novospalcos = calcular_variacao_percentual(novos_palcos, comp_np) if comp_np is not None and comp_np > 0 else None

    # Lifetime Médio (Novos)
    lifetime_medio_str = "-"
    var_lifetime = None
    def calc_lifetime(novos_ids):
        if df_casas_earliest is None or df_casas_latest is None:
            return None
        df_m = pd.merge(
            df_casas_earliest[["Id da Casa", "EarliestShow"]],
            df_casas_latest[["Id da Casa", "LastShow"]],
            on="Id da Casa", 
            how="inner"
        )
        df_m = df_m[df_m["Id da Casa"].isin(novos_ids)]
        if df_m.empty:
            return None
        df_m["DiffDays"] = (df_m["LastShow"] - df_m["EarliestShow"]).dt.days
        df_m = df_m[df_m["DiffDays"] >= 0]
        if df_m.empty:
            return None
        return df_m["DiffDays"].mean()
    if not df_new_period.empty:
        nids = df_new_period["Id da Casa"].unique()
        avg_days = calc_lifetime(nids)
        if avg_days is not None:
            if avg_days < 30:
                lifetime_medio_str = f"{int(avg_days)}d"
            else:
                meses_ = avg_days/30
                if meses_ < 12:
                    lifetime_medio_str = f"{meses_:.1f}m"
                else:
                    anos_ = meses_/12
                    lifetime_medio_str = f"{anos_:.1f}y"
    if not df_new_period_comp.empty: # Usa df_new_period_comp
        nids_comp = df_new_period_comp["Id da Casa"].unique()
        avg_days_comp = calc_lifetime(nids_comp)
        if avg_days_comp and avg_days_comp > 0 and lifetime_medio_str != "-":
            avg_days_principal = calc_lifetime(df_new_period["Id da Casa"].unique())
            if avg_days_principal is not None:
                var_lifetime = calcular_variacao_percentual(avg_days_principal, avg_days_comp)

    # Faturamento dos Novos Palcos
    fat_novos = 0.0
    if not df_principal.empty and not df_new_period.empty:
        novos_ids_ = df_new_period["Id da Casa"].unique()
        df_princ_novos = df_principal[df_principal["Id da Casa"].isin(novos_ids_)]
        if not df_princ_novos.empty:
            valid_cols_n = [c for c in colunas_fat if c in df_princ_novos.columns]
            if valid_cols_n:
                df_princ_novos = df_princ_novos[valid_cols_n].apply(pd.to_numeric, errors='coerce').fillna(0)
                fat_novos_ = df_princ_novos.sum().sum()
                fat_novos = float(fat_novos_)
    fat_novos_comp = 0.0
    if not df_comp.empty and not df_new_period_comp.empty: # Usa df_new_period_comp
        novos_ids_comp_ = df_new_period_comp["Id da Casa"].unique() # Usa df_new_period_comp
        df_comp_novos = df_comp[df_comp["Id da Casa"].isin(novos_ids_comp_)]
        if not df_comp_novos.empty:
            valid_cols_nc = [c for c in colunas_fat if c in df_comp_novos.columns]
            if valid_cols_nc:
                df_comp_novos = df_comp_novos[valid_cols_nc].apply(pd.to_numeric, errors='coerce').fillna(0)
                fat_novos_comp_ = df_comp_novos.sum().sum()
                fat_novos_comp = float(fat_novos_comp_)
    var_fat_novos = calcular_variacao_percentual(fat_novos, fat_novos_comp) if fat_novos_comp is not None and fat_novos_comp > 0 else None

    # Churn de Novos Palcos
    churn_data_novos_palcos = get_churn_variables(
        ano, periodo, mes,
        custom_range=custom_range_principal_tuple,
        df_eshows_global=df_eshows, # Passando df_eshows filtrado para o período principal
        # start_date e end_date são redundantes se custom_range é bem tratado dentro de get_churn_variables
        # A função get_churn_variables pode precisar de ajuste para priorizar custom_range
        # ou podemos manter start_date/end_date aqui se forem usados diretamente por calcular_churn dentro dela
        start_date=custom_range_principal_tuple[0] if custom_range_principal_tuple else None,
        end_date=custom_range_principal_tuple[1] if custom_range_principal_tuple else None,
        # Adicionar lógica para filtrar por apenas novos palcos se necessário, ou ajustar get_churn_variables
        # Esta chamada é para CHURN GERAL, não especificamente de novos palcos.
        # Para CHURN DE NOVOS PALCOS, o cálculo original era:
        # churn_count_novos = calcular_churn_novos_palcos(...)
        # Vamos manter o cálculo específico para churn de novos palcos por enquanto, 
        # a menos que get_churn_variables seja adaptada para isso.
    )
    # O KPI no dashboard é "Churn de Novos Palcos", não churn geral.
    # Portanto, o cálculo original de `calcular_churn_novos_palcos` deve ser mantido e não substituído por `get_churn_variables` diretamente aqui.
    # A instrução era "troque cálculo manual de NRR/Churn por get_nrr_variables(...) e get_churn_variables(...)"
    # Isso se aplica ao Churn geral, não ao Churn de Novos Palcos que tem uma lógica diferente.
    # Se houver um card de "Churn" geral, ele seria substituído. No layout atual, parece que não há.
    # O card existente é "Churn de Novos Palcos".

    # Mantendo cálculo original para Churn de Novos Palcos:
    churn_count_novos = calcular_churn_novos_palcos(
        ano,
        periodo,
        mes,
        custom_range_principal_tuple[0] if custom_range_principal_tuple else None, # start_date_main
        custom_range_principal_tuple[1] if custom_range_principal_tuple else None, # end_date_main
        df_casas_earliest,
        df_eshows,
        df_new_period, # Novos palcos do período principal
        dias_sem_show=45,
        uf=None
    )
    var_churn_novos = None
    churn_count_novos_comp = 0
    # Lógica de comparação para churn_count_novos_comp
    sdt_comp_churn_np, edt_comp_churn_np = None, None
    ano_churn_comp_np, periodo_churn_comp_np, mes_churn_comp_np = ano, periodo, mes

    if comparar_opcao == 'ano_anterior':
        ano_churn_comp_np = ano - 1
        if custom_range_principal_tuple:
            sdt_comp_churn_np = custom_range_principal_tuple[0] - pd.DateOffset(years=1)
            edt_comp_churn_np = custom_range_principal_tuple[1] - pd.DateOffset(years=1)
    elif comparar_opcao == 'periodo_anterior':
        periodo_churn_comp_np, ano_churn_comp_np, mes_churn_comp_np = calcular_periodo_anterior(ano, periodo, mes)
        if custom_range_principal_tuple:
            duration = custom_range_principal_tuple[1] - custom_range_principal_tuple[0]
            edt_comp_churn_np = custom_range_principal_tuple[0] - pd.Timedelta(days=1)
            sdt_comp_churn_np = edt_comp_churn_np - duration
    elif comparar_opcao == 'custom-compare' and custom_range_comparacao_tuple:
        sdt_comp_churn_np, edt_comp_churn_np = custom_range_comparacao_tuple
        # O ano/periodo/mes para custom_compare podem ser derivados das datas de comparação se necessário
        if sdt_comp_churn_np:
            ano_churn_comp_np = sdt_comp_churn_np.year
            mes_churn_comp_np = sdt_comp_churn_np.month
            periodo_churn_comp_np = "custom-range" # Indica que é custom
    
    df_new_period_comp_churn = filtrar_novos_palcos_por_periodo(df_casas_earliest, ano_churn_comp_np, periodo_churn_comp_np, mes_churn_comp_np, (sdt_comp_churn_np, edt_comp_churn_np))

    if not df_new_period_comp_churn.empty:
        churn_count_novos_comp = calcular_churn_novos_palcos(
            ano_churn_comp_np,
            periodo_churn_comp_np,
            mes_churn_comp_np,
            sdt_comp_churn_np,
            edt_comp_churn_np,
            df_casas_earliest,
            df_eshows, 
            df_new_period_comp_churn, # Novos palcos do período de comparação
            dias_sem_show=45,
            uf=None
        )
    if churn_count_novos_comp is not None and churn_count_novos_comp > 0:
        var_churn_novos = calcular_variacao_percentual(churn_count_novos, churn_count_novos_comp)


    # Contas Chave (Top5 Grupos do ano anterior)
    logger.info("[atualizar_kpis] INICIANDO CÁLCULO KPIs KA")
    top5_list = obter_top5_grupos_ano_anterior(df_eshows, ano)
    logger.debug("[atualizar_kpis] Debug: Top 5 List para %s: %s", ano-1, top5_list)

    fat_ka = 0.0
    fat_ka_comp = 0.0
    var_fat_ka = None
    np_ka = 0
    np_ka_comp = 0
    var_np_ka = None
    take_rate_ka = 0.0
    take_rate_ka_comp = 0.0
    var_takerate_ka = None
    churn_ka_count = 0
    churn_ka_comp = 0
    var_churn_ka = None

    # NRR para Contas Chave (substituindo cálculo manual, se houver um card para isso)
    if top5_list:
        logger.debug("[atualizar_kpis] Debug: top5_list NÃO está vazia. Calculando KAs...")
        grp_names = [g[0] for g in top5_list]
        logger.debug("[atualizar_kpis] Debug: KA Group Names: %s", grp_names)

        # Faturamento KA
        logger.debug("[atualizar_kpis] Debug: Calculando Faturamento KA...")
        fat_ka = faturamento_dos_grupos(df_principal, top5_list)
        fat_ka_comp = faturamento_dos_grupos(df_comp, top5_list)
        logger.debug("[atualizar_kpis] Debug: Fat KA Princ: %s, Comp: %s", fat_ka, fat_ka_comp)
        var_fat_ka = calcular_variacao_percentual(fat_ka, fat_ka_comp) if fat_ka_comp is not None else None

        # Novos Palcos KA
        logger.debug("[atualizar_kpis] Debug: Calculando Novos Palcos KA...")
        np_ka = novos_palcos_dos_grupos(df_new_period, df_principal, top5_list)
        np_ka_comp = novos_palcos_dos_grupos(df_new_period_comp, df_comp, top5_list) # Usa df_new_period_comp
        logger.debug("[atualizar_kpis] Debug: NP KA Princ: %s, Comp: %s", np_ka, np_ka_comp)
        var_np_ka = calcular_variacao_percentual(np_ka, np_ka_comp) if np_ka_comp is not None else None

        # Take Rate KA
        logger.debug("[atualizar_kpis] Debug: Calculando Take Rate KA...")
        gmv_ka = 0.0
        gmv_ka_comp = 0.0
        df_ka_princ = df_principal[df_principal['Grupo'].isin(grp_names)]
        df_ka_comp = df_comp[df_comp['Grupo'].isin(grp_names)]
        if not df_ka_princ.empty:
            gmv_ka = df_ka_princ['Valor Total do Show'].sum()
        if not df_ka_comp.empty:
            gmv_ka_comp = df_ka_comp['Valor Total do Show'].sum()
        logger.debug("[atualizar_kpis] Debug: GMV KA Princ: %s, Comp: %s", gmv_ka, gmv_ka_comp)

        take_rate_ka = (fat_ka / gmv_ka) * 100 if gmv_ka > 0 else 0
        take_rate_ka_comp = (fat_ka_comp / gmv_ka_comp) * 100 if gmv_ka_comp > 0 else 0
        logger.debug("[atualizar_kpis] Debug: Take Rate KA Princ: %s, Comp: %s", take_rate_ka, take_rate_ka_comp)
        var_takerate_ka = calcular_variacao_percentual(take_rate_ka, take_rate_ka_comp) if take_rate_ka_comp is not None else None

        # Churn KA
        logger.debug("[atualizar_kpis] Debug: Calculando Churn KA...")
        churn_ka_count = get_churn_ka_for_period(ano, periodo, mes, top5_list, start_date_main, end_date_main)
        logger.debug("[atualizar_kpis] Debug: Churn KA Princ: %s", churn_ka_count)

        # Calcular Churn KA Comparativo
        logger.debug("[atualizar_kpis] Debug: Calculando Churn KA Comparativo...")
        if comparar_opcao == 'ano_anterior':
            logger.debug("[atualizar_kpis] Debug: Churn Comp - Ano Anterior")
            churn_ka_comp = get_churn_ka_for_period(ano-1, periodo, mes, top5_list) # Não passa datas custom
        elif comparar_opcao == 'periodo_anterior':
            logger.debug("[atualizar_kpis] Debug: Churn Comp - Período Anterior")
            per_ant, ano_ant, mes_ant = calcular_periodo_anterior(ano, periodo, mes)
            churn_ka_comp = get_churn_ka_for_period(ano_ant, per_ant, mes_ant, top5_list) # Não passa datas custom
        elif comparar_opcao == 'custom-compare' and start_date_compare and end_date_compare:
            logger.debug("[atualizar_kpis] Debug: Churn Comp - Custom Compare")
            # Passa as datas customizadas para o período de comparação
            # A função get_churn_ka_for_period usa (ano, periodo, mes) apenas como fallback se custom_range não for passado
            # Podemos passar ano/periodo/mes atuais ou do custom, mas as datas é que mandam.
            # Passando ano/periodo/mes do range custom para clareza:
            dt_comp_start = pd.to_datetime(start_date_compare)
            churn_ka_comp = get_churn_ka_for_period(
                dt_comp_start.year, # Usa ano/periodo/mes do custom para clareza
                'custom-range',     # Indica que é custom
                dt_comp_start.month,
                top5_list,
                start_date_compare, # Passa as datas custom
                end_date_compare
            )
        else: # Caso 'sem_comparacao' ou datas custom inválidas
            logger.debug("[atualizar_kpis] Debug: Churn Comp - Sem Comparação ou Datas Inválidas")
            churn_ka_comp = 0

        logger.debug("[atualizar_kpis] Debug: Churn KA Comp (%s): %s", comparar_opcao, churn_ka_comp)
        var_churn_ka = calcular_variacao_percentual(churn_ka_count, churn_ka_comp) if churn_ka_comp is not None else None
    else:
        logger.debug("[atualizar_kpis] Debug: top5_list está vazia para %s. KPIs de KA serão zero.", ano-1)

    # Palcos Ativos
    palcos_ativos = df_principal["Id da Casa"].nunique() if not df_principal.empty else 0

    # -----------------------
    # Criação dos cards
    # -----------------------
    card_gmv        = criar_card_kpi_shows("GMV", gmv, var_gmv, label_comp, format_type='monetario')
    card_numshows   = criar_card_kpi_shows("Número de Shows", num_shows, var_num, label_comp, format_type='numero')
    card_ticket     = criar_card_kpi_shows("Ticket Médio", ticket, var_ticket, label_comp, format_type='monetario')
    card_cidades    = criar_card_kpi_shows("Número de Cidades", cidades, var_cidades, label_comp, format_type='numero')

    card_fat        = criar_card_kpi_shows("Faturamento Eshows", fat, var_fat, label_comp, format_type='monetario')
    card_takegmv    = criar_card_kpi_shows("Take Rate GMV", take_rate_gmv, var_takegmv, label_comp, format_type='percentual')
    card_custos     = criar_card_kpi_shows("Custos Totais", custos_tot, var_custos, label_comp, format_type='monetario', is_negative=True)
    card_lucro      = criar_card_kpi_shows("Lucro Líquido", lucro_liquido, var_lucro, label_comp, format_type='monetario')

    card_novospalcos    = criar_card_kpi_shows("Novos Palcos", novos_palcos, var_novospalcos, label_comp, format_type='numero')
    card_fatnovospalcos = criar_card_kpi_shows("Fat. Novos Palcos", fat_novos, var_fat_novos, label_comp, format_type='monetario')
    card_lifetimemedio  = criar_card_kpi_shows("Life Time Médio", lifetime_medio_str, var_lifetime, label_comp, format_type='numero')
    card_churn_novospalcos = criar_card_kpi_shows("Churn de Novos Palcos", churn_count_novos, var_churn_novos, label_comp, format_type='numero', is_negative=True)

    card_ka_fat         = criar_card_kpi_shows("Faturamento KA", fat_ka, var_fat_ka, label_comp, format_type='monetario')
    card_ka_np          = criar_card_kpi_shows("Novos Palcos KA", np_ka, var_np_ka, label_comp, format_type='numero')
    card_ka_takerate    = criar_card_kpi_shows("Take Rate KA", take_rate_ka, var_takerate_ka, label_comp, format_type='percentual')
    card_ka_churn       = criar_card_kpi_shows("Churn KA", churn_ka_count, var_churn_ka, label_comp, format_type='numero', is_negative=True)

    card_palcos_ativos  = criar_card_kpi_shows("Palcos Ativos", palcos_ativos, var_palcos_ativos, label_comp, format_type='numero')
    card_artistas_ativos = criar_card_kpi_shows("Artistas Ativos", artistas_ativos, var_artistas_ativos, label_comp, format_type='numero')
    card_palcos_vazios  = criar_card_kpi_shows("Palcos Vazios", palcos_vazios, var_palcosvazios, label_comp, format_type='numero')
    card_erros_op       = criar_card_kpi_shows("Erros Operacionais", erros_op, var_errosop, label_comp, format_type='monetario', is_negative=True)

    card_palcos_ativos  = criar_card_kpi_shows("Palcos Ativos", palcos_ativos, var_palcos_ativos, label_comp, format_type='numero')
    # card_artistas_ativos já definido acima - não precisamos redefini-lo
    card_palcos_vazios  = criar_card_kpi_shows("Palcos Vazios", palcos_vazios, var_palcosvazios, label_comp, format_type='numero')
    card_erros_op       = criar_card_kpi_shows("Erros Operacionais", erros_op, var_errosop, label_comp, format_type='monetario', is_negative=True)

    # Cards da seção Pessoas
    cards_pessoas = [
        dbc.Col(
            criar_card_kpi_shows(
                "Nº de Colaboradores",
                met_princ["n_func"],
                pct(met_princ["n_func"], (met_comp_rh or {}).get("n_func")),
                label_comp,
                "numero"
            ),
            width=3
        ),

        dbc.Col(
            criar_card_kpi_shows(
                "Tempo Médio de Casa",
                met_princ["tempo_medio_casa_fmt"],                # string já formatada
                pct(met_princ["tempo_medio_casa"],                # usa valor numérico em dias
                    (met_comp_rh or {}).get("tempo_medio_casa")),
                label_comp,
                "tempo"                                           # novo tipo p/ formatação, vide criar_card_kpi_shows
            ),
            width=3
        ),

        dbc.Col(
            criar_card_kpi_shows(
                "Receita por Colaborador",
                met_princ["rpc_fmt"],                       # string pronta "R$ 4,3 k"
                pct(met_princ["receita_por_colaborador"],
                    (met_comp_rh or {}).get("receita_por_colaborador")),
                label_comp,
                "monetario"                                # continua monetário
            ),
            width=3
        ),

        dbc.Col(
            criar_card_kpi_shows(
                "Custo Médio do Colaborador",
                met_princ["salario_medio"],
                pct(met_princ["salario_medio"],
                    (met_comp_rh or {}).get("salario_medio")),
                label_comp,
                "monetario"
            ),
            width=3
        ),
    ]

    # -----------------------
    # Coleta dos indicadores simples
    # -----------------------
    all_indicators_simple = {
        "GMV": float(gmv) if not np.isnan(gmv) else None,
        "NumShows": float(num_shows) if not np.isnan(num_shows) else None,
        "TicketMedio": float(ticket) if ticket and not np.isnan(ticket) else None,
        "Cidades": int(cidades) if not np.isnan(cidades) else None,
        "Faturamento": float(fat) if not np.isnan(fat) else None,
        "TakeRateGMV": float(take_rate_gmv) if take_rate_gmv and not np.isnan(take_rate_gmv) else None,
        "CustosTotais": float(custos_tot) if custos_tot and not np.isnan(custos_tot) else None,
        "LucroLiquido": float(lucro_liquido) if lucro_liquido and not np.isnan(lucro_liquido) else None,
        "NovosPalcos": float(novos_palcos) if not np.isnan(novos_palcos) else None,
        "FaturamentoNovosPalcos": float(fat_novos) if not np.isnan(fat_novos) else None,
        "LifetimeMedio": str(lifetime_medio_str),
        "ChurnNovosPalcos": float(churn_count_novos) if not np.isnan(churn_count_novos) else None,
        "FatKA": float(fat_ka) if not np.isnan(fat_ka) else None,
        "NovosPalcosKA": float(np_ka) if not np.isnan(np_ka) else None,
        "TakeRateKA": float(take_rate_ka) if take_rate_ka and not np.isnan(take_rate_ka) else None,
        "ChurnKA": float(churn_ka_count) if not np.isnan(churn_ka_count) else None,
        "PalcosAtivos": float(palcos_ativos) if not np.isnan(palcos_ativos) else None,
        "ArtistasAtivos": float(artistas_ativos) if not np.isnan(artistas_ativos) else None,
        "PalcosVazios": float(palcos_vazios) if not np.isnan(palcos_vazios) else None,
        "ErrosOperacionais": float(erros_op) if erros_op and not np.isnan(erros_op) else None
    }

    # -----------------------
    # Coleta dos indicadores históricos DO MAPA IMPORTADO
    # -----------------------
    # Obter o mapa atualizado de config_data
    current_hist_kpi_map = get_hist_kpi_map() 
    
    # Garantir que os nomes das chaves aqui correspondam exatamente aos usados no HIST_KPI_MAP
    # e que o callback de kpis_charts.py também use esses mesmos nomes.
    historical_indicators_from_map = {}
    for kpi_key_in_map, data_dict in current_hist_kpi_map.items():
        # A chave para o all_indicators_store pode ser diferente se necessário,
        # mas vamos usar a mesma por simplicidade por enquanto, prefixada.
        store_key = f"historical_{kpi_key_in_map.lower().replace(' ', '_').replace('.', '').replace('º', '')}" 
        historical_indicators_from_map[store_key] = data_dict

    serializable_historical_indicators = {k: floatify_hist_data(v) for k, v in historical_indicators_from_map.items()}

    if not isinstance(existing_indicators, dict):
        existing_indicators = {}
    merged_indicators = {**existing_indicators, **all_indicators_simple, **serializable_historical_indicators}

    # Retorna todos os dados conforme a ordem dos outputs
    return (
        card_gmv, card_numshows, card_ticket, card_cidades,
        card_fat, card_takegmv, card_custos, card_lucro,
        card_novospalcos, card_fatnovospalcos, card_lifetimemedio, card_churn_novospalcos,
        card_ka_fat, card_ka_np, card_ka_takerate, card_ka_churn,
        card_palcos_ativos, card_artistas_ativos, card_palcos_vazios, card_erros_op,
        cards_pessoas,
        label_princ,
        merged_indicators
    )

# =================================================================================
# CALLBACK DO BOTÃO "FILTRAR BASE" => BAIXAR EXCLUIDOS
# =================================================================================
@app.callback(
    Output("download-excluidos", "data"),
    Input("btn-limpeza", "n_clicks"),
    prevent_initial_call=True
)
def baixar_excluidos(n):
    """Botão que exporta as linhas excluídas do Eshows (df_excl) em Excel."""
    if not n:
        return None
    df_excl = carregar_eshows_excluidos()
    if df_excl.empty:
        return None
    return dcc.send_data_frame(
        df_excl.to_excel,
        "Excluidos.xlsx",
        sheet_name="Excluidos",
        index=False
    )

# =================================================================================
# CALLBACK - GRÁFICO RECEITA × CUSTO
# =================================================================================
@callback(
    dash.Output("grafico-receita-custo", "figure"),
    [
        dash.Input("url",                        "pathname"),
        dash.Input("dashboard-ano-dropdown",     "value"),
        dash.Input("dashboard-periodo-dropdown", "value"),
        dash.Input("dashboard-mes-dropdown",     "value"),
        dash.Input("dashboard-date-range-picker","start_date"),
        dash.Input("dashboard-date-range-picker","end_date"),
        dash.Input("check-ultimos-12-meses",     "value"),
    ],
    # <<< disparo já no 1º load
    prevent_initial_call=False
)
def atualizar_grafico_receita_custo(
    pathname,
    ano, periodo, mes,
    start_date_main, end_date_main,
    ultimos_12_meses,
):
    # --------------------------------------------------------
    # 0) rota /dashboard
    # --------------------------------------------------------
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    # --------------------------------------------------------
    # 1) intervalo principal (padrão ou custom-range)
    # --------------------------------------------------------
    custom_range = None
    if periodo == "custom-range" and start_date_main and end_date_main:
        custom_range = (
            pd.to_datetime(start_date_main).normalize(),
            pd.to_datetime(end_date_main).normalize(),
        )

    # --------------------------------------------------------
    # 2) “últimos 12 meses”
    #    – 1ª render (None)   ➜ aplica 12 m
    #    – []                ➜ usuário desmarcou
    #    – qualquer lista     ➜ usuário marcou
    # --------------------------------------------------------
    aplica_12m = (ultimos_12_meses is None) or bool(ultimos_12_meses)

    if aplica_12m:
        dt_fim = get_period_end(ano, periodo, mes, custom_range) or datetime(ano, 12, 31)
        dt_ini = (dt_fim - relativedelta(months=11)).replace(day=1)
        custom_range = (dt_ini, dt_fim)

    # --------------------------------------------------------
    # 3) receita  (df_eshows)
    # --------------------------------------------------------
    df_principal = filtrar_periodo_principal(df_eshows, ano, periodo, mes, custom_range)
    if df_principal.empty:
        return dash.no_update

    COLS_FAT = [
        "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
        "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"
    ]
    val_cols = [c for c in COLS_FAT if c in df_principal.columns]
    df_principal[val_cols] = df_principal[val_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    df_principal["Faturamento"] = df_principal[val_cols].sum(axis=1)

    if {"Ano","Mês"}.difference(df_principal.columns):
        dcol = pd.to_datetime(df_principal["Data"])
        df_principal["Ano"], df_principal["Mês"] = dcol.dt.year, dcol.dt.month

    df_principal["AnoMes"] = (
        df_principal["Ano"].astype(int).astype(str)
        + "-" +
        df_principal["Mês"].astype(int).astype(str).str.zfill(2)
    )
    df_fat = (
        df_principal
        .groupby("AnoMes", as_index=False)["Faturamento"].sum()
        .assign(AnoMesDate=lambda d: pd.to_datetime(d["AnoMes"] + "-01"))
    )

    # --------------------------------------------------------
    # 4) custos  (df_base2)
    # --------------------------------------------------------
    df_cus_raw = filtrar_periodo_principal(df_base2, ano, periodo, mes, custom_range)
    if df_cus_raw.empty:
        df_cus = pd.DataFrame(columns=["AnoMes","Custos","AnoMesDate"])
    else:
        df_cus_raw["Custos"] = pd.to_numeric(df_cus_raw.get("Custos",0), errors="coerce").fillna(0)

        if {"Ano","Mês"}.difference(df_cus_raw.columns):
            dcol = pd.to_datetime(df_cus_raw["Data"])
            df_cus_raw["Ano"], df_cus_raw["Mês"] = dcol.dt.year, dcol.dt.month

        df_cus_raw["AnoMes"] = (
            df_cus_raw["Ano"].astype(int).astype(str)
            + "-" +
            df_cus_raw["Mês"].astype(int).astype(str).str.zfill(2)
        )
        df_cus = (
            df_cus_raw
            .groupby("AnoMes", as_index=False)["Custos"].sum()
            .assign(AnoMesDate=lambda d: pd.to_datetime(d["AnoMes"] + "-01"))
        )

    # --------------------------------------------------------
    # 5) merge Receita × Custos  +  corte até o último mês válido
    # --------------------------------------------------------
    df_merge = pd.merge(df_fat, df_cus, on="AnoMes", how="outer", copy=False)

    # assegura coluna-data
    if "AnoMesDate" not in df_merge.columns:
        df_merge["AnoMesDate"] = (
            df_merge.filter(like="AnoMesDate").bfill(axis=1).iloc[:, 0]
            .fillna(pd.to_datetime(df_merge["AnoMes"] + "-01"))
        )
        df_merge.drop(columns=df_merge.filter(like="AnoMesDate_").columns,
                    inplace=True)

    # corta onde as duas séries ainda têm dados
    if not df_merge.empty:
        ultima_comum = min(
            df_merge.loc[df_merge["Faturamento"].notna(), "AnoMesDate"].max(),
            df_merge.loc[df_merge["Custos"].notna(),      "AnoMesDate"].max()
        )
        df_merge = df_merge[df_merge["AnoMesDate"] <= ultima_comum]

    df_merge.sort_values("AnoMesDate", inplace=True)
    if df_merge.empty:
        return dash.no_update

    receita_vals = df_merge["Faturamento"].to_numpy()
    custo_vals   = df_merge["Custos"].to_numpy()
    meses_eixo   = df_merge["AnoMesDate"].dt.strftime("%b/%y")

    # --------------------------------------------------------
    # 6) helper para formatação
    # --------------------------------------------------------
    def abrevia(v):
        if pd.isna(v):          return ""
        if abs(v) >= 1_000_000: return f"R${v/1_000_000:.2f}M"
        if abs(v) >= 1_000:     return f"R${v/1_000:.0f}k"
        return f"R${v:,.0f}"

    # textos nos marcadores  ── primeira/última posição ficam vazias
    texts_rec = [abrevia(v) for v in receita_vals]
    texts_cus = [abrevia(v) for v in custo_vals]
    idx_first, idx_last = 0, len(meses_eixo) - 1
    for i in (idx_first, idx_last):
        texts_rec[i] = ""       # remove texto interno
        texts_cus[i] = ""

    # posiciona texto dos pontos “internos”
    pos_rec, pos_cus = [], []
    for r, c in zip(receita_vals, custo_vals):
        if pd.notna(r) and pd.notna(c) and r >= c:
            pos_rec.append("top center");  pos_cus.append("bottom center")
        elif pd.notna(r) and pd.notna(c):
            pos_rec.append("bottom center"); pos_cus.append("top center")
        else:
            pos_rec.append("top center");   pos_cus.append("top center")

    # --------------------------------------------------------
    # 7) monta figura
    # --------------------------------------------------------
    fig = go.Figure()

    # ► RECEITA
    fig.add_trace(go.Scatter(
        x=meses_eixo, y=receita_vals,
        mode="lines+markers+text",
        text=texts_rec, textposition=pos_rec,
        textfont=dict(size=15, color="forestgreen"),
        line=dict(color="forestgreen", width=2),
        marker=dict(color="forestgreen", size=6),
        fill="tozeroy", fillcolor="rgba(46,139,87,0.15)",
        name="Receita",
        connectgaps=False,
        hovertemplate="%{text}<extra></extra>",
    ))

    # ► CUSTOS
    fig.add_trace(go.Scatter(
        x=meses_eixo, y=custo_vals,
        mode="lines+markers+text",
        text=texts_cus, textposition=pos_cus,
        textfont=dict(size=15, color="firebrick"),
        line=dict(color="firebrick", width=2),
        marker=dict(color="firebrick", size=6),
        fill="tonexty", fillcolor="rgba(178,34,34,0.15)",
        name="Custos",
        connectgaps=False,
        hovertemplate="%{text}<extra></extra>",
    ))

    # ------------------------------------------------------------------
    # anotações – mesmo style das labels da série
    # ------------------------------------------------------------------
    idx_first, idx_last = 0, len(meses_eixo) - 1
    text_style_rec = dict(size=15, color="forestgreen", family="Inter")
    text_style_cus = dict(size=15, color="firebrick",  family="Inter")

    for i in (idx_first, idx_last):
        # Receita (verde) – em cima
        fig.add_annotation(
            x=meses_eixo[i], y=receita_vals[i],
            text=abrevia(receita_vals[i]),
            showarrow=False, xanchor="center", yanchor="bottom",
            yshift=10, font=text_style_rec
        )
        # Custos (vermelho) – embaixo
        fig.add_annotation(
            x=meses_eixo[i], y=custo_vals[i],
            text=abrevia(custo_vals[i]),
            showarrow=False, xanchor="center", yanchor="top",
            yshift=-10, font=text_style_cus
        )

    # --------------------------------------------------------
    # 8) layout
    # --------------------------------------------------------
    min_v = np.nanmin(np.concatenate([receita_vals, custo_vals])) * 0.9
    max_v = np.nanmax(np.concatenate([receita_vals, custo_vals])) * 1.1

    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=60, r=60, t=40, b=40),
        xaxis=dict(showgrid=False, tickfont=dict(size=14)),
        yaxis=dict(showgrid=False, visible=False, range=[min_v, max_v]),
        hoverlabel=dict(bgcolor="white", font_size=13, font_family="Inter"),
        height=350,
    )

    return fig

# =================================================================================
# MAPA DO BRASIL + CALLBACKS (adaptado, com allow_duplicate=True para evitar conflito)
# =================================================================================

import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback_context

# Supondo que as funções e variáveis abaixo (df_eshows, formatar_valor_utils, get_nome_estado,
# estado_para_arquivo_bandeira, filtrar_periodo_principal, filtrar_novos_palcos_por_periodo,
# calcular_churn, df_casas_earliest) já estejam importadas ou definidas em outro local.

with open("assets/br.json","r",encoding="utf-8") as f:
    geojson_br = json.load(f)

def criar_choropleth_brasil(df_mapa, selected_state):
    """
    Dado um DataFrame df_mapa com colunas: ['UF', 'NumShows'],
    retorna a Figure do choropleth do Brasil, destacando o estado selecionado
    (caso selected_state não seja None).
    """

    # Lista de UFs existentes no geojson
    lista_uf_geo = [feat["id"] for feat in geojson_br["features"]]
    df_all = pd.DataFrame({"UF": lista_uf_geo})

    # Faz merge para garantir que temos uma linha para cada UF
    df_mapa_merged = pd.merge(df_all, df_mapa, on="UF", how="left")
    df_mapa_merged["NumShows"] = df_mapa_merged["NumShows"].fillna(0)

    # Cálculo de participação
    total_shows = df_mapa_merged["NumShows"].sum()
    df_mapa_merged["StateName"] = df_mapa_merged["UF"].apply(get_nome_estado)
    df_mapa_merged["ShowsFmt"] = df_mapa_merged["NumShows"].apply(
        lambda x: formatar_valor_utils(x, "numero") if x > 0 else "0"
    )
    df_mapa_merged["ShareVal"] = df_mapa_merged["NumShows"] / total_shows if total_shows else 0
    df_mapa_merged["SharePct"] = df_mapa_merged["ShareVal"] * 100
    df_mapa_merged["ShareFmt"] = df_mapa_merged["SharePct"].apply(
        lambda x: formatar_valor_utils(x, "percentual") if x > 0 else "0.00%"
    )
    df_mapa_merged["custom"] = list(
        zip(df_mapa_merged["StateName"], df_mapa_merged["ShowsFmt"], df_mapa_merged["ShareFmt"])
    )

    # Determina os valores p/ escalas
    zmax_val = df_mapa_merged["NumShows"].dropna().max()
    if zmax_val is None or zmax_val < 1:
        zmax_val = 1
    zmax_custom = zmax_val * 0.9

    tick_vals = np.linspace(0, zmax_val, 5)
    tick_text = [formatar_valor_utils(v, "numero") for v in tick_vals]

    fig = go.Figure()

    # Camada base branca (para deixar o fundo do mapa branco e destacar as bordas)
    base_choropleth = go.Choropleth(
        geojson=geojson_br,
        locations=df_all["UF"],
        z=[1] * len(df_all),
        featureidkey="id",
        colorscale=[[0, "#ffffff"], [1, "#ffffff"]],
        marker_line_color="#BDBDBD",
        marker_line_width=0.75,
        showscale=False,
        hoverinfo='skip'
    )
    fig.add_trace(base_choropleth)

    # Se NumShows == 0, convertemos para NaN (para não serem coloridas)
    df_mapa_merged.loc[df_mapa_merged["NumShows"] == 0, "NumShows"] = np.nan

    if selected_state is None:
        # Desenha todas as UFs com gradiente (0 => claro, maior => laranja escuro)
        choropleth_dados = go.Choropleth(
            geojson=geojson_br,
            locations=df_mapa_merged["UF"],
            z=df_mapa_merged["NumShows"],
            featureidkey="id",
            colorscale=[[0, "#ffe5dc"], [1, "#fc4f22"]],
            marker_line_color="#BDBDBD",
            marker_line_width=0.75,
            showscale=True,
            zmin=0,
            zmax=zmax_custom,
            colorbar=dict(
                tickmode='array',
                tickvals=tick_vals,
                ticktext=tick_text,
                title=dict(text="Shows", side="top", font=dict(size=12)),
                x=0.75,
                y=0.5,
                xanchor='left',
                yanchor='middle',
                len=0.6,
                thickness=15,
                outlinewidth=0
            ),
            customdata=df_mapa_merged["custom"],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "<span style='font-size:0.9rem'>Shows: %{customdata[1]}</span><br>"
                "<span style='font-size:0.9rem'>Participação: %{customdata[2]}</span><br>"
                "<span style='font-size:0.8rem; color:#aaa'>(Clique para selecionar)</span>"
                "<extra></extra>"
            )
        )
        fig.add_trace(choropleth_dados)

    else:
        # Destaca somente o estado selecionado
        df_mapa_merged["Selected"] = df_mapa_merged["UF"].apply(lambda x: 1 if x == selected_state else 0)
        choropleth_sel = go.Choropleth(
            geojson=geojson_br,
            locations=df_mapa_merged["UF"],
            z=df_mapa_merged["Selected"],
            featureidkey="id",
            colorscale=["#ffffff", "#FDB03D"],
            showscale=False,
            marker_line_color="#BDBDBD",
            marker_line_width=0.75,
            customdata=df_mapa_merged["custom"],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "<span style='font-size:0.9rem'>Shows: %{customdata[1]}</span><br>"
                "<span style='font-size:0.9rem'>Participação: %{customdata[2]}</span><br>"
                "<span style='font-size:0.8rem; color:#aaa'>(Clique para remover)</span>"
                "<extra></extra>"
            )
        )
        fig.add_trace(choropleth_sel)

    # Configurações de layout do mapa
    fig.update_geos(
        visible=False,
        showframe=False,
        showcoastlines=False,
        showland=False,
        showlakes=False,
        showocean=False,
        showcountries=False,
        projection_type="mercator",
        fitbounds="locations",
        center=dict(lat=-15, lon=-60),
        lataxis=dict(range=[-35, 6]),
        lonaxis=dict(range=[-74, -34])
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        geo=dict(bgcolor='rgba(0,0,0,0)'),
        clickmode='event+select'
    )
    return fig

def gerar_mapa_uf(ano, periodo, mes, start_date, end_date):
    """
    Auxiliar que filtra df_eshows pelo período
    e retorna o DataFrame agregado por UF (nº de shows).
    """
    dfp = filtrar_periodo_principal(df_eshows, ano, periodo, mes, (start_date, end_date))
    if dfp.empty:
        return pd.DataFrame(columns=["UF","NumShows"])
    dfp["Id do Show"] = dfp["Id do Show"].astype(str)
    agg_ = dfp.groupby("Estado")["Id do Show"].nunique().reset_index()
    agg_.rename(columns={"Estado":"UF","Id do Show":"NumShows"}, inplace=True)
    return agg_

# ================================================
# CB: UNINDO A LÓGICA DO ESTADO SELECIONADO
# ================================================
@app.callback(
    Output("estado-selecionado", "data", allow_duplicate=True),
    [
        Input("url", "pathname"),              # <--- Adicionado
        Input("grafico-mapa-brasil", "clickData")
    ],
    State("estado-selecionado", "data"),
    prevent_initial_call=True
)
def selecionar_ou_desmarcar_estado(pathname, clickData, current_state):
    """
    Se clicar em um estado, seleciona-o;
    se clicar de novo, desmarca (None).
    """
    # 1) Verifica se estamos em /dashboard
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    # 2) Lógica original
    if clickData is None:
        return None
    loc = clickData["points"][0].get("location", None)
    if loc == current_state:
        return None
    return loc if loc else None


# ================================================
# GERA O MAPA DO BRASIL
# ================================================
@app.callback(
    Output("grafico-mapa-brasil", "figure"),
    [
        Input("url", "pathname"),                   # <--- Adicionado
        Input("dashboard-ano-dropdown", "value"),
        Input("dashboard-periodo-dropdown", "value"),
        Input("dashboard-mes-dropdown", "value"),
        Input("dashboard-date-range-picker", "start_date"),
        Input("dashboard-date-range-picker", "end_date"),
        Input("estado-selecionado", "data")
    ],
    prevent_initial_call=True
)
def gerar_mapa(pathname, ano, periodo, mes, start_date, end_date, selected_state):
    """
    Renderiza o choropleth do Brasil pintando as UF de acordo
    com número de shows no período filtrado.
    """
    # 1) Verifica se estamos em /dashboard
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    # 2) Lógica original
    if periodo != 'custom-range':
        start_date = None
        end_date = None

    df_mapa = gerar_mapa_uf(ano, periodo, mes, start_date, end_date)
    fig = criar_choropleth_brasil(df_mapa, selected_state)
    return fig

# ================================================
# INDICADORES DA PARTE ESQUERDA DO MAPA
# ================================================
@app.callback(
    Output("bandeira-selecionada", "src"),
    Output("titulo-selecionado","children"),
    Output("indicador-cidades","children"),
    Output("indicador-gmv","children"),
    Output("indicador-palcosativos","children"),
    Output("indicador-shows","children"),
    Output("indicador-faturamento","children"),
    Output("indicador-novospalcos","children"),
    Output("indicador-artistasativos","children"),
    Output("indicador-ticketmedio","children"),
    Output("indicador-churn","children"),
    [
        Input("url", "pathname"),  # <-- adicionado
        Input("estado-selecionado","data"),
        Input("dashboard-ano-dropdown","value"),
        Input("dashboard-periodo-dropdown","value"),
        Input("dashboard-mes-dropdown","value"),
        Input("dashboard-date-range-picker","start_date"),
        Input("dashboard-date-range-picker","end_date")
    ],
    prevent_initial_call=True
)
def atualizar_indicadores_mapa(pathname,
                               uf_selecionada,
                               ano, periodo, mes,
                               start_date, end_date):
    """
    Atualiza os 9 indicadores (Cidades, GMV, Palcos Ativos, etc.)
    sempre que um estado é selecionado no mapa.
    Se uf_selecionada for None => 'BR' (Brasil).
    E se periodo != 'custom-range', zeramos as datas.
    """
    # 1) Verifica se a rota NÃO é "/dashboard"
    if pathname != "/dashboard":
        raise dash.exceptions.PreventUpdate

    # 2) Lógica original do callback
    if periodo != 'custom-range':
        start_date = None
        end_date = None

    if not uf_selecionada:
        uf_selecionada = "BR"

    dfp = filtrar_periodo_principal(df_eshows, ano, periodo, mes, (start_date, end_date))
    if uf_selecionada != "BR":
        dfp = dfp[dfp["Estado"] == uf_selecionada]

    nome_estado = "Brasil" if uf_selecionada == "BR" else get_nome_estado(uf_selecionada)
    bandeira_src = "/assets/" + estado_para_arquivo_bandeira(nome_estado)

    if dfp.empty:
        return (
            bandeira_src,
            nome_estado,
            "0",
            "R$0",
            "0",
            "0",
            "R$0",
            "0",
            "0",
            "R$0",
            "0"
        )

    num_cidades = dfp["Cidade"].nunique() if "Cidade" in dfp.columns else 0
    dfp["Valor Total do Show"] = pd.to_numeric(dfp["Valor Total do Show"], errors='coerce').fillna(0)
    gmv_val = dfp["Valor Total do Show"].sum()
    palcos_ativos = dfp["Id da Casa"].nunique() if "Id da Casa" in dfp.columns else 0
    num_shows = dfp["Id do Show"].nunique() if "Id do Show" in dfp.columns else 0

    # Faturamento
    colunas_fat = [
        "Comissão B2B","Comissão B2C","Antecipação de Cachês",
        "Curadoria","SaaS Percentual","SaaS Mensalidade","Notas Fiscais"
    ]
    faturamento_val = 0.0
    valid_cols_fat = [c for c in colunas_fat if c in dfp.columns]
    if valid_cols_fat:
        df_fattemp = dfp[valid_cols_fat].apply(pd.to_numeric, errors='coerce').fillna(0)
        faturamento_val = df_fattemp.sum().sum()

    # Novos Palcos
    df_novos = filtrar_novos_palcos_por_periodo(df_casas_earliest, ano, periodo, mes, (start_date, end_date))
    if uf_selecionada != "BR" and not df_novos.empty:
        ids_uf = dfp["Id da Casa"].unique()
        df_novos = df_novos[df_novos["Id da Casa"].isin(ids_uf)]
    novos_palcos_count = df_novos["Id da Casa"].nunique() if not df_novos.empty else 0

    artistas_ativos = dfp["Nome do Artista"].nunique() if "Nome do Artista" in dfp.columns else 0
    ticket_medio = (gmv_val / num_shows) if num_shows > 0 else 0

    # Churn
    try:
        churn_count = calcular_churn(
            ano, periodo, mes,
            start_date, end_date,
            uf_selecionada,
            dias_sem_show=45
        )
    except:
        churn_count = 0

    return (
        bandeira_src,
        nome_estado,
        formatar_valor_utils(num_cidades, "numero"),
        formatar_valor_utils(gmv_val, "monetario"),
        formatar_valor_utils(palcos_ativos, "numero"),
        formatar_valor_utils(num_shows, "numero"),
        formatar_valor_utils(faturamento_val, "monetario"),
        formatar_valor_utils(novos_palcos_count, "numero"),
        formatar_valor_utils(artistas_ativos, "numero"),
        formatar_valor_utils(ticket_medio, "monetario"),
        formatar_valor_utils(churn_count, "numero")
    )


# =================================================================================
# CALLBACK DO GRÁFICO WATERFALL
# =================================================================================
@app.callback(
    Output('grafico-waterfall', 'figure'),
    [
        Input("url", "pathname"),   # <-- adicionado
        Input('dashboard-ano-dropdown', 'value'),
        Input('dashboard-periodo-dropdown', 'value'),
        Input('dashboard-mes-dropdown', 'value'),
        Input('dashboard-date-range-picker','start_date'),
        Input('dashboard-date-range-picker','end_date')
    ],
    prevent_initial_call=False
)
def atualizar_waterfall_chart(pathname,
                              ano, periodo, mes,
                              start_date_main, end_date_main):
    """
    Atualiza o gráfico Waterfall (Lucros e Perdas) de acordo com
    o período selecionado. Se não for range custom, limpa datas.
    """
    logger.info("--- [atualizar_waterfall_chart] Iniciando para ano=%s, periodo=%s, mes=%s ---", ano, periodo, mes) # DEBUG

    # 1) Verifica se a rota NÃO é "/dashboard"
    if pathname != "/dashboard":
        logger.debug("[atualizar_waterfall_chart] Rota não é /dashboard. Abortando.") # DEBUG
        raise dash.exceptions.PreventUpdate

    # 2) Lógica original
    if periodo != 'custom-range':
        logger.debug("[atualizar_waterfall_chart] Período não é custom-range. Zerando datas.") # DEBUG
        start_date_main = None
        end_date_main = None
    else:
        logger.debug("[atualizar_waterfall_chart] Período custom. Datas: %s a %s", start_date_main, end_date_main) # DEBUG

    # 1) Monta as categories e values
    logger.debug("[atualizar_waterfall_chart] Chamando get_waterfall_data...") # DEBUG
    categories_wf, values_wf = get_waterfall_data(ano, periodo, mes)
    logger.debug("[atualizar_waterfall_chart] get_waterfall_data retornou: categories=%s, values=%s", categories_wf, values_wf) # DEBUG

    # 2) Monta as categories_donut e values_donut (Top4 + 'Outras')
    logger.debug("[atualizar_waterfall_chart] Chamando get_donut_data...") # DEBUG
    cats_donut, vals_donut = get_donut_data(ano, periodo, mes)
    logger.debug("[atualizar_waterfall_chart] get_donut_data retornou: categories=%s, values=%s", cats_donut, vals_donut) # DEBUG

    # 3) Cria a figura
    logger.debug("[atualizar_waterfall_chart] Criando figura waterfall...") # DEBUG
    fig_wf = create_waterfall_chart(
        categories_wf,
        values_wf,
        periodo=periodo,
        ano=ano,
        categories_donut=cats_donut,
        values_donut=vals_donut
    )
    return fig_wf

# =================================================================================
# FUNÇÕES EXTRAS P/ WATERFALL
# =================================================================================
def get_waterfall_data(ano, periodo, mes):
    """Calcula categorias e valores para o gráfico Waterfall."""

    # ── faturamento ────────────────────────────────────────────
    df_princ = filtrar_periodo_principal(df_eshows, ano, periodo, mes, None)
    faturamento = 0
    if not df_princ.empty:
        cols_fat = [
            "Comissão B2B","Comissão B2C","Antecipação de Cachês",
            "Curadoria","SaaS Percentual","SaaS Mensalidade","Notas Fiscais"
        ]
        valid = [c for c in cols_fat if c in df_princ.columns]
        faturamento = (
            df_princ[valid].apply(pd.to_numeric, errors="coerce")
            .fillna(0).sum().sum()
        )

    # ── custos ────────────────────────────────────────────────
    df_b2 = filtrar_periodo_principal(df_base2, ano, periodo, mes, None)
    custos = {}
    if not (df_b2 is None or df_b2.empty):
        cols_custo = [
            "Imposto","Ocupação","Equipe","Terceiros","Op. Shows",
            "D.Cliente","Softwares","Mkt","D.Finan"
        ]
        for col in cols_custo:
            if col not in df_b2.columns:
                df_b2[col] = 0
            total = pd.to_numeric(df_b2[col], errors="coerce").fillna(0).sum()
            if total != 0:                    # ← descarta custo zero
                custos[col] = total

    categories = ["Faturamento", *custos.keys(), "Lucro Líquido"]
    values     = [faturamento, *(-v for v in custos.values())]
    values.append(faturamento - sum(custos.values()))
    return categories, values

def get_donut_data(ano, periodo, mes):
    """
    Retorna (categories_donut, values_donut) – Top-4 departamentos + “Outras”.
    Se o total de despesas for 0, devolve listas vazias.
    """
    df_b2 = filtrar_periodo_principal(df_base2, ano, periodo, mes, None)
    if df_b2 is None or df_b2.empty:
        return [], []

    cols_dep = [
        "Comercial","Tech","Geral","Finanças","Control",
        "Juridico","C.Sucess","Operações","RH"
    ]

    soma_dep = {}
    for col in cols_dep:
        if col in df_b2.columns:
            total = (
                pd.to_numeric(df_b2[col], errors="coerce")
                .fillna(0).sum()
            )
        else:
            total = 0
        soma_dep[col] = total

    total_geral = sum(soma_dep.values())
    if total_geral == 0:
        return [], []                      # ← não há dados para donut

    # top-4 + “Outras”
    ordenado = sorted(soma_dep.items(), key=lambda x: x[1], reverse=True)
    top4, resto = ordenado[:4], ordenado[4:]
    cats = [k for k, _ in top4] + ["Outras"]
    vals = [v for _, v in top4] + [sum(v for _, v in resto)]
    return cats, vals

# Registrar callbacks do KPI
register_callbacks(app)
register_okrs_callbacks(app)  # CORRIGIDO - adicionado (app)

# =================================================================================
# CALLBACK DO MODAL DE KPI COM DASHBOARD
# =================================================================================

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

@callback(
    Output("kpi-dash-modal", "is_open"),
    Output("kpi-dash-modal-title", "children"),
    Output("kpi-dash-card-title", "children"),   # NOVO
    Output("kpi-dash-modal-graph", "figure"),
    [Input({"type": "kpi-dash-icon", "index": ALL}, "n_clicks"),
     Input("close-kpi-dash-modal", "n_clicks")],
    State("kpi-dash-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_kpi_modal(n_clicks_list, close_clicks, is_open):
    """
    Abre o modal com o gráfico do KPI clicado ou fecha quando o X é clicado.

    • Mantém a lógica original (todos os outros KPIs já funcionam).
    • Corrige a captura do ID para casos com ponto no nome
      - ex.: "Fat. Novos Palcos".
    """
    if not callback_context.triggered:
        raise PreventUpdate

    # -------- identifica qual componente disparou -----------------------
    # rsplit(".", 1) ⇒ corta **apenas** depois do último ponto
    triggered = callback_context.triggered[0]["prop_id"].rsplit(".", 1)[0]

    # botão fechar
    if triggered == "close-kpi-dash-modal":
        return False, dash.no_update, dash.no_update, dash.no_update

    # evita abrir se nenhum ícone foi realmente clicado ou já está aberto
    if not any(n_clicks_list) or is_open:
        return False, dash.no_update, dash.no_update, dash.no_update

    # -------- nome do KPI (index) ---------------------------------------
    kpi_index = json.loads(triggered)["index"]

    # -------- classe utilitária p/ generate_kpi_figure ------------------
    class DashboardKPI:
        def __init__(self):
            self.df = df_eshows
            self.df_clientes = df_base2
            self.kpi_to_column = {
                "GMV": "Valor Total do Show",
                "Faturamento Eshows": "Faturamento",
                "Número de Shows": "Id do Show",
                "Ticket Médio": "Valor Total do Show",
                "Número de Cidades": "Cidade",
                "Take Rate GMV": "Comissão B2B",
                "Custos Totais": "Custos",
                "Lucro Líquido": "Lucro Líquido",
                "Palcos Ativos": "Id da Casa",
                "Novos Palcos": "Id da Casa",
                "Fat. Novos Palcos": "Faturamento",   # ← importante
                "Life Time Médio": "Id da Casa",
                "Churn de Novos Palcos": "Id da Casa",
                "Faturamento KA": "Faturamento",
                "Novos Palcos KA": "Id da Casa",
                "Take Rate KA": "Comissão B2B",
                "Churn KA": "Id da Casa",
                "Artistas Ativos": "Id do Show",
                "Palcos Vazios": "Id da Ocorrência",
                "Erros Operacionais": "Custos",
                "Nº de Colaboradores": "Id do Funcionário",
                "Tempo Médio de Casa": "Id do Funcionário",
                "Receita por Colaborador": "Id do Funcionário",
                "Custo Médio do Colaborador": "Salário"
            }

        def formatar_valor(self, valor, tipo="numero"):
            return formatar_valor_custom(valor, tipo)

    dashboard_instance = DashboardKPI()

    # -------- formatação para a legenda / tooltip -----------------------
    if kpi_index.startswith("Life Time"):
        format_type = "numero"                  # ex.: 3.5 m

    elif any(k in kpi_index for k in [
            "GMV", "Faturamento", "Custos",
            "Líquido", "Fat.", "$"
    ]):
        format_type = "monetario"

    elif kpi_index in ["Churn de Novos Palcos", "Churn KA"]:
        # estes churns são contagem absoluta, não porcentagem
        format_type = "numero"

    elif "Rate" in kpi_index or "Churn" in kpi_index:
        # demais ch-*taxas* ou churn em %
        format_type = "percentual"

    else:
        format_type = "numero"

    # -------- gera o gráfico -------------------------------------------
    today = datetime.now()
    try:
        fig = generate_kpi_figure(
            kpi_name=kpi_index,
            ano=today.year,
            mes=today.month,
            dashboard=dashboard_instance,
            chart_type="auto",
            format_type=format_type,
            animated=True
        )
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(
            text=f"Erro ao gerar gráfico: {e}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color="red", size=14)
        )

    # -------- títulos ---------------------------------------------------
    card_title = f"{kpi_index} – Evolução nos últimos 12 meses"
    return True, kpi_index, card_title, fig

# =========================================================
# CALLBACKS DE AUTENTICAÇÃO
# =========================================================
# Inicializa os callbacks de autenticação
init_auth_callbacks(app)
init_logout_callback(app)
init_client_side_callbacks(app)

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    # Fix para problema de memória: desabilitar reloader que duplica o processo
    app.run_server(debug=True, use_reloader=False, dev_tools_hot_reload=False)
    
    # # Em vez disso, imprimir uma mensagem de instrução:
    # logger.info("Use 'python index.py' para iniciar o aplicativo com a tela de login")






