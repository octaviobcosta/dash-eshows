# ──────────────────────────────────────────────────────────────
# kpis/kpis.py   –  Imports corrigidos
# ──────────────────────────────────────────────────────────────
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, ALL, callback_context
from datetime import datetime, timedelta
import math
import pandas as pd
import json
import os
import numbers
import textwrap
import re
import logging

# ── IMPORTS DO PROJETO (todos voltam um nível: "..") ──────────
from ..controles        import kpi_area_mapping, sanitize_id
from ..kpi_interpreter  import KPIInterpreter
from ..modulobase       import (
    carregar_base_eshows,
    carregar_base2,
    carregar_pessoas,
    carregar_ocorrencias,
    carregar_base_inad,
    carregar_eshows_excluidos,
)
from ..utils            import (
    formatar_valor_utils,
    mes_nome_intervalo,
    carregar_kpi_descriptions,
    kpi_bases_mapping,          # dicionário de mapeamento de bases
    calcular_variacao_percentual, 
    get_period_start,
    get_period_end,
    filtrar_periodo_principal  
)
from ..variacoes        import (
    get_cmgr_variables,
    get_lucratividade_variables,
    get_nrr_variables,
    get_ebitda_variables,
    get_receita_pessoal_variables,
    get_rpc_variables,
    get_inadimplencia_variables,
    get_estabilidade_variables,
    get_nivel_servico_variables,
    get_churn_variables,
    get_turnover_variables,
    get_palcos_vazios_variables,
    get_perdas_operacionais_variables,
    get_crescimento_sustentavel_variables,
    get_perfis_completos_variables,
    get_take_rate_variables,
    get_autonomia_usuario_variables,
    get_nps_artistas_variables,
    get_nps_equipe_variables,
    get_conformidade_juridica_variables,
    get_eficiencia_atendimento_variables,
    get_inadimplencia_real_variables,
    get_sucesso_implantacao_variables,
    get_roll_6m_growth,
    get_ltv_cac_variables,
    get_score_medio_show_variables,
    get_churn_valor_variables,
    get_csat_artistas_variables,
    get_csat_operacao_variables,
)

# ── Descrições dos KPIs ───────────────────────────────────────
# utils.carregar_kpi_descriptions já resolve o caminho app/data/
kpi_descriptions = carregar_kpi_descriptions()
interpreter      = KPIInterpreter(kpi_descriptions)
# ──────────────────────────────────────────────────────────────

##################################
# Cores para o gráfico Termômetro
##################################
colors = {
    'critico':   {'color': '#D32F2F'},
    'ruim':      {'color': '#F57C7C'},
    'controle':  {'color': '#FFDC00'},
    'bom':       {'color': '#29B388'},
    'excelente': {'color': '#008000'},
    'indefinido': {'color': '#808080'}
}

##################################
# Funções de Apoio
##################################
def parse_valor_formatado(valor_str):
    """
    Converte strings de valor em float. Exemplo:
      - "R$8.8k" -> 8800
      - "R$3.95M" -> 3950000
      - "12.3%" -> 12.3
      - "N/A" -> 0.0
    """
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    v = valor_str.strip()

    # Remove prefixos/sufixos
    v = (v.replace('R$', '')
         .replace('%', '')
         .replace(',', '.')
         .replace(' ', '')
         .lower())  # => "8.8k" ou "3.95m"

    multiplicador = 1.0

    # Se contiver "k" => milhar
    if 'k' in v:
        v = v.replace('k', '')
        multiplicador = 1000.0

    # Se contiver "m" => milhão
    if 'm' in v:
        v = v.replace('m', '')
        multiplicador = 1_000_000.0

    try:
        return float(v) * multiplicador
    except:
        return 0.0


# Extrair conteúdo do PDF
def extract_pdf_content(pdf_name, folder="assets"):
    import os
    try:
        import PyPDF2
    except ImportError:
        raise RuntimeError("PyPDF2 não está instalado. Execute 'pip install PyPDF2'.")
    pdf_path = os.path.join(folder, pdf_name)
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Erro ao ler o PDF {pdf_name}: {e}")
        return ""

def parse_strategy_and_pillars(pdf_text):
    estrategia = ""
    pilares = ""
    
    lines = pdf_text.split('\n')
    current_section = None
    for line in lines:
        line = line.strip()
        if "Estratégia" in line:
            current_section = 'estrategia'
            continue
        elif "Pilares" in line:
            current_section = 'pilares'
            continue
        
        if current_section == 'estrategia':
            estrategia += line + " "
        elif current_section == 'pilares':
            pilares += line + " "
    
    return {
        'estrategia': estrategia.strip(),
        'pilares': pilares.strip()
    }

# Função para parsear valores de controle
def parse_control_values(control_values):
    """Converte strings 'Infinity' e '-Infinity' para os valores apropriados no Python."""
    for key, value in control_values.items():
        control_values[key] = [
            float('inf') if v == "Infinity" else float('-inf') if v == "-Infinity" else v
            for v in value
        ]
    return control_values

# Carregando PDF e extraindo sua estratégia/pilares
pdf_name = "OKRs25.pdf"
pdf_folder = "assets"
pdf_text = extract_pdf_content(pdf_name, pdf_folder)
strategy_info = parse_strategy_and_pillars(pdf_text)


def get_kpi_status(kpi_name, kpi_value, kpi_descriptions):
    if kpi_name not in kpi_descriptions:
        return None, None

    zona = kpi_descriptions[kpi_name]
    comportamento = zona.get('behavior', 'Positivo')
    control_values = zona.get('control_values', {})

    def parse_limit(value):
        if value == "Infinity":
            return float('inf')
        elif value == "-Infinity":
            return float('-inf')
        else:
            return float(value)

    try:
        kpi_value = float(kpi_value)
    except ValueError:
        kpi_value = 0.0

    intervals = {}
    for key, val in control_values.items():
        start = parse_limit(val[0])
        end = parse_limit(val[1])
        intervals[key] = (start, end)

    def valor_entre(valor, intervalo):
        return intervalo[0] <= valor < intervalo[1]

    if comportamento == 'Positivo':
        if valor_entre(kpi_value, intervals['critico']):
            status = 'critico'
        elif valor_entre(kpi_value, intervals['ruim']):
            status = 'ruim'
        elif valor_entre(kpi_value, intervals['controle']):
            status = 'controle'
        elif valor_entre(kpi_value, intervals['bom']):
            status = 'bom'
        elif valor_entre(kpi_value, intervals['excelente']):
            status = 'excelente'
        else:
            status = 'indefinido'
    else:
        # Para comportamento Negativo
        if valor_entre(kpi_value, intervals['excelente']):
            status = 'excelente'
        elif valor_entre(kpi_value, intervals['bom']):
            status = 'bom'
        elif valor_entre(kpi_value, intervals['controle']):
            status = 'controle'
        elif valor_entre(kpi_value, intervals['ruim']):
            status = 'ruim'
        elif valor_entre(kpi_value, intervals['critico']):
            status = 'critico'
        else:
            status = 'indefinido'

    status_to_icon = {
       'critico': 'critico.png',
       'ruim': 'ruim.png',
       'controle': 'controle.png',
       'bom': 'bom.png',
       'excelente': 'excelente.png',
       'indefinido': 'indefinido.png'
    }

    icon_filename = status_to_icon.get(status, 'indefinido.png')
    return status, icon_filename


##################################
# Termômetro e Modal
##################################
import plotly.graph_objects as go
def create_enhanced_thermometer(kpi_name, resultado_num):
    kpi_info = kpi_descriptions.get(kpi_name, {})
    control_values = kpi_info.get('control_values', {})
    kpi_format = kpi_info.get('format', 'number')  # 'percent', 'monetary' ou 'number'

    def parse_limit(value):
        if isinstance(value, (int, float)):
            return float(value)
        elif value == "Infinity":
            return float('inf')
        elif value == "-Infinity":
            return float('-inf')
        else:
            return float(value)

    intervals = {}
    for zona, val in control_values.items():
        start = parse_limit(val[0])
        end = parse_limit(val[1])
        intervals[zona] = (start, end)

    finite_limits = []
    for (start, end) in intervals.values():
        if start not in [float('-inf'), float('inf')]:
            finite_limits.append(start)
        if end not in [float('-inf'), float('inf')]:
            finite_limits.append(end)

    if not finite_limits:
        finite_limits = [0, 10]

    original_global_min = min(finite_limits)
    original_global_max = max(finite_limits)

    global_min = original_global_min
    global_max = original_global_max

    base_step = 5.0
    critico_interval = intervals.get('critico', None)
    if critico_interval:
        cstart, cend = critico_interval
        if cstart == float('-inf'):
            global_min = min(global_min, cend)

    excelente_interval = intervals.get('excelente', None)
    if excelente_interval:
        estart, eend = excelente_interval
        if eend == float('inf'):
            global_max = max(global_max, estart)

    data_range = global_max - global_min
    if data_range == 0:
        data_range = 1.0

    base_step = data_range * 0.05

    if critico_interval and critico_interval[0] == float('-inf'):
        cstart, cend = critico_interval
        global_min = min(global_min, cend - base_step)

    if excelente_interval and excelente_interval[1] == float('inf'):
        estart, eend = excelente_interval
        global_max = max(global_max, estart + base_step)

    def step_down(value, step):
        div = value / step
        return (int(div)-1)*step if not div.is_integer() else value

    def step_up(value, step):
        div = value / step
        return (int(div)+1)*step if not div.is_integer() else value

    if resultado_num < global_min:
        global_min = step_down(resultado_num, base_step)
    if resultado_num > global_max:
        global_max = step_up(resultado_num, base_step)

    range_span = global_max - global_min
    if range_span == 0:
        range_span = 1.0
    final_step = range_span / 10.0

    updated_intervals = {}
    for zona, (start, end) in intervals.items():
        new_start = start
        new_end = end
        if start == float('-inf'):
            new_start = global_min - final_step
        if end == float('inf'):
            new_end = global_max + final_step
        updated_intervals[zona] = (new_start, new_end)

    if kpi_format == 'percent':
        kpi_str = formatar_valor_utils(resultado_num, 'percentual')
    elif kpi_format == 'monetary':
        kpi_str = formatar_valor_utils(resultado_num, 'monetario')
    else:
        kpi_str = formatar_valor_utils(resultado_num, 'numero')

    status, _ = get_kpi_status(kpi_name, resultado_num, kpi_descriptions)
    if status is None:
        status = 'indefinido'
    status_color = colors[status]['color']
    text_color = '#FFFFFF' if status in ['bom', 'excelente', 'critico'] else '#000000'
    image_name = f"modal_{status}.png"

    fig = go.Figure()

    interval_list = sorted(updated_intervals.items(), key=lambda x: x[1][0])
    for zona, (start, end) in interval_list:
        fig.add_trace(go.Bar(
            x=[end - start],
            y=[0],
            orientation='h',
            width=1.0,
            marker=dict(color=colors[zona]['color'], line=dict(width=2, color='#ffffff')),
            base=start,
            showlegend=False,
            hoverinfo='skip'
        ))

    fig.add_trace(go.Scatter(
        x=[resultado_num],
        y=[-0.1],
        mode='markers',
        marker=dict(symbol='triangle-up', size=25, color='black'),
        hoverinfo='skip',
        showlegend=False
    ))

    sizex = range_span * 0.07
    sizey = 3.0

    fig.add_layout_image(
        dict(
            source=f"assets/{image_name}",
            x=resultado_num,
            y=0.82,
            xref='x',
            yref='paper',
            xanchor='center',
            yanchor='middle',
            sizex=sizex,
            sizey=sizey,
            layer='above'
        )
    )

    fig.add_annotation(
        x=resultado_num,
        y=0.84,
        xref='x',
        yref='paper',
        text=kpi_str,
        showarrow=False,
        font=dict(color=text_color, size=18),
        align='center',
        xanchor='center',
        yanchor='middle',
        bgcolor='rgba(0,0,0,0)',
        borderwidth=0
    )

    range_buffer = 0.05 * range_span
    if (resultado_num - global_min) < range_buffer:
        global_min = resultado_num - range_buffer
    if (global_max - resultado_num) < range_buffer:
        global_max = resultado_num + range_buffer

    boundaries = set()
    for s, e in updated_intervals.values():
        boundaries.add(s)
        boundaries.add(e)
    boundaries = sorted(boundaries)

    tick_texts = []
    if kpi_format == 'percent':
        for val in boundaries:
            tick_texts.append(formatar_valor_utils(val, 'percentual'))
    elif kpi_format == 'monetary':
        for val in boundaries:
            tick_texts.append(formatar_valor_utils(val, 'monetario'))
    else:
        for val in boundaries:
            tick_texts.append(formatar_valor_utils(val, 'numero'))

    fig.update_yaxes(
        type='linear',
        range=[-0.3, 0.3],
        showticklabels=False,
        showgrid=False,
        zeroline=False,
        showline=False,
        fixedrange=True
    )

    fig.update_xaxes(
        range=[global_min, global_max],
        showgrid=False,
        zeroline=False,
        showline=True,
        linecolor='rgba(0,0,0,0.2)',
        mirror=False,
        ticks='outside',
        tickcolor='rgba(0,0,0,0.2)',
        ticklen=3,
        tickwidth=1,
        tickfont=dict(size=14),
        tickvals=boundaries,
        ticktext=tick_texts,
        fixedrange=True
    )

    fig.update_layout(
        height=130,
        margin=dict(l=40, r=40, t=20, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        barmode='stack',
        showlegend=False,
        font=dict(family='Arial', size=14, color='#333'),
        hovermode=False,
        bargap=0.05,
        dragmode=False
    )

    return fig

def create_status_card():
    return dbc.Card(
        dbc.CardBody(
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Img(src="/assets/status_icon.png", className="card-header-icon"),
                                    html.H5("Status e Zonas de Controle", className="card-title"),
                                    html.Div(
                                        html.I(className="bi bi-info-circle", id="status-info-icon"),
                                        style={"marginLeft": "8px", "cursor": "help"}
                                    ),
                                    dbc.Tooltip(
                                        "Este gráfico mostra o status atual do KPI em relação às zonas de controle estabelecidas",
                                        target="status-info-icon",
                                        placement="right"
                                    )
                                ],
                                className="d-flex align-items-center"
                            )
                        ],
                        className="card-header d-flex justify-content-between align-items-center mb-3"
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Img(
                                                id="status-icon",
                                                style={"width": "24px", "height": "24px", "marginRight": "10px"}
                                            ),
                                            html.Span(id="status-text", className="fs-5 fw-medium")
                                        ],
                                        id="status-box"
                                    )
                                ],
                                className="status-indicator"
                            )
                        ],
                        className="mb-3"
                    ),
                    html.Div(
                        [
                            dcc.Graph(
                                id='thermometer-graph',
                                config={
                                    'displayModeBar': False,
                                    'staticPlot': True
                                },
                                className="thermometer-graph",
                                style={"height": "90px"}
                            )
                        ],
                        className="thermometer-container position-relative"
                    )
                ],
                className="inner-card"
            )
        ),
        className="shadow-sm mb-4"
    )

def create_kpi_painel_modal():
    return dbc.Modal(
        [
            dbc.ModalHeader(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Img(
                                    id="kpi-painel-modal-icon",
                                    src="/assets/kpiicon.png",
                                    className="modal-title-icon",
                                    style={"margin-right": "10px"}
                                ),
                                html.H4(
                                    id='kpi-painel-modal-title',
                                    className="modal-title-text"
                                )
                            ],
                            className="d-flex align-items-center",
                            style={'flex': '1'}
                        ),
                        html.Button(
                            "✕",
                            id='close-kpi-painel-modal', # ID específico para este modal
                            className="kpi-dash-close-btn", # Reutiliza a classe CSS
                            style={
                                "position": "absolute",
                                "right": "2rem", # Ajustado para melhor alinhamento no header do modal
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
                            }
                        ),
                    ],
                    className="d-flex align-items-center justify-content-between",
                    style={'width': '100%', 'padding': '0 20px'}
                ),
                className="modal-header-custom",
                close_button=False, # Garantir que o botão padrão do header não apareça
                style={'padding': '20px', 'position': 'relative'} # Adicionado position: relative
            ),
            dbc.ModalBody(
                html.Div([
                    # Card DESCRIÇÃO
                    dbc.Card(
                        dbc.CardBody(
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Img(src="/assets/description_icon.png", className="card-header-icon"),
                                                    html.H5("Descrição do KPI", className="card-title")
                                                ],
                                                className="d-flex align-items-center"
                                            )
                                        ],
                                        className="card-header d-flex justify-content-between align-items-center"
                                    ),
                                    dcc.Markdown(
                                        id='kpi-description',
                                        className="modal-text-content",
                                        mathjax=True,
                                        style={'textAlign': 'left', 'fontSize': '16px'},
                                        dangerously_allow_html=True
                                    )
                                ],
                                className="inner-card"
                            )
                        ),
                        className="shadow-sm mb-4"
                    ),
                    # Card Status
                    create_status_card(),
                    # Card Interpretação
                    dbc.Card(
                        dbc.CardBody(
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Img(src="/assets/interpretation_icon.png", className="card-header-icon"),
                                                    html.H5("Interpretação para a Eshows", className="card-title")
                                                ],
                                                className="d-flex align-items-center"
                                            )
                                        ],
                                        className="card-header d-flex justify-content-start align-items-center"
                                    ),
                                    dcc.Loading(
                                        id="loading-interpretation",
                                        type="default",
                                        children=[
                                            dcc.Markdown(
                                                id='interpretation-content',
                                                className="modal-text-content",
                                                mathjax=True,
                                                style={'marginTop': '0px'}
                                            )
                                        ]
                                    )
                                ],
                                className="inner-card"
                            )
                        ),
                        className="shadow-sm mb-4"
                    ),
                ], style={"textAlign": "left"})
            )
        ],
        id='kpi-painel-modal',
        is_open=False,
        size="xl",
        backdrop=True,
        scrollable=True,
        fullscreen=True,
        contentClassName="modal-content-areia"
    )

# --------------------------------------------------------------------------- #
# Cria card de KPI no Painel                                                  #
# --------------------------------------------------------------------------- #
def criar_card_kpi_painel(
    titulo,
    valor,            # string ex.: "3.01%", "0.48%", "R$12.3k", "N/A"...
    variacao,         # float com a variação em %
    periodo_comp,
    is_negative=False,
    format_type='numero',
    icon_path_painel="/assets/infokpi.png"
):
    valor_float = parse_valor_formatado(valor)

    # Corrige cálculo de variação para valores negativos
    if variacao is not None and valor_float is not None:
        ref = valor_float - variacao if variacao != 0 else valor_float
        variacao_calc = ((valor_float - ref) / abs(ref)) * 100 if ref != 0 else 0
        is_positive = variacao_calc > 0
    else:
        is_positive = variacao is not None and variacao > 0

    cor = 'danger' if (is_positive == is_negative) else 'success'
    valor_formatado = formatar_valor_utils(valor_float, format_type)

    # ------------------------------------------- #
    # Ajuste exclusivo p/ Score Médio do Show
    # ------------------------------------------- #
    if titulo == "Score Médio do Show":
        valor_formatado = f"{valor_float:.2f}"   # força 2 casas → 4.85
    # ------------------------------------------- #

    # -------- NOVO: classe extra para KPIs com estrela -------------------- #
    valor_display = valor_formatado
    valor_classes = "card-kpi-value"
    if titulo in {"Score Médio do Show", "CSAT Artistas", "CSAT Operação"}:
        valor_classes += " rating-star"      # CSS cuidará da estrelinha
    # ---------------------------------------------------------------------- #

    variacao_text = (
        f"{'+' if is_positive else ''}{variacao:.1f}%" if variacao is not None else "N/A"
    )

    status, icon_filename = get_kpi_status(titulo, valor_float, kpi_descriptions)
    display_icon   = (status not in [None, 'controle']) and (icon_filename is not None)
    icon_path_status = f"/assets/{icon_filename}" if display_icon else None

    kpi_icon_id   = {'type': 'kpi-icon-painel', 'index': sanitize_id(titulo)}
    icon_id_status = f"status-icon-painel-{sanitize_id(titulo)}"

    card_content = [
        dbc.CardBody([
            html.Div([
                # -------- Título + ícone-info --------------------------------
                html.Div(
                    [
                        html.Span(titulo, className="card-kpi-title-text"),
                        html.Img(
                            src=icon_path_painel,
                            className="card-kpi-icon",
                            alt="Ícone do KPI Painel",
                            title="Detalhes do KPI Painel",
                            id=kpi_icon_id,
                            height="16px",
                            style={"margin-left": "auto", 'cursor': 'pointer'}
                        )
                    ],
                    className="card-kpi-title",
                    style={
                        'display': 'flex',
                        'align-items': 'center',
                        'justify-content': 'space-between',
                        'margin-bottom': '0.25rem'
                    }
                ),

                # -------- Valor principal ------------------------------------
                html.H3(
                    valor_display,
                    className=valor_classes,         # ← usa classes dinâmicas
                    style={'margin-bottom': '0.25rem'}
                ),

                # -------- Linha de variação + status -------------------------
                html.Div([
                    html.Div(
                        [
                            html.Img(
                                src=icon_path_status,
                                id=icon_id_status,
                                height="22px",
                                style={'cursor': 'pointer', 'margin-right': '5px'},
                                title=""
                            ),
                            dbc.Tooltip(
                                status.capitalize() if status else "",
                                target=icon_id_status,
                                placement='top',
                                className=(
                                    f"tooltip-status tooltip-{status.lower()}" if status else ""
                                )
                            )
                        ] if display_icon else None,
                        style={'display': 'flex', 'align-items': 'center'}
                    ),
                    html.Div(style={'flex': '1'}),
                    html.Div([
                        html.I(
                            className=(
                                "fa-solid fa-arrow-trend-up me-1" if is_positive
                                else "fa-solid fa-arrow-trend-down me-1"
                            ),
                            style={
                                'color': '#198754' if cor == 'success' else '#dc3545',
                                'font-size': '1rem'
                            }
                        ),
                        html.Span(
                            variacao_text,
                            style={
                                "color": '#198754' if cor == 'success' else '#dc3545',
                                "font-size": "1rem"
                            }
                        )
                    ], className="card-kpi-variation")
                ], style={
                    'display': 'flex',
                    'align-items': 'center',
                    'margin-bottom': '0.25rem'
                }),

                # -------- Texto do período comparativo -----------------------
                html.Div(f"vs {periodo_comp}", className="card-kpi-period")
            ], className="card-kpi-inner")
        ])
    ]
    return dbc.Card(card_content, className="card-kpi h-100")



############################################
# Layout Principal do Painel de KPIs
############################################
painel_kpis_layout = dbc.Container([
    # IMPORTANTE: crie um Store **específico** do painel, p/ não conflitar:
    dcc.Store(id='painel-indicators-store', data={}),

    dcc.Store(id='strategy-info', data={}),   # se quiser reaproveitar
    dcc.Store(id='ia-interpretations', data={}),
    dcc.Store(id='kpi-selected-data'),

    # TÍTULO E DATA
    dbc.Row([
        dbc.Col([
            html.H1(
                "Painel de KPIs",
                style={
                    'font-family': 'Inter',
                    'font-weight': '700',
                    'font-size': '56px',
                    'color': '#4A4A4A'
                },
                className="mb-0"
            ),
            html.Div(
                id='current-date-kpis',
                style={
                    'font-family': 'Inter',
                    'font-weight': '300',
                    'font-style': 'italic',
                    'font-size': '16px',
                    'color': '#4A4A4A'
                },
                className="current-date"
            )
        ], className="mb-4")
    ]),

    # ----------------------------
    #  DROPDOWNS  (Painel KPIs)
    # ----------------------------
    dbc.Row([
        # — Ano —
        dbc.Col([
            html.Label("Ano:", className="mb-1"),
            dcc.Dropdown(
                id="kpi-ano-dropdown",
                options=[{"label": str(a), "value": a} for a in [2025, 2024, 2023, 2022]],
                value=2025,
                clearable=False,
            ),
        ], xs=6, sm=3, md=2, lg=1, style={"padding": "0 5px"}),

        # — Período —
        dbc.Col([
            html.Label("Período:", className="mb-1"),
            dcc.Dropdown(
                id="kpi-periodo-dropdown",
                options=[
                    {"label": "Year To Date",        "value": "YTD"},
                    {"label": "1° Trimestre",        "value": "1° Trimestre"},
                    {"label": "2° Trimestre",        "value": "2° Trimestre"},
                    {"label": "3° Trimestre",        "value": "3° Trimestre"},
                    {"label": "4° Trimestre",        "value": "4° Trimestre"},
                    {"label": "Mês Aberto",          "value": "Mês Aberto"},
                    {"label": "Ano Completo",        "value": "Ano Completo"},
                    {"label": "Período Personalizado","value": "custom-range"},
                ],
                value="YTD",
                clearable=False,
            ),
        ], xs=10, sm=6, md=4, lg=2, style={"padding": "0 5px"}),

        # — Mês (só para "Mês Aberto") —
        dbc.Col([
            html.Div([
                html.Label("Mês:", className="mb-1"),
                dcc.Dropdown(
                    id="kpi-mes-dropdown",
                    options=[{"label": m, "value": i} for i, m in enumerate(
                        ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"], 1)],
                    value=datetime.now().month,
                    clearable=False,
                    disabled=True,
                ),
            ], id="kpi-mes-dropdown-container", style={"display": "none"}),
        ], xs=10, sm=6, md=4, lg=2, style={"padding": "0 5px"}),

        dbc.Col([], className="flex-grow-1"),  # espaçador flexível

        # — Comparar com  ← ***novo***
        dbc.Col([
            html.Label("Comparar com:", className="mb-1"),
            dcc.Dropdown(
                id="kpi-comparar-dropdown",
                options=[
                    {"label": "Ano Anterior",       "value": "ano_anterior"},
                    {"label": "Período Anterior",   "value": "periodo_anterior"},
                    {"label": "Selecionar Período", "value": "custom-compare"},
                ],
                value="ano_anterior",
                clearable=False,
            ),
        ], xs=10, sm=6, md=4, lg=2, style={"padding": "0 5px"}),

        # — Status —
        dbc.Col([
            html.Label("Status:", className="mb-1 text-end"),
            dcc.Dropdown(
                id="status-dropdown-kpis",
                options=[
                    {"label": "Crítico",    "value": "critico"},
                    {"label": "Ruim",       "value": "ruim"},
                    {"label": "Controle",   "value": "controle"},
                    {"label": "Bom",        "value": "bom"},
                    {"label": "Excelente",  "value": "excelente"},
                ],
                placeholder="Filtrar por Status",
                multi=False,
                style={"width": "100%"},
                className="dropdown-container",
            ),
        ], xs=10, sm=6, md=4, lg=2, style={"padding": "0 5px"}),

        # — Área —
        dbc.Col([
            html.Label("Área:", className="mb-1 text-end"),
            dcc.Dropdown(
                id="area-dropdown-kpis",
                options=[
                    {"label": "Institucional",        "value": "Institucional"},
                    {"label": "Comercial",            "value": "Comercial"},
                    {"label": "Financeiro",           "value": "Financeiro"},
                    {"label": "Operações",            "value": "Operações"},
                    {"label": "Produto",              "value": "Produto"},
                    {"label": "Jurídico & Pessoas",   "value": "Jurídico & Pessoas"},
                ],
                placeholder="Filtrar por Área",
                multi=False,
                style={"width": "100%"},
                className="dropdown-container",
            ),
        ], xs=10, sm=6, md=4, lg=2, style={"padding": "0 5px"}),
    ], className="mb-2 g-1 align-items-end"),
  
    # Nova linha para o período personalizado
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Label("Período Personalizado:", className="mb-1"),
                html.Div(
                    dcc.DatePickerRange(
                        id='kpi-date-range',
                        start_date=datetime(datetime.now().year, 1, 1),
                        end_date=datetime.now(),
                        display_format='DD/MM/YYYY',
                        first_day_of_week=1,
                        day_size=36,
                        min_date_allowed=datetime(2020, 1, 1),
                        show_outside_days=True,
                        persistence=True,
                        clearable=True,
                        calendar_orientation='horizontal'
                    ),
                    className="date-picker-wrapper"
                ),
                html.Div(id="kpi-custom-range-error", style={"color": "#D32F2F", "marginTop": "0.5rem"})
            ], id='kpi-date-range-container', style={'display':'none'})
        ], xs=12, sm=12, md=6, lg=6)
    ], className="mb-2 g-1"),

    html.Div([
        html.Span("Período Analisado: ",
                  style={"fontStyle": "italic", "fontSize": "16px", "color": "#4A4A4A"},
                  className='me-1'),
        html.Span(id='kpi-periodo-analisado',
                  style={"fontStyle": "italic", "fontSize": "16px", "color": "#4A4A4A"})
    ], className='mb-2 g-1'),

    dbc.Row(id='kpis-cards-container', className="g-3"),

    create_kpi_painel_modal()

], fluid=True)

########################
# REGISTER CALLBACKS
########################
def register_callbacks(app):
    @app.callback(
        Output('kpi-mes-dropdown-container', 'style'),
        Output('kpi-mes-dropdown', 'value'),
        Output('kpi-mes-dropdown', 'disabled'),  # Novo Output
        Input('kpi-periodo-dropdown', 'value')
    )
    def mostrar_esconder_dropdown_mes(periodo_sel):
        if periodo_sel == 'Mês Aberto':
            return {"display": "block"}, datetime.now().month, False  # disabled=False
        else:
            return {"display": "none"}, datetime.now().month, True   # disabled=True

    @app.callback(
        Output('kpi-date-range-container', 'style'),
        Input('kpi-periodo-dropdown', 'value')
    )
    def mostrar_esconder_datepicker(periodo_sel):
        if periodo_sel == 'custom-range':
            return {"display": "block"}
        else:
            return {"display": "none"}

    @app.callback(
        Output('kpi-custom-range-error', 'children'),
        [Input('kpi-date-range', 'start_date'),
         Input('kpi-date-range', 'end_date'),
         Input('kpi-periodo-dropdown', 'value')]
    )
    def validar_custom_range(start_date, end_date, periodo):
        if periodo == 'custom-range':
            if not start_date or not end_date:
                return "Selecione o início e o fim do período."
            if start_date > end_date:
                return "A data final deve ser igual ou posterior à inicial."
        return ""

    # ------------------------------------------------------------------------------
    # Período analisado (Painel de KPIs)
    # ------------------------------------------------------------------------------
    @app.callback(
        Output("kpi-periodo-analisado", "children"),
        Input("kpi-ano-dropdown", "value"),
        Input("kpi-periodo-dropdown", "value"),
        Input("kpi-mes-dropdown", "value"),
        Input("kpi-date-range", "start_date"),
        Input("kpi-date-range", "end_date"),
    )
    def atualizar_periodo_analisado(ano, periodo, mes, start_date_str, end_date_str):
        """
        Devolve o texto que aparece logo abaixo dos filtros do Painel.
        Agora replica o mesmo formato usado no Dashboard ("Jan/25 até Abr/25").
        """
        from datetime import datetime
        import pandas as pd
        from ..utils import (
            get_period_start,
            get_period_end,
            mes_nome,            # dicionário helper já existente em utils.py
        )

        # ------------------------------------------------------------------ #
        # 1) Mês Aberto – mantém lógica anterior                             #
        # ------------------------------------------------------------------ #
        if periodo == "Mês Aberto":
            if mes is None:
                # defensor – se por acaso vier None
                return f"Mês Aberto de {ano}"
            return f"{mes_nome(mes)} de {ano}"

        # ------------------------------------------------------------------ #
        # 2) Período Personalizado                                           #
        # ------------------------------------------------------------------ #
        if periodo == "custom-range":
            if start_date_str and end_date_str:
                try:
                    ini = pd.to_datetime(start_date_str)
                    fim = pd.to_datetime(end_date_str)
                    ini_txt = ini.strftime("%d/%m/%y")
                    fim_txt = fim.strftime("%d/%m/%y")
                    return f"{ini_txt} – {fim_txt}"
                except Exception:
                    # fallback em caso de datas inválidas
                    return "Período Personalizado"
            return "Período Personalizado"

        # ------------------------------------------------------------------ #
        # 3) Demais opções  ➜ usa utils.get_period_start / get_period_end    #
        # ------------------------------------------------------------------ #
        dt_ini = get_period_start(ano, periodo, mes, None)
        dt_fim = get_period_end(ano, periodo, mes, None)

        if dt_ini is None or dt_fim is None:
            # fallback se alguma função devolver None
            return f"{periodo} de {ano}"

        # Ex.: "Janeiro/25"  ou  "Janeiro/25 até Abril/25"
        ini_txt = f"{mes_nome(dt_ini.month)}/{str(dt_ini.year)[2:]}"
        fim_txt = f"{mes_nome(dt_fim.month)}/{str(dt_fim.year)[2:]}"

        # Se começo e fim caem no mesmo mês/ano, mostra só um
        if (dt_ini.year == dt_fim.year) and (dt_ini.month == dt_fim.month):
            return ini_txt
        return f"{ini_txt} até {fim_txt}"

    # ------------------------------------------------------------------------------
    # Listagem de KPIs
    # ------------------------------------------------------------------------------
    kpi_list = [
        "CMGR",
        "Roll 6M Growth",
        "Net Revenue Retention",
        "Take Rate",
        # "Sucesso da Implantação",
        "Receita por Colaborador",
        "Lucratividade",
        "EBITDA",
        "Crescimento Sustentável",  # Comentado conforme solicitado
        "Inadimplência",
        "Inadimplência Real",
        "Estabilidade",
        # "Nível de Serviço",  # Comentado conforme solicitado
        "Churn %",
        "Palcos Vazios",
        "Perdas Operacionais",
        "Eficiência de Atendimento",
        "NPS Artistas",
        "NPS Equipe",
        "Turn Over",
        "Eficiência Comercial", # <-- Adicionado LTV/CAC
        # "Perfis Completos",  # Comentado conforme solicitado
        # "Autonomia do Usuário",  # Comentado conforme solicitado
        # "Conformidade Jurídica",  # Comentado conforme solicitado
        "Score Médio do Show",
        "Churn em Valor",
        "Receita por Pessoal",
        "CSAT Artistas",
        "CSAT Operação"
    ]
    kpi_functions = {
        "CMGR": get_cmgr_variables,
        "Lucratividade": get_lucratividade_variables,
        "Net Revenue Retention": get_nrr_variables,
        "EBITDA": get_ebitda_variables,
        "Receita por Colaborador": get_rpc_variables,
        "Inadimplência": get_inadimplencia_variables,
        "Estabilidade": get_estabilidade_variables,
        "Nível de Serviço": get_nivel_servico_variables,
        "Churn %": get_churn_variables,
        "Turn Over": get_turnover_variables,
        "Palcos Vazios": get_palcos_vazios_variables,
        "Perdas Operacionais": get_perdas_operacionais_variables,
        "Crescimento Sustentável": get_crescimento_sustentavel_variables,
        "Perfis Completos": get_perfis_completos_variables,
        "Take Rate": get_take_rate_variables,
        "Autonomia do Usuário": get_autonomia_usuario_variables,
        "NPS Artistas": get_nps_artistas_variables,
        "NPS Equipe": get_nps_equipe_variables,
        "Conformidade Jurídica": get_conformidade_juridica_variables,
        "Eficiência de Atendimento": get_eficiencia_atendimento_variables,
        "Inadimplência Real": get_inadimplencia_real_variables,
        "Sucesso da Implantação": get_sucesso_implantacao_variables,
        "Roll 6M Growth": get_roll_6m_growth,
        "Eficiência Comercial": get_ltv_cac_variables, # <-- Adicionado LTV/CAC
        "Score Médio do Show": get_score_medio_show_variables,
        "Churn em Valor": get_churn_valor_variables,
        "Receita por Pessoal": get_receita_pessoal_variables,
        "CSAT Artistas": get_csat_artistas_variables,
        "CSAT Operação": get_csat_operacao_variables,
    }

    # # TASK A: Adicionando aliases
    # kpi_functions["Churn "] = kpi_functions["Churn"] 
    # kpi_functions["Net Revenue Retention "] = kpi_functions["Net Revenue Retention"]

    df_eshows_global = carregar_base_eshows()
    df_base2_global = carregar_base2()

    @app.callback(
        [Output('kpis-cards-container', 'children'),
        Output('painel-indicators-store', 'data')],
        [
            Input('kpi-ano-dropdown',      'value'),
            Input('kpi-periodo-dropdown',  'value'),
            Input('kpi-mes-dropdown',      'value'),
            Input('status-dropdown-kpis',  'value'),
            Input('area-dropdown-kpis',    'value'),
            Input('kpi-date-range',        'start_date'),
            Input('kpi-date-range',        'end_date'),
            Input('kpi-comparar-dropdown', 'value')          # ← comparativo
        ],
        [State('painel-indicators-store',  'data')],
        prevent_initial_call=True
    )
    def atualizar_todos_cards(ano, periodo, mes,
                            status_sel, area_sel,
                            start_date_main, end_date_main,
                            comparar_opcao,
                            current_indicators):

        # ------------------------------------------------------------------
        # 0) segurança | stores vacios
        # ------------------------------------------------------------------
        if not current_indicators:
            current_indicators = {}

        # ------------------------------------------------------------------
        # 1) range principal (se custom-range)
        # ------------------------------------------------------------------
        custom_range_principal = None
        if periodo == "custom-range" and start_date_main and end_date_main:
            custom_range_principal = (
                pd.to_datetime(start_date_main).normalize(),
                pd.to_datetime(end_date_main).normalize()
            )

        # ------------------------------------------------------------------
        # 2) range de COMPARAÇÃO (quando usuário pede "Período Anterior")
        # ------------------------------------------------------------------
        custom_range_comparacao = None
        ano_comp, periodo_comp, mes_comp = ano - 1, periodo, mes  # default: ano-1

        if comparar_opcao == "periodo_anterior":
            ini_p = get_period_start(ano, periodo, mes, custom_range_principal)
            fim_p = get_period_end  (ano, periodo, mes, custom_range_principal)

            duracao = fim_p - ini_p          # mesmo comprimento
            fim_cmp = ini_p - timedelta(days=1)
            ini_cmp = fim_cmp - duracao

            custom_range_comparacao = (ini_cmp, fim_cmp)
            periodo_comp            = "custom-range"
            ano_comp, mes_comp      = ini_cmp.year, ini_cmp.month

        elif comparar_opcao == "custom-compare" and start_date_main and end_date_main:
            custom_range_comparacao = (
                pd.to_datetime(start_date_main), pd.to_datetime(end_date_main)
            )
            periodo_comp = "custom-range"
            ano_comp     = custom_range_comparacao[0].year
            mes_comp     = custom_range_comparacao[0].month
        # caso 'ano_anterior': nada muda (ano-1) 

        # ─── aliases p/ manter variáveis usadas no resto da função ──────────
        custom_range_principal_tuple  = custom_range_principal
        custom_range_comparacao_tuple = custom_range_comparacao
        # -------------------------------------------------------------------

        # "ano anterior" continua igual: troca só o ano.
        # ------------------------------------------------------------------

        # bases em memória --------------------------------------------------
        bases_available = {
            "eshows": df_eshows_global,
            "base2":  df_base2_global,
            "pessoas": carregar_pessoas(),
            "ocorrencias": carregar_ocorrencias(),
            "inad": carregar_base_inad()
        }

        all_cards         = []
        painel_indicators = {}

        for kpi_name in kpi_list:
            kpi_key = kpi_name.strip()
            func    = kpi_functions.get(kpi_key)
            if not func:
                continue

            # -------------------------------------------------------------- #
            # 2.1) kwargs – bases + custom_range (se a função aceita)
            # -------------------------------------------------------------- #
            needed_bases   = kpi_bases_mapping.get(kpi_key, [])
            kwargs_current = {}
            for b in needed_bases:
                if b == "inad":
                    casas, artistas = bases_available["inad"]
                    kwargs_current["df_inad_casas"] = casas
                    kwargs_current["df_inad_artistas"] = artistas
                elif b in bases_available: # Adiciona verificação se a base existe
                    kwargs_current[f"df_{b}_global"] = bases_available[b]
            
            if 'custom_range' in func.__code__.co_varnames:
                kwargs_current['custom_range'] = custom_range_principal

            # cálculo principal ------------------------------------------- #
            try:
                data_now = func(ano, periodo, mes, **kwargs_current)
            except Exception as e:
                print(f"[ERRO] KPI {kpi_key} atual: {e}")
                data_now = {}

            valor_str      = data_now.get('resultado', "N/A")
            status_now     = data_now.get('status',   'controle')

            # filtros de Status / Área ------------------------------------ #
            if status_sel and status_now != status_sel:
                continue
            if area_sel and kpi_area_mapping.get(kpi_key) != area_sel:
                continue

            # -------------------------------------------------------------- #
            # 2.2) kwargs para COMPARAÇÃO
            # -------------------------------------------------------------- #
            kwargs_comp = {}
            for b in needed_bases:
                if b == "inad":
                    # Presumindo que as mesmas bases de inadimplência são usadas para comparação
                    # Se forem diferentes (ex: carregar_base_inad_comp()), ajuste aqui.
                    casas, artistas = bases_available["inad"] 
                    kwargs_comp["df_inad_casas"] = casas
                    kwargs_comp["df_inad_artistas"] = artistas
                elif b in bases_available: # Adiciona verificação se a base existe
                    kwargs_comp[f"df_{b}_global"] = bases_available[b]

            if 'custom_range' in func.__code__.co_varnames:
                kwargs_comp['custom_range'] = custom_range_comparacao

            try:
                data_comp = func(ano_comp, periodo_comp, mes_comp, **kwargs_comp)
                anterior_result_float = parse_valor_formatado(data_comp.get('resultado', "0"))
            except Exception as e:
                print(f"[ERRO] KPI {kpi_key} comparativo: {e}")
                anterior_result_float = 0.0

            atual_result_float = parse_valor_formatado(valor_str)
            variacao           = calcular_variacao_percentual(atual_result_float,
                                                            anterior_result_float)

            # -------------------------------------------------------------- #
            # 3) label do período comparado
            # -------------------------------------------------------------- #
            if comparar_opcao == "periodo_anterior":
                label_comp = mes_nome_intervalo(
                    filtrar_periodo_principal(
                        df_eshows_global,
                        ano_comp, periodo_comp, mes_comp,
                        custom_range_comparacao_tuple
                    ),
                    periodo_comp
                )
            elif comparar_opcao == "custom-compare":
                label_comp = mes_nome_intervalo(
                    filtrar_periodo_principal(
                        df_eshows_global,
                        ano_comp, periodo_comp, mes_comp,
                        custom_range_comparacao_tuple
                    ),
                    "custom-range"
                )
            else:  # ano anterior
                label_comp = f"{periodo} {ano-1}"

            # card --------------------------------------------------------- #
            info_kpi   = kpi_descriptions.get(kpi_key, {})
            format_kpi = info_kpi.get('format', 'numero')

            card = criar_card_kpi_painel(
                titulo       = kpi_key,
                valor        = valor_str,
                variacao     = variacao,
                periodo_comp = label_comp,
                format_type  = format_kpi,
                is_negative  = (info_kpi.get('behavior', 'Positivo') == 'Negativo')
            )
            all_cards.append(dbc.Col(card, xs=12, sm=6, md=6, lg=3))

            painel_indicators[kpi_key] = float(atual_result_float or 0.0)

        updated_indicators           = {**current_indicators, **painel_indicators}
        return all_cards, updated_indicators


    # Exemplo de logging (opcional)
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    import ast
    @app.callback(
        Output('kpi-selected-data', 'data'),
        Input({'type': 'kpi-icon-painel', 'index': ALL}, 'n_clicks'),
        [State('kpi-ano-dropdown', 'value'),
         State('kpi-periodo-dropdown', 'value'),
         State('kpi-mes-dropdown', 'value'),
         State('kpi-date-range', 'start_date'), # Novo State
         State('kpi-date-range', 'end_date')],  # Novo State
        prevent_initial_call=True
    )
    def update_kpi_selected_data(kpi_clicks, ano_value, periodo_value, mes_value, custom_start_date, custom_end_date): # Novos States
        ctx = dash.callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        # --- DataFrames needed ---
        # Reference the globally loaded dataframe (ensure df_eshows_global is loaded globally)
        # df_eshows_global = df_eshows_global # No need to reassign if it's truly global and loaded before

        # Calculate earliest/latest based on the global df_eshows_global
        # Ensure df_eshows_global is accessible here (should be if loaded globally)
        print("DEBUG: Calculando earliest/latest dentro de update_kpi_selected_data")
        df_casas_earliest = df_eshows_global.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow") if df_eshows_global is not None and not df_eshows_global.empty else None
        df_casas_latest = df_eshows_global.groupby("Id da Casa")["Data do Show"].max().reset_index(name="LastShow") if df_eshows_global is not None and not df_eshows_global.empty else None
        # Also ensure df_base2_global is accessible if needed later (e.g., for LTV/CAC call)
        # ------------------------------------------------------------------

        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if triggered_id.startswith("{") and 'type' in triggered_id:
            triggered_id_dict = ast.literal_eval(triggered_id)
            if triggered_id_dict.get('type') == 'kpi-icon-painel':
                if all(click is None or click == 0 for click in kpi_clicks):
                    raise dash.exceptions.PreventUpdate

                ano = ano_value
                periodo = periodo_value
                mes = mes_value

                if ano is None or periodo is None or mes is None:
                    raise dash.exceptions.PreventUpdate

                kpi_name = triggered_id_dict.get('index')
                kpi_info = kpi_descriptions.get(kpi_name, {})

                # --- Construir custom_range para a função do KPI ---
                current_custom_range = None
                if periodo_value == 'custom-range' and custom_start_date and custom_end_date:
                    try:
                        start_dt = pd.to_datetime(custom_start_date).normalize()
                        end_dt = pd.to_datetime(custom_end_date).normalize()
                        if start_dt <= end_dt:
                            current_custom_range = (start_dt, end_dt)
                    except Exception as e:
                        print(f"Erro ao converter datas para custom_range em update_kpi_selected_data: {e}")

                # --- Ajuste na chamada da função --- 
                func_to_call = kpi_functions.get(kpi_name)
                kpi_values = {} # Inicializa vazio
                if func_to_call:
                    try:
                        # Chamada específica para LTV/CAC
                        if kpi_name == 'Eficiência Comercial':
                            kpi_values = func_to_call(
                                ano=ano, periodo=periodo, mes=mes,
                                df_eshows_global=df_eshows_global, # Use the global one
                                df_base2_global=df_base2_global,   # Use the global df_base2_global
                                df_casas_earliest_global=df_casas_earliest, # Use calculated one
                                df_casas_latest_global=df_casas_latest,     # Use calculated one
                                custom_range=current_custom_range # Adicionado custom_range
                            )
                        # Adicione elif para outros KPIs com assinaturas diferentes
                        # elif kpi_name == 'OutroKPI': ...
                        
                        else: # Chamada genérica para os demais KPIs (ajuste se necessário)
                             # Mapeia quais bases injetar baseado no nome
                            needed_bases = kpi_bases_mapping.get(kpi_name, [])
                            kwargs_for_kpi = {}
                            bases_available = { # Define bases disponíveis no escopo
                                "eshows": df_eshows_global, # Use global
                                "base2": df_base2_global,   # Use global
                                "pessoas": carregar_pessoas(), # Carrega se necessário
                                "ocorrencias": carregar_ocorrencias(), # Carrega se necessário
                                "inad": carregar_base_inad() # Carrega se necessário
                            }
                            for base_tag in needed_bases:
                                if base_tag == "eshows": kwargs_for_kpi["df_eshows_global"] = bases_available["eshows"]
                                elif base_tag == "base2": kwargs_for_kpi["df_base2_global"] = bases_available["base2"]
                                elif base_tag == "pessoas": kwargs_for_kpi["df_pessoas_global"] = bases_available["pessoas"]
                                elif base_tag == "ocorrencias": kwargs_for_kpi["df_ocorrencias_global"] = bases_available["ocorrencias"]
                                elif base_tag == "inad": 
                                    casas, artistas = bases_available["inad"]
                                    kwargs_for_kpi["df_inad_casas"] = casas
                                    kwargs_for_kpi["df_inad_artistas"] = artistas
                                # Passe custom_range se a função o aceitar
                                # if 'custom_range' in func_to_call.__code__.co_varnames: # Checagem básica
                                #    kwargs_for_kpi['custom_range'] = custom_range_value # Precisa obter custom_range
                            
                            kpi_values = func_to_call(ano=ano, periodo=periodo, mes=mes, **kwargs_for_kpi)
                            
                    except Exception as e:
                        print(f"Erro ao chamar {kpi_name}: {e}")
                        kpi_values = {} # Retorna vazio em caso de erro
                # -----------------------------------

                if not kpi_values:
                    print(f"WARNING: kpi_values vazio para {kpi_name}")
                    # raise dash.exceptions.PreventUpdate # Decide se quer impedir update ou mostrar modal vazio

                kpi_data = {
                    'kpi_name': kpi_name,
                    'ano': ano,
                    'periodo': periodo,
                    'mes': mes,
                    'control_info': kpi_info.get("control_values", {}),
                    'variables_values': kpi_values.get('variables_values', {}),
                    'resultado': kpi_values.get('resultado', ''),
                    'periodo_texto': kpi_values.get('periodo', ''),
                    'status': kpi_values.get('status', ''),
                }
                print(f"DEBUG: kpi_data a ser armazenado para {kpi_name}: {kpi_data}") # DEBUG STORE
                return kpi_data

        raise dash.exceptions.PreventUpdate
  
    ########################################
    # CALLBACK DE ABRIR/FECHAR O MODAL
    ########################################
    @app.callback(
        Output('kpi-painel-modal', 'is_open'),
        Output('kpi-painel-modal-title', 'children'),
        [Input({'type': 'kpi-icon-painel', 'index': ALL}, 'n_clicks'),
         Input('close-kpi-painel-modal', 'n_clicks')], # Adicionado input do novo botão de fechar
        [State('kpi-painel-modal', 'is_open')],
        prevent_initial_call=True
    )
    def toggle_modal(kpi_clicks, close_click, modal_is_open): # Adicionado close_click
        ctx = dash.callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        triggered_id_str = ctx.triggered[0]['prop_id'].split('.')[0]

        # Checa se o botão de fechar foi clicado
        if triggered_id_str == 'close-kpi-painel-modal' and close_click:
            return False, dash.no_update # Fecha o modal, não atualiza o título

        # Lógica original para abrir o modal pelo ícone do KPI
        if triggered_id_str.startswith("{"):
            try:
                triggered_id_dict = ast.literal_eval(triggered_id_str)
                if triggered_id_dict.get('type') == 'kpi-icon-painel':
                    if all(click is None or click == 0 for click in kpi_clicks):
                        raise dash.exceptions.PreventUpdate

                    kpi_name = triggered_id_dict.get('index')
                    kpi_info = kpi_descriptions.get(kpi_name, {})
                    title = kpi_info.get("title", kpi_name)
                    return True, f"Detalhes do KPI: {title}"
            except (ValueError, SyntaxError):
                # Se não for um dict stringuificado, ou erro de parsing, ignora este trigger
                pass

        raise dash.exceptions.PreventUpdate
    
    #CALLBACK KPI DESCRIÇÃO 
    def remove_code_fences(text):
        """
        Remove trechos de código encapsulados por ``` ou ~~~,
        além de strings como 'md\n', que por vezes podem vir de conteúdos de Markdown.
        """
        # Remove blocos ```...```
        text = re.sub(r'(?s)```.*?```', '', text)
        # Remove blocos ~~~...~~~
        text = re.sub(r'(?s)~~~.*?~~~', '', text)
        # Remove possíveis 'md\n'
        text = re.sub(r'\b(md|python)\n', '', text)
        # Remove texto que por vezes acompanha "Copiar código"
        text = text.replace('Copiar código', '')
        return textwrap.dedent(text).strip()


    def parse_valor_formatado(valor_str):
        """
        Converte strings de valor em float. Exemplo:
        - "R$8.8k" -> 8800
        - "R$3.95M" -> 3950000
        - "12.3%" -> 12.3
        - "N/A" -> 0.0
        """
        if isinstance(valor_str, (int, float)):
            return float(valor_str)
        v = valor_str.strip()

        # Remove prefixos/sufixos
        v = (v.replace('R$', '')
            .replace('%', '')
            .replace(',', '.')
            .replace(' ', '')
            .lower())  # => "8.8k" ou "3.95m"

        multiplicador = 1.0

        # Se contiver "k" => milhar
        if 'k' in v:
            v = v.replace('k', '')
            multiplicador = 1000.0

        # Se contiver "m" => milhão
        if 'm' in v:
            v = v.replace('m', '')
            multiplicador = 1_000_000.0

        try:
            return float(v) * multiplicador
        except:
            return 0.0


    def to_float_percent_local(valor_str):
        """
        Converte strings como "12.3%", "12,3%" ou "12,3" em float 12.3.
        """
        if not valor_str:
            return 0.0
        try:
            valor_str = valor_str.replace('%', '').replace(',', '.')
            return float(valor_str)
        except:
            return 0.0

    @app.callback(
        Output('kpi-description', 'children'),
        Input('kpi-selected-data', 'data'),
        prevent_initial_call=True
    )
    def update_kpi_description(kpi_data):
        """
        Callback que preenche o texto de descrição dos KPIs dentro do modal
        (dcc.Markdown id='kpi-description').
        """
        if not kpi_data or 'kpi_name' not in kpi_data:
            raise dash.exceptions.PreventUpdate

        # ------------------------------------------------------------ básicos
        variaveis_explicadas = ""

        kpi_name         = kpi_data.get('kpi_name')
        variables_values = kpi_data.get('variables_values', {})
        resultado        = kpi_data.get('resultado', '0')
        periodo_texto    = kpi_data.get('periodo_texto', '')

        # --------------------------------------------------- dados do JSON
        kpi_info         = kpi_descriptions.get(kpi_name, {})
        raw_description  = kpi_info.get("description", "Descrição não disponível.")
        description      = remove_code_fences(raw_description)
        formula          = kpi_info.get("formula", "Fórmula não disponível.")
        variables        = kpi_info.get("variables", {})
        responsible_area = kpi_info.get('responsible_area', 'Área não definida.')

        # ------------------------------------------------- período inicial/final
        periodo_inicial_texto = periodo_texto
        periodo_final_texto   = ""
        if " até " in periodo_texto:
            parts = periodo_texto.split(" até ")
            periodo_inicial_texto = parts[0]
            periodo_final_texto   = parts[-1]

        # --------------------------------------------------- helpers/moldes
        resultado_num   = to_float_percent_local(resultado)
        resultado_latex = f"{resultado_num:,.2f}\\%"

        computed_formula = ""
        itens            = []
        general_formula  = ""

        # ================================================= CMGR  ============
        if kpi_name == 'CMGR':
            receita_final_val   = variables_values.get('Receita final', 0)
            receita_inicial_val = variables_values.get('Receita inicial', 0)
            n                   = variables_values.get('n', 1)

            # períodos específicos vindos da função get_cmgr_variables
            periodo_ini_txt = variables_values.get('Periodo inicial', periodo_inicial_texto)
            periodo_fim_txt = variables_values.get('Periodo final',  periodo_final_texto)

            receita_inicial_fmt = formatar_valor_utils(receita_inicial_val, 'monetario')
            receita_final_fmt   = formatar_valor_utils(receita_final_val, 'monetario')

            computed_formula = (
                f"CMGR = \\Bigl(\\dfrac{{{receita_final_fmt}}}{{{receita_inicial_fmt}}}\\Bigr)"
                f"^{{\\dfrac{{1}}{{{n}}}}} - 1 \\;=\\; {resultado_latex}"
            )

            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Receita Inicial em {periodo_ini_txt}:** {receita_inicial_fmt}",
                f"**Receita Final em {periodo_fim_txt}:** {receita_final_fmt}",
                f"**n (meses contados):** {n}",
            ]

            general_formula = (
                "CMGR = \\Bigl(\\dfrac{Receita_{final}}{Receita_{inicial}}\\Bigr)^{\\dfrac{1}{n}} - 1"
            )

        elif kpi_name == 'Lucratividade':
            lucro_liquido_val     = variables_values.get('Lucro Líquido', 0)
            faturamento_total_val = variables_values.get('Faturamento Total', 0)

            lucro_liquido_fmt     = formatar_valor_utils(lucro_liquido_val, 'monetario')
            faturamento_total_fmt = formatar_valor_utils(faturamento_total_val, 'monetario')

            # Fórmula simplificada
            computed_formula = (
                f"Lucratividade = \\frac{{{lucro_liquido_fmt}}}{{{faturamento_total_fmt}}}"
                f" \\times 100 = {resultado_latex}"
            )
            
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Faturamento Total:** {faturamento_total_fmt}",
                f"**Lucro Líquido (Faturamento - Custos):** {lucro_liquido_fmt}"
            ]
            
            # Fórmula genérica ajustada para evitar sobreposição
            general_formula = (
                "Lucratividade = \\frac{\\text{Lucro Liquido}}{\\text{Faturamento Total}} \\times 100"
            )

        elif kpi_name == 'Net Revenue Retention':
            # ---- captura dinâmica dos rótulos -------------------------
            keys   = [k for k in variables_values.keys() if k.startswith("Receita")]
            keys.sort()                               # garante ordem "anterior", "atual"
            key_ant   = keys[0] if len(keys) > 0 else "Receita Anterior"
            key_atual = keys[1] if len(keys) > 1 else "Receita Atual"

            receita_ant_val = variables_values.get(key_ant,   0)
            receita_atu_val = variables_values.get(key_atual, 0)
            delta_val       = variables_values.get("Variação Absoluta", receita_atu_val - receita_ant_val)

            # ---- formatação amigável ---------------------------------
            receita_ant_fmt = formatar_valor_utils(receita_ant_val, 'monetario')
            receita_atu_fmt = formatar_valor_utils(receita_atu_val, 'monetario')
            delta_fmt       = formatar_valor_utils(delta_val,       'monetario')

            # ---- fórmula (fração grande) -----------------------------
            computed_formula = (
                f"NRR = \\Bigl(\\dfrac{{{receita_atu_fmt} - {receita_ant_fmt}}}{{{receita_ant_fmt}}}\\Bigr)"
                f" \\times 100 \\;=\\; {resultado_latex}"
            )

            # ---- bullets "Temos:" ------------------------------------
            itens = [
                f"**Período analisado:** {periodo_texto}",
                f"**{key_ant}:** {receita_ant_fmt}",
                f"**{key_atual}:** {receita_atu_fmt}",
                f"**Variação absoluta:** {delta_fmt}",
            ]

            # ---- fórmula genérica p/ seção "Como é calculado?" -----
            general_formula = (
                "NRR = \\Bigl(\\dfrac{\\text{Receita}_{Atual} - "
                "\\text{Receita}_{Anterior}}{\\text{Receita}_{Anterior}}\\Bigr) "
                "\\times 100"
            )

        elif kpi_name == 'EBITDA':
            # 1) Captura valores do EBTIDA
            ebtida_val    = variables_values.get('EBTIDA Valor', 0)
            receita_ebt   = variables_values.get('Receita EBTIDA', 0)
            custos_ebt    = variables_values.get('Custos EBTIDA', 0)
            notas_val     = variables_values.get('Notas Fiscais', 0)
            imposto_val   = variables_values.get('Imposto', 0)

            ebtida_txt   = formatar_valor_utils(ebtida_val, 'monetario')
            rec_ebt_txt  = formatar_valor_utils(receita_ebt, 'monetario')
            cst_ebt_txt  = formatar_valor_utils(custos_ebt, 'monetario')
            notas_txt    = formatar_valor_utils(notas_val, 'monetario')
            imposto_txt  = formatar_valor_utils(imposto_val, 'monetario')

            resultado_num   = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            # 2) Fórmula final
            computed_formula = (
                f"EBITDA\\% = \\Bigl(\\frac{{({rec_ebt_txt} - {cst_ebt_txt})}}{{{rec_ebt_txt}}}\\Bigr) "
                f"\\times 100 = {resultado_latex}"
            )

            # 3) Bullets de exibição
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Receita EBTIDA:** {rec_ebt_txt}",
                f"**Notas Fiscais (dedução):** {notas_txt}",
                f"**Custos EBTIDA:** {cst_ebt_txt}",
                f"**Imposto Total:** {imposto_txt}",
                f"**EBITDA (R$):** {ebtida_txt}"
            ]

            # 4) Fórmula genérica LaTeX
            general_formula = (
                "EBITDA\\% = \\Bigl(\\frac{Receita_{EBTIDA} - Custos_{EBTIDA}}{Receita_{EBTIDA}}\\Bigr) \\times 100"
            )

            # 5) **Sobrescreve** as variáveis para "Onde:"
            #    Em vez de usar as do JSON, definimos manualmente:
            variables = {
                "Receita EBTIDA": "Receita Total - Receita de Notas Emitidas",
                "Custos EBTIDA": "Custo Total - Impostos",
                "Notas Fiscais": "Ajustes de notas fiscais emitidas",
                "Imposto": "Custo com Imposto"
            }

            # 6) Gera a string "Onde:" com as novas variáveis
            variaveis_explicadas = "\n".join([f"- **{var}:** {desc}" for var, desc in variables.items()])

            # E depois montamos "detalhes_reais" e "markdown_content" normalmente,
            # sem cair no fallback "Fórmula específica não disponível".

        elif kpi_name == 'Receita por Colaborador':
            # 1) Extrair valores do dict 'variables_values'
            fat_val   = variables_values.get('Faturamento', 0)
            media_val = variables_values.get('Média de Funcionários', 0)
            meses_val = variables_values.get('Meses Contabilizados', 1)

            # 2) Converter 'resultado' p/ float e formatar monetário
            rpc_float = parse_valor_formatado(resultado)  # ex.: "R$8.3k" -> 8300.0
            rpc_str   = formatar_valor_utils(rpc_float, 'monetario')  # ex. "R$8.3k"

            # 3) Formatar também Faturamento e média
            fat_str   = formatar_valor_utils(fat_val, 'monetario')  # ex. "R$529.5k"
            media_str = f"{media_val:.1f}"
            meses_str = str(meses_val)

            # 4) Versão ajustada da fórmula
            computed_formula = (
                f"RPC(\\text{{mes}}) = \\left(\\frac{{{fat_str}}}{{{media_str}}}\\right) "
                f"\\div {meses_str} = {rpc_str}"
            )

            # 5) Lista de itens que irão aparecer em "Temos:" no modal
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Faturamento Total (no período):** {fat_str}",
                f"**Média de Funcionários:** {media_str}",
                f"**Quantidade de Meses:** {meses_str}"
            ]

            # 6) Fórmula genérica simplificada
            general_formula = (
                "RPC_{\\text{mensal}} = \\frac{\\text{Faturamento}}{\\text{Media de Funcionarios}} "
                "\\div \\text{Numero de Meses}"
            )

            # 7) Variáveis explicadas
            vars_expl = {
                "Faturamento": "Somatório do faturamento no período considerado",
                "Funcionários": "Número total de funcionários ativos (somado mês a mês)",
            }
            variaveis_explicadas = "\n".join([f"- **{var}:** {desc}" for var, desc in vars_expl.items()])

        elif kpi_name == 'Inadimplência':
            # 1) Pegar variáveis
            valor_inad = variables_values.get('Valor Inadimplente', 0)
            gmv_val = variables_values.get('GMV', 0)

            # 2) Formatar
            valor_inad_fmt = formatar_valor_utils(valor_inad, 'monetario')
            gmv_fmt = formatar_valor_utils(gmv_val, 'monetario')

            # 3) Converter resultado
            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:.2f}\\%"

            # 4) Fórmula com os valores - simplificada
            computed_formula = (
                f"Inadimplencia\\% = \\dfrac{{{valor_inad_fmt}}}{{{gmv_fmt}}}"
                f" \\times 100 = {resultado_latex}"
            )

            # 5) itens: lista com bullet points
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**GMV:** {gmv_fmt}",
                f"**Valor Inadimplente:** {valor_inad_fmt}",
            ]

            # 6) general_formula: versão simplificada
            general_formula = (
                "Inadimplencia\\% = \\dfrac{\\text{Valor Inadimplente}}{\\text{GMV}} \\times 100"
            )

            # 7) Explicação das variáveis
            vars_expl = {
                "Valor Inadimplente": "Somatório do valor de todos os boletos vencidos há mais de 22 dias",
                "GMV": "Valor Total dos shows transacionados no período selecionado"
            }
            variaveis_explicadas = "\n".join([f"- **{k}:** {v}" for k,v in vars_expl.items()])

        elif kpi_name == 'Estabilidade':
            # ----------------------------------------------------------------
            # 1) Valores médios brutos
            # ----------------------------------------------------------------
            uptime_val      = variables_values.get('Uptime (%)',        0)
            mtbf_val        = variables_values.get('MTBF (horas)',      0)
            mttr_val        = variables_values.get('MTTR (Min)',        0)
            taxa_erros_val  = variables_values.get('Taxa de Erros (%)', 0)

            uptime_txt = formatar_valor_utils(uptime_val, 'numero_2f')
            mtbf_txt   = formatar_valor_utils(mtbf_val,   'numero_2f')
            mttr_txt   = formatar_valor_utils(mttr_val,   'numero_2f')
            erros_txt  = formatar_valor_utils(taxa_erros_val, 'numero_2f')

            # ----------------------------------------------------------------
            # 2) Valores normalizados (0 – 100) vindos da função geradora
            # ----------------------------------------------------------------
            up_norm = variables_values.get('Uptime Normalizado', 0)
            mb_norm = variables_values.get('MTBF Normalizado',   0)
            mt_norm = variables_values.get('MTTR Normalizado',   0)
            er_norm = variables_values.get('Erros Normalizado',  0)

            up_norm_txt = formatar_valor_utils(up_norm, 'numero_2f')
            mb_norm_txt = formatar_valor_utils(mb_norm, 'numero_2f')
            mt_norm_txt = formatar_valor_utils(mt_norm, 'numero_2f')
            er_norm_txt = formatar_valor_utils(er_norm, 'numero_2f')

            # ----------------------------------------------------------------
            # 3) Pesos
            # ----------------------------------------------------------------
            PESO_UP, PESO_MB, PESO_MT, PESO_ER = 0.4, 0.2, 0.2, 0.2

            resultado_num   = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            # ----------------------------------------------------------------
            # 4) Fórmula resolvida (LaTeX)
            # ----------------------------------------------------------------
            computed_formula = (
                f"\\text{{Índice}} = "
                f"({up_norm_txt}\\% \\times {PESO_UP}) + "
                f"({mb_norm_txt}\\% \\times {PESO_MB}) + "
                f"({mt_norm_txt}\\% \\times {PESO_MT}) + "
                f"({er_norm_txt}\\% \\times {PESO_ER}) = {resultado_latex}"
            )

            # ----------------------------------------------------------------
            # 5) Itens (sem entradas vazias)
            # ----------------------------------------------------------------
            itens = [
                f"**Período analisado:** {periodo_texto}",

                "**Valores médios brutos:**",
                f"Uptime: {uptime_txt}%",
                f"MTBF: {mtbf_txt} horas",
                f"MTTR: {mttr_txt} min",
                f"Taxa de Erros: {erros_txt}%",

                "**Valores normalizados (0 – 100):**",
                f"Uptime: {up_norm_txt}%",
                f"MTBF: {mb_norm_txt}%",
                f"MTTR: {mt_norm_txt}%",
                f"Taxa de Erros: {er_norm_txt}%",

                "**Pesos aplicados:** 0.4 / 0.2 / 0.2 / 0.2",
            ]

            # ----------------------------------------------------------------
            # 6) Fórmula genérica
            # ----------------------------------------------------------------
            general_formula = (
                "\\text{Índice} = (\\text{Uptime}_{norm}\\% \\times 0.4) + "
                "(\\text{MTBF}_{norm}\\% \\times 0.2) + "
                "(\\text{MTTR}_{norm}\\% \\times 0.2) + "
                "(\\text{Taxa de Erros}_{norm}\\% \\times 0.2)"
            )

        elif kpi_name == 'Nível de Serviço':
            # Extrair variáveis do dicionário retornado pela função "get_nivel_servico_variables"
            occ_excl_val = variables_values.get('Ocorrências (excl. leves)', 0)
            shows_val    = variables_values.get('Shows', 0)

            # Formatar cada uma para exibir no modal
            # Se quiser só número inteiro, pode usar 'numero'
            occ_excl_fmt = formatar_valor_utils(occ_excl_val, 'numero')  # ex.: "10"
            shows_fmt    = formatar_valor_utils(shows_val, 'numero')     # ex.: "37"

            # Montar a "fórmula computada" (LaTeX) exibindo o valor final (resultado)
            # => "Nível de Serviço = (10 / 37) x 100 = 27.03%"
            computed_formula = (
                f"Nível de Serviço = \\left(\\frac{{{occ_excl_fmt}}}{{{shows_fmt}}}\\right) \\times 100 "
                f"= {resultado}"
            )
            # Aqui, "resultado" em si é a string final do KPI (p.ex. "3.45%").

            # Lista de itens que vão aparecer em "Temos:" no modal
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Ocorrências (excluindo leves):** {occ_excl_fmt}",
                f"**Shows Totais:** {shows_fmt}"
            ]

            # Fórmula genérica, sem valores, para aparecer na seção "Como é calculado?"
            general_formula = (
                "Nível de Serviço = \\left(\\frac{\\text{Ocorrências Excl. Leves}}{\\text{Total de Shows}}\\right) \\times 100"
            )

            # Montar "Onde:" (se quiser explicar cada variável). Exemplo:
            variables = {
                "Ocorrências (excl. leves)": "Contagem de ocorrências, excluindo as que têm TIPO='Leve'",
                "Shows": "Número total de shows no período"
            }
            variaveis_explicadas = "\n".join([f"- **{v}:** {desc}" for v, desc in variables.items()])

        elif kpi_name == 'Churn %':
            estabelecimentos_perdidos_val = variables_values.get('Estabelecimentos Perdidos', 0)
            estabelecimentos_ativos_val   = variables_values.get('Estabelecimentos Ativos no Período', 0)

            perdidos_txt = formatar_valor_utils(estabelecimentos_perdidos_val, 'numero')
            ativos_txt   = formatar_valor_utils(estabelecimentos_ativos_val, 'numero')

            resultado_num   = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            computed_formula = (
                f"Churn \\% = \\frac{{{perdidos_txt}}}{{{ativos_txt}}} \\times 100 = {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Estabelecimentos Perdidos:** {perdidos_txt}",
                f"**Estabelecimentos Ativos no Período:** {ativos_txt}"
            ]
            general_formula = (
                "Churn \\% = \\frac{Estabelecimentos_{Perdidos}}{Estabelecimentos_{Ativos}} \\times 100"
            )

        elif kpi_name == 'Turn Over':
            desl_val = variables_values.get('Desligamentos', 0)
            inic_val = variables_values.get('Funcionários Iniciais', 0)

            desl_txt = formatar_valor_utils(desl_val, 'numero')
            inic_txt = formatar_valor_utils(inic_val, 'numero')

            # Simplificada
            computed_formula = (
                f"Turn Over\\% = \\frac{{{desl_txt}}}{{{inic_txt}}} \\times 100 = {resultado}"
            )
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Desligamentos:** {desl_txt}",
                f"**Funcionários Iniciais:** {inic_txt}"
            ]
            # Simplificada
            general_formula = "Turn Over\\% = \\frac{\\text{Desligamentos}}{\\text{Funcionarios Iniciais}} \\times 100"

            vars_tu = {
                "Desligamentos": "Pessoas que saíram no intervalo",
                "Funcionários Iniciais": "Ativos no primeiro dia do período"
            }
            variaveis_explicadas = "\n".join([f"- **{k}:** {v}" for k,v in vars_tu.items()])

        elif kpi_name == 'Palcos Vazios':
            palcos_vazios_val = variables_values.get('Palcos Vazios', 0)
            palcos_vazios_txt = formatar_valor_utils(palcos_vazios_val, 'numero')

            computed_formula = f"Palcos Vazios = {palcos_vazios_txt}"
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Palcos Vazios no Período:** {palcos_vazios_txt}"
            ]
            general_formula = "Palcos Vazios"

        elif kpi_name == 'Perdas Operacionais':
            erros_op_val  = variables_values.get('Erros Operacionais (Op. Shows)', 0)
            fat_val       = variables_values.get('Faturamento', 0)

            # Formatar para exibir no modal
            erros_op_fmt = formatar_valor_utils(erros_op_val, 'monetario')
            fat_fmt      = formatar_valor_utils(fat_val, 'monetario')

            # Simplificada
            computed_formula = (
                f"Perdas Operacionais\\% = \\frac{{{erros_op_fmt}}}{{{fat_fmt}}}"
                f" \\times 100 = {resultado}"
            )

            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Erros Operacionais (R$):** {erros_op_fmt}",
                f"**Faturamento (R$):** {fat_fmt}"
            ]

            # Já estava correta
            general_formula = (
                "Perdas Operacionais\\% = \\frac{\\text{Erros Operacionais}}{\\text{Faturamento}} \\times 100"
            )

            # Ajustando a descrição "Onde:"
            variables = {
                "Erros Operacionais": "Despesas originadas por erros operacionais (lançamentos duplicados, palco vazio, transporte, etc.)",
                "Faturamento": "Faturamento no Período Analisado"
            }
            variaveis_explicadas = "\n".join([f"- **{v}:** {desc}" for v, desc in variables.items()])

        elif kpi_name == "Crescimento Sustentável":
            # ─── identifica anos automaticamente ───────────────────────────
            fat_keys = sorted(k for k in variables_values if k.startswith("Faturamento"))
            cus_keys = sorted(k for k in variables_values if k.startswith("Custos"))
            if len(fat_keys) < 2 or len(cus_keys) < 2:
                itens = ["Não há dados suficientes para exibir a descrição."]
                computed_formula = general_formula = ""
            else:
                ano_prev   = int(fat_keys[0].split()[-1])
                ano_atual  = int(fat_keys[1].split()[-1])

                # --- valores formatados -----------------------------------
                fat_prev_txt = formatar_valor_utils(variables_values[fat_keys[0]], "monetario")
                fat_atual_txt = formatar_valor_utils(variables_values[fat_keys[1]], "monetario")
                cus_prev_txt = formatar_valor_utils(variables_values[cus_keys[0]], "monetario")
                cus_atual_txt = formatar_valor_utils(variables_values[cus_keys[1]], "monetario")

                var_fat_txt = formatar_valor_utils(variables_values["Variação do Faturamento (%)"], "percentual")
                var_cus_txt = formatar_valor_utils(variables_values["Variação dos Custos (%)"], "percentual")

                # --- LaTeX simplificado ---------------------------------------
                resultado_num = to_float_percent_local(resultado)
                
                # Fórmula simplificada usando frações individuais
                computed_formula = (
                    f"\\text{{Crescimento Sustentavel}} = \\left(\\frac{{{fat_atual_txt} - {fat_prev_txt}}}{{{fat_prev_txt}}}\\right) - \\left(\\frac{{{cus_atual_txt} - {cus_prev_txt}}}{{{cus_prev_txt}}}\\right) = {resultado_num:.2f}\\%"
                )

                # Fórmula genérica vem do JSON, mas sobrescrevemos se necessário
                general_formula = "\\text{Crescimento Sustentavel} = (\\Delta\\%\\text{Faturamento}) - (\\Delta\\%\\text{Custos})"

                itens = [
                    f"**Período:** {periodo_texto}",
                    f"**Faturamento {ano_prev}:** {fat_prev_txt}",
                    f"**Faturamento {ano_atual}:** {fat_atual_txt}",
                    f"**Variação do Faturamento:** {var_fat_txt}",
                    f"**Custos {ano_prev}:** {cus_prev_txt}",
                    f"**Custos {ano_atual}:** {cus_atual_txt}",
                    f"**Variação dos Custos:** {var_cus_txt}",
                ]
                
        elif kpi_name == 'Perfis Completos':
            base_completa_val = variables_values.get('Base Acumulada Completa', 0)
            base_total_val = variables_values.get('Base Acumulada Total', 0)

            base_completa_txt = formatar_valor_utils(base_completa_val, 'numero')
            base_total_txt = formatar_valor_utils(base_total_val, 'numero')

            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            computed_formula = (
                f"Perfis Completos = \\frac{{{base_completa_txt}}}{{{base_total_txt}}} \\times 100 = {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Base Acumulada Completa:** {base_completa_txt}",
                f"**Base Acumulada Total:** {base_total_txt}"
            ]
            general_formula = (
                "Perfis Completos = \\frac{Base_{Completa}}{Base_{Total}} \\times 100"
            )

        elif kpi_name == 'Take Rate':
            # Corrige as chaves vindas de variables_values
            comissao_val = variables_values.get('Comissão B2B (R$)', variables_values.get('Comissão Total', 0))
            gmv_val       = variables_values.get('GMV (R$)',        variables_values.get('GMV', 0))

            comissao_txt = formatar_valor_utils(comissao_val, 'monetario')
            gmv_txt      = formatar_valor_utils(gmv_val, 'monetario')

            resultado_num   = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            # Fórmula com \dfrac para melhor legibilidade
            computed_formula = (
                f"Take\\ Rate = \\dfrac{{{comissao_txt}}}{{{gmv_txt}}} \\times 100 = {resultado_latex}"
            )

            # Bullets "Temos:" com informações claras
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Comissão B2B (acumulada):** {comissao_txt}",
                f"**GMV (acumulado):** {gmv_txt}"
            ]

            # Fórmula genérica em LaTeX
            general_formula = (
                "Take\\ Rate = \\dfrac{\\text{Comissao Total}}{\\text{GMV}} \\times 100"
            )

        elif kpi_name == 'Autonomia do Usuário':
            propostas_usuarios_val = variables_values.get('Propostas Lançadas Usuários', 0)
            propostas_internas_val = variables_values.get('Propostas Lançadas Internas', 0)

            puser_txt = formatar_valor_utils(propostas_usuarios_val, 'numero')
            pinterna_txt = formatar_valor_utils(propostas_internas_val, 'numero')

            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            computed_formula = (
                f"Autonomia do Usuário = \\frac{{{puser_txt}}}{{({puser_txt} + {pinterna_txt})}} "
                f"\\times 100 = {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Propostas Lançadas Usuários:** {puser_txt}",
                f"**Propostas Lançadas Internas:** {pinterna_txt}"
            ]
            general_formula = (
                "Autonomia do Usuário = \\frac{Propostas_{Usuários}}{Propostas_{Usuários} + Propostas_{Internas}} \\times 100"
            )

        elif kpi_name == 'NPS Artistas':
            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            computed_formula = (
                f"NPS Artistas = \\text{{Media de NPS dos Artistas}} \\times 100 = {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}"
            ]
            general_formula = "NPS Artistas = \\text{Media de NPS dos Artistas} \\times 100"

        elif kpi_name == 'NPS Equipe':
            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            computed_formula = (
                f"NPS Equipe = \\text{{Media de NPS da Equipe}} \\times 100 = {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}"
            ]
            general_formula = "NPS Equipe = \\text{Media de NPS da Equipe} \\times 100"

        elif kpi_name == 'Conformidade Jurídica':
            casas_contrato_val = variables_values.get('Casas Contrato', 0)
            casas_ativas_val = variables_values.get('Casas Ativas', 0)

            casas_contrato_txt = formatar_valor_utils(casas_contrato_val, 'numero')
            casas_ativas_txt = formatar_valor_utils(casas_ativas_val, 'numero')

            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            computed_formula = (
                f"Conformidade Jurídica = \\frac{{{casas_contrato_txt}}}{{{casas_ativas_txt}}} \\times 100 = {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Casas Contrato:** {casas_contrato_txt}",
                f"**Casas Ativas:** {casas_ativas_txt}"
            ]
            general_formula = (
                "Conformidade Jurídica = \\frac{Casas_{Contrato}}{Casas_{Ativas}} \\times 100"
            )

        elif kpi_name == 'Eficiência de Atendimento':
            tempo_resposta_medio_val = variables_values.get('Tempo Resposta Médio', 0)
            tempo_resolucao_medio_val = variables_values.get('Tempo Resolução Média', 0)

            tempo_resposta_txt = f"{formatar_valor_utils(tempo_resposta_medio_val, 'numero_2f')} min"
            tempo_resolucao_txt = f"{formatar_valor_utils(tempo_resolucao_medio_val, 'numero_2f')} min"

            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            # Simplificada
            computed_formula = (
                "Eficiencia de Atendimento = \\frac{\\text{Meta TP}}{\\text{TP Medio}} \\times \\text{Peso TP} + "
                "\\frac{\\text{Meta TR}}{\\text{TR Medio}} \\times \\text{Peso TR} "
                f"= {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Tempo Resposta Médio:** {tempo_resposta_txt}",
                f"**Tempo Resolução Média:** {tempo_resolucao_txt}"
            ]
            # Simplificada
            general_formula = (
                "Eficiencia de Atendimento = \\frac{\\text{Meta TP}}{\\text{TP Medio}} \\times \\text{Peso TP} + "
                "\\frac{\\text{Meta TR}}{\\text{TR Medio}} \\times \\text{Peso TR}"
            )

        elif kpi_name == 'Inadimplência Real':
            # 1) Pegar variáveis
            valor_adiant_inad = variables_values.get('Adiantado Inadimplente', 0)
            fat_val = variables_values.get('Faturamento', 0)

            # 2) Formatar
            adiant_fmt = formatar_valor_utils(valor_adiant_inad, 'monetario')
            fat_fmt = formatar_valor_utils(fat_val, 'monetario')

            # 3) Converter resultado para float
            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:.2f}\\%"

            # 4) computed_formula - simplificada
            computed_formula = (
                f"Inadimplencia Real\\% = \\frac{{{adiant_fmt}}}{{{fat_fmt}}}"
                f" \\times 100 = {resultado_latex}"
            )

            # 5) itens
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Faturamento:** {fat_fmt}",
                f"**Valor Adiantado Inadimplente:** {adiant_fmt}",
            ]

            # 6) general_formula - simplificada
            general_formula = (
                "Inadimplencia Real\\% = \\frac{\\text{Valor Adiantado Inadimplente}}{\\text{Faturamento}} \\times 100"
            )

            # 7) Explicação das variáveis
            vars_expl = {
                "Adiantado Inadimplente": "Soma dos valores adiantados a artistas que ainda não foram pagos pela casa (boleto em aberto há mais de 22 dias)",
                "Faturamento": "Faturamento Total da Eshows no período"
            }
            variaveis_explicadas = "\n".join([f"- **{k}:** {v}" for k,v in vars_expl.items()])

        elif kpi_name == 'Sucesso da Implantação':
            novos_clientes_val = variables_values.get('Novos Clientes', 0)
            clientes_implantacao_val = variables_values.get('Casas Implantação', 0)

            novos_clientes_txt = formatar_valor_utils(novos_clientes_val, 'numero')
            clientes_implantacao_txt = formatar_valor_utils(clientes_implantacao_val, 'numero')

            resultado_num = to_float_percent_local(resultado)
            resultado_latex = f"{resultado_num:,.2f}\\%"

            computed_formula = (
                f"Sucesso da Implantação = \\frac{{{novos_clientes_txt}}}{{{clientes_implantacao_txt}}} "
                f"\\times 100 = {resultado_latex}"
            )
            itens = [
                f"**Período:** {periodo_texto}",
                f"**Novos Clientes:** {novos_clientes_txt}",
                f"**Casas Implantação:** {clientes_implantacao_txt}"
            ]
            general_formula = (
                "Sucesso da Implantação = \\frac{Novos_{Clientes}}{Casas_{Implantação}} \\times 100"
            )

        elif kpi_name == 'Roll 6M Growth':
            # --- variáveis ------------------------------------------------
            periodo_base      = variables_values.get('Periodo base', periodo_texto)
            janela_atual_txt  = variables_values.get('Janela atual', '')
            janela_ant_txt    = variables_values.get('Janela anterior', '')

            r6m_atuais_val   = variables_values.get('Receita 6m Atuais', 0)
            r6m_passados_val = variables_values.get('Receita 6m Passados', 0)

            # --- formatação ----------------------------------------------
            r6m_atuais_fmt   = formatar_valor_utils(r6m_atuais_val,   'monetario')
            r6m_passados_fmt = formatar_valor_utils(r6m_passados_val, 'monetario')

            # --- fórmula computada (fração maior com \dfrac) --------------
            computed_formula = (
                f"Roll\\ 6M\\ Growth = "
                f"\\dfrac{{({r6m_atuais_fmt} - {r6m_passados_fmt})}}{{{r6m_passados_fmt}}}"
                f" \\times 100 \\;=\\; {resultado_latex}"
            )

            # --- itens para o modal --------------------------------------
            itens = [
                f"**Período:** {periodo_base}",
                f"**Janela Últimos 6 meses (atual):** {janela_atual_txt}",
                f"**Janela 6 meses anteriores:** {janela_ant_txt}",
                f"**Receita Acumulada (últimos 6 meses):** {r6m_atuais_fmt}",
                f"**Receita Acumulada (6 meses anteriores):** {r6m_passados_fmt}",
            ]

            # --- fórmula genérica ----------------------------------------
            general_formula = (
                "Roll\\ 6M\\ Growth = "
                "\\Bigl(\\dfrac{\\text{Receita}_{6m\\,Atuais} - "
                "\\text{Receita}_{6m\\,Passados}}{\\text{Receita}_{6m\\,Passados}}\\Bigr) "
                "\\times 100"
            )
        
        elif kpi_name == 'Score Médio do Show':
            soma_avaliacoes   = variables_values.get('Soma das Avaliações', 0)
            total_avaliados   = variables_values.get('Total de Shows Avaliados', 0)
            score_medio       = variables_values.get('Score Médio', 0)

            soma_fmt   = formatar_valor_utils(soma_avaliacoes, 'numero')
            total_fmt  = formatar_valor_utils(total_avaliados, 'numero')
            media_fmt  = formatar_valor_utils(score_medio, 'numero')

            # Fórmula simplificada
            computed_formula = (
                f"Score\\text{{ }}Medio = \\frac{{{soma_fmt}}}{{{total_fmt}}} = {media_fmt}"
            )
            
            itens = [
                f"**Período Analisado:** {periodo_texto}",
                f"**Total de Shows Avaliados:** {total_fmt}",
                f"**Soma das Avaliações:** {soma_fmt}",
                f"**Score Médio:** {media_fmt}"
            ]
            
            # Fórmula genérica ajustada para evitar sobreposição
            general_formula = (
                "Score\\text{ }Medio = \\frac{\\text{Soma das Avaliacoes}}{\\text{Total de Shows Avaliados}}"
            )            
        
        elif kpi_name in ("Eficiência Comercial", "LTV/CAC", "LTVCAC"):
            # ---------- valores que a função já devolve ----------
            ltv_val          = variables_values.get('LTV', 0)
            cac_val          = variables_values.get('CAC Por Cliente', 0)
            ratio_val        = variables_values.get('LTV/CAC', 0)
            novos_val        = variables_values.get('Novos Palcos', 0)
            churn_val        = variables_values.get('Churn', 0)
            life_val         = variables_values.get('Lifetime Médio Ajustado (meses)', 0)
            fat_mensal_val   = variables_values.get('Faturamento Médio Mensal', 0)
            cac_total_val    = variables_values.get('CAC Total Acumulado', 0)

            # ---------- formatação friendly ----------
            ltv_txt        = formatar_valor_utils(ltv_val, 'monetario')
            cac_txt        = formatar_valor_utils(cac_val, 'monetario')
            cac_total_txt  = formatar_valor_utils(cac_total_val, 'monetario') if cac_total_val > 0 else "N/A"
            ratio_txt      = formatar_valor_utils(ratio_val, 'numero_2f')
            novos_txt      = formatar_valor_utils(novos_val, 'numero')
            churn_txt      = formatar_valor_utils(churn_val, 'numero')
            life_txt       = f"{formatar_valor_utils(life_val, 'numero_2f')} meses"
            fat_mensal_txt = formatar_valor_utils(fat_mensal_val, 'monetario')

            # ---------- Descrição simplificada ----------
            description = rf"""
### LTV/CAC — {periodo_texto}

LTV/CAC é um indicador essencial que compara o valor que um cliente gera durante seu ciclo de vida (LTV) com o custo para adquiri-lo (CAC). Neste período, analisamos os **{novos_txt} novos palcos** adquiridos.
"""

            # ---------- campos que o resto da função espera ----------
            general_formula = r"LTV/CAC = \frac{LTV}{CAC} \quad \text{onde} \quad LTV = \text{Faturamento Medio Mensal} \times \text{Lifetime Medio}"
            
            computed_formula = rf"LTV/CAC = \dfrac{{{ltv_txt}}}{{{cac_txt}}} = {ratio_txt}"
            
            # Explicação das variáveis - mais detalhadas
            variaveis_explicadas = (
                "- **LTV (Lifetime Value):** Valor total projetado que um palco gera durante todo seu ciclo de vida\n"
                "- **Faturamento Médio Mensal:** Receita média que cada palco gera por mês\n"
                "- **Lifetime Médio Ajustado:** Tempo estimado que o palco permanecerá ativo, ajustado com dados históricos\n"
                "- **CAC (Customer Acquisition Cost):** Investimento médio necessário para adquirir cada novo palco\n"
                "- **Churn:** Quantidade de palcos que deixaram de ser ativos durante o período"
            )
            
            # Override description para eliminar repetições
            markdown_content = f"""

LTV/CAC é um indicador essencial que compara o valor que um cliente gera durante seu ciclo de vida (LTV) com o custo para adquiri-lo (CAC).

**Área Responsável:** {responsible_area}

## Como o LTV/CAC é calculado?

$$
LTV/CAC = \\frac{{LTV}}{{CAC}} \\quad \\text{{onde}} \\quad LTV = \\text{{Faturamento Medio Mensal}} \\times \\text{{Lifetime Medio}}
$$

## **Onde:**
{variaveis_explicadas}

## Aplicando LTV/CAC para a Eshows

## **Temos:**
- **Período:** {periodo_texto}
- **Novos palcos:** {novos_txt}
- **Faturamento médio mensal:** {fat_mensal_txt}
- **Lifetime médio ajustado:** {life_txt}
- **LTV médio:** {ltv_txt}
- **CAC por cliente:** {cac_txt}
- **Resultado (LTV/CAC):** **{ratio_txt}**

## **Passo a Passo do Cálculo:**

1. **Calculamos o LTV** de cada palco:
   
   $$
   LTV = \\text{{Faturamento Medio Mensal}} \\times \\text{{Lifetime Medio Ajustado}}
   $$
   
   $$
   LTV = {fat_mensal_txt} \\times {life_txt} = {ltv_txt}
   $$

2. **Calculamos a relação LTV/CAC**:
   
   $$
   LTV/CAC = \\frac{{{ltv_txt}}}{{{cac_txt}}} = {ratio_txt}
   $$

## **O que isso significa?**

> **Cada R$ 1.00 investido em aquisição de cliente retorna R$ {ratio_txt} em valor projetado ao longo do ciclo de vida do cliente.**
>
> Do total de {novos_txt} novos palcos adquiridos no período, {churn_txt} apresentaram churn.
"""
            
            # Usado para sobrescrever o padrão
            return markdown_content

        elif kpi_name in ("Churn $", "Churn em Valor", "Churn Valor"):
            # ---------- valores que a função já devolve ----------
            valor_perdido_val = variables_values.get('Churn em Valor (R$)', 0)
            faturamento_val   = variables_values.get('Faturamento no Período', 0)
            churn_pct_val     = variables_values.get('Churn em Valor (%)', 0)
            perdidos_ct_val   = variables_values.get('Estabelecimentos Perdidos', 0)
            # ---------- formatação friendly ----------
            valor_perdido_txt = formatar_valor_utils(valor_perdido_val, 'monetario')
            faturamento_txt   = formatar_valor_utils(faturamento_val, 'monetario')
            churn_pct_txt     = formatar_valor_utils(churn_pct_val, 'numero') + '%'
            perdidos_ct_txt   = formatar_valor_utils(perdidos_ct_val, 'numero')
            
            # Remover o R$ para o LaTeX
            valor_perdido_latex = valor_perdido_txt.replace('R$', '\\text{R\\$}')
            faturamento_latex = faturamento_txt.replace('R$', '\\text{R\\$}')
            
            # ---------- Descrição simplificada ----------
            description = rf"""
### Churn em Valor — {periodo_texto}
Churn em Valor (%) mostra quanta receita mensal recorrente a Eshows perdeu porque algumas casas deixaram de realizar shows no período.
"""
            # ---------- campos que o resto da função espera ----------
            general_formula = (
                r"Churn\% = "
                r"\frac{\text{Valor perdido no periodo}}{\text{Faturamento no periodo}} \times 100"
            )
            # Explicação das variáveis
            variaveis_explicadas = (
                "- **Valor perdido no período:** Soma das médias mensais de faturamento das casas que churnaram\n"
                "- **Faturamento no período:** Receita total gerada por todas as casas no mesmo intervalo\n"
                "- **Estabelecimentos Perdidos:** Número de casas que deixaram de fazer shows"
            )
            # Override description para eliminar repetições
            markdown_content = f"""
Churn em Valor (%) indica quanto da receita mensal recorrente foi perdida no período porque certos clientes deixaram de fazer shows.

**Área Responsável:** {responsible_area}

## Como o Churn em Valor é calculado?

$$
{general_formula}
$$

## **Onde:**

{variaveis_explicadas}

## Aplicando o Churn em Valor à Eshows

## **Temos:**

- **Período:** {periodo_texto}
- **Casas churnadas:** {perdidos_ct_txt}
- **Valor perdido no período:** {valor_perdido_txt}
- **Faturamento no período:** {faturamento_txt}
- **Churn em Valor (%):** **{churn_pct_txt}**

## **Passo a Passo do Cálculo:**

1. **Calculamos o valor perdido** somando a média mensal de faturamento das casas churnadas:
   
   $$
   \\text{{Valor perdido no periodo}} = {valor_perdido_latex}
   $$

2. **Dividimos pelo faturamento total do período**:
   
   $$
   Churn\\% = \\frac{{{valor_perdido_latex}}}{{{faturamento_latex}}} = {churn_pct_txt}
   $$

## **O que isso significa?**

> Durante **{periodo_texto}**, a Eshows perdeu **{churn_pct_txt}** de sua receita mensal recorrente.
"""
            
            # Usado para sobrescrever o padrão
            return markdown_content
        
        elif kpi_name in ("Receita por Pessoal", "Receita/Pessoal", "ReceitaPessoal"):
            # ---------- valores que a função já devolve ----------
            faturamento_val = variables_values.get('Faturamento no Período', 0)
            custo_val       = variables_values.get('Custo Equipe no Período', 0)
            ratio_val       = variables_values.get('Receita por Pessoal', 0)

            # ---------- formatação friendly ----------
            faturamento_txt = formatar_valor_utils(faturamento_val, 'monetario')
            custo_txt       = formatar_valor_utils(custo_val, 'monetario')
            ratio_txt       = formatar_valor_utils(ratio_val, 'numero_2f')

            # Remover o R$ para o LaTeX
            faturamento_latex = faturamento_txt.replace('R$', '\\text{R\\$}')
            custo_latex       = custo_txt.replace('R$', '\\text{R\\$}')

            # ---------- Descrição simplificada ----------
            description = rf"""
### Receita por Pessoal — {periodo_texto}
Este KPI mostra quantas vezes a receita cobre o custo total da equipe interna no período analisado.
"""

            # ---------- campos que o resto da função espera ----------
            general_formula = (
                r"\text{Receita por Pessoal} = "
                r"\frac{\text{Faturamento no periodo}}{\text{Custo Equipe no periodo}}"
            )

            # Explicação das variáveis
            variaveis_explicadas = (
                "- **Faturamento no período:** Receita total gerada por todas as casas no intervalo\n"
                "- **Custo Equipe no período:** Despesas totais com pessoal (coluna *Equipe* da Base2)\n"
                "- **Receita por Pessoal:** Quantas vezes a receita cobre o custo de pessoal"
            )

            # Override description para eliminar repetições
            markdown_content = f"""
{description}

**Área Responsável:** {responsible_area}

## Como a Receita por Pessoal é calculada?

$$
{general_formula}
$$

## **Onde:**

{variaveis_explicadas}

## Aplicando à Eshows

## **Temos:**

- **Período:** {periodo_texto}
- **Faturamento no período:** {faturamento_txt}
- **Custo da equipe no período:** {custo_txt}
- **Receita por Pessoal:** **{ratio_txt}**

## **Passo a Passo do Cálculo:**

1. **Faturamento total** no período:

   $$
   \\text{{Faturamento}} = {faturamento_latex}
   $$

2. **Custo total da equipe** no mesmo período:

   $$
   \\text{{Custo Equipe}} = {custo_latex}
   $$

3. **Receita por Pessoal**:

   $$
   \\text{{Receita por Pessoal}} = \\frac{{{faturamento_latex}}}{{{custo_latex}}} = {ratio_txt}
   $$

## **O que isso significa?**

> Cada real investido em equipe interna gerou **{ratio_txt}** reais de receita no período **{periodo_texto}**.
"""
            
            # Usado para sobrescrever o padrão
            return markdown_content

        elif kpi_name == "CSAT Artistas":
            csat_val = variables_values.get("CSAT Artistas", 0.0)
            csat_fmt = f"{csat_val:.2f}☆"

            computed_formula = (
                f"CSAT_{{Artistas}} = \\frac{{\\sum \\text{{Notas}}}}{{n_{{respostas}}}} = {csat_fmt}"
            )
            itens = [
                f"Período: {periodo_texto}",
                f"CSAT Médio (1-5): {csat_fmt}"
            ]
            general_formula = (
                "CSAT_{Artistas} = \\frac{\\sum \\text{pontuacoes}}{n_{respostas}}"
            )
            variaveis_explicadas = (
                "- **Notas CSAT:** Soma das respostas dos artistas para a satisfação com os shows (escala de 1 a 5 estrelas)\n"
                "- **Quantidade de Respostas:** Total de avaliações recebidas no período"
            )

        elif kpi_name == "CSAT Operação":
            csat_val = variables_values.get("CSAT Operação", 0.0)
            total_avaliacoes = variables_values.get("Total Avaliações", 0)
            csat_fmt = f"{csat_val:.2f}☆"

            computed_formula = (
                f"CSAT_{{Operacao}} = \\frac{{\\sum \\text{{Notas validas}}}}{{n_{{respostas validas}}}} = {csat_fmt}"
            )
            itens = [
                f"Período: {periodo_texto}",
                f"CSAT Médio (1-5): {csat_fmt}",
                f"Total de avaliações válidas: {total_avaliacoes}"
            ]
            detalhes_reais = '\n'.join([f'- {item}' for item in itens])
            general_formula = (
                "CSAT_{Operacao} = \\frac{\\sum \\text{pontuacoes validas}}{n_{respostas validas}}"
            )
            variaveis_explicadas = (
                "- **Notas CSAT dos Operadores:** Soma das respostas dos artistas para o atendimento dos operadores (escala de 1 a 5 estrelas)\n"
                "- **Quantidade de Respostas Válidas:** Total de avaliações consideradas para o cálculo no período"
            )
            description = (
                "O CSAT Operação mede o grau de satisfação dos artistas com o atendimento prestado pelos operadores da Eshows. "       
                "A nota é dada em uma escala de 1 a 5 estrelas, onde valores mais altos indicam melhor experiência de atendimento."
            )
            markdown_content = f"""
{description}

**Área Responsável:** Operações

## Como o CSAT Operação é calculado?

$$
{general_formula}
$$

### Onde:
{variaveis_explicadas}

## Aplicando CSAT Operação para a Eshows no Período

### Temos:
{detalhes_reais}

$$
{computed_formula}
$$
"""
            final_markdown = "\n".join(line.lstrip() for line in textwrap.dedent(markdown_content).splitlines())
            return final_markdown

        else:
            print(f"DEBUG: KPI '{kpi_name}' caiu no bloco ELSE (não mapeado explicitamente ou nome incorreto)") # DEBUG
            computed_formula = "Fórmula específica não disponível."
            # ... (lógica do else) ...
            itens = [
                f"**Período:** {periodo_texto}",
                "Não há detalhes adicionais para este KPI."
            ]
            general_formula = formula
            variaveis_explicadas = "\n".join([f"- **{var}:** {desc}" for var, desc in variables.items()])

        # Monta a listagem final de variáveis descritas no JSON (se houver)
        if not variaveis_explicadas and variables:
             variaveis_explicadas = "\n".join([f"- **{var}:** {desc}" for var, desc in variables.items()])

        # Monta os itens (valores calculados)
        detalhes_reais = "\n".join([f"- {item}" for item in itens])

        # Integra TUDO num Markdown final
        markdown_content = f"""
{description}

**Área Responsável:** {responsible_area}

## Como {kpi_name} é calculado?

$$
{general_formula}
$$

### Onde:
{variaveis_explicadas if variaveis_explicadas else "Variáveis não especificadas."}

## Aplicando {kpi_name} para a Eshows no Período

### Temos:
{detalhes_reais}

$$
{computed_formula}
$$

"""
        # Ajuste final: remover indent excessivo e retorna
        final_markdown = "\n".join(line.lstrip() for line in textwrap.dedent(markdown_content).splitlines())
        
        # --- DEBUG START ---
        print(f"DEBUG: Conteúdo Markdown Final (primeiros 200 chars): {final_markdown[:200]}...") # DEBUG
        print("="*30 + " FIM DEBUG " + "="*30 + "\n")
        # --- DEBUG END ---
        
        return final_markdown

    ########################################
    # CALLBACK DE GERAÇÃO DA INTERPRETAÇÃO
    ########################################
    @app.callback(
        [Output('ia-interpretations','data'),
        Output('interpretation-content','children')],
        [
            Input('kpi-selected-data','data'),
            Input('strategy-info','data'),
            Input('painel-indicators-store','data'),
            Input('all-indicators-store','data'),
            Input('kpi-painel-modal','is_open')
        ],
        [State('ia-interpretations','data')],
        prevent_initial_call=True
    )
    def generate_interpretation(kpi_data, strategy_info, painel_data, dashboard_data, modal_is_open, ia_data):
        print("Dashboard_data recebido:", dashboard_data)  # Debug: ver o conteúdo do store
        if not modal_is_open or not kpi_data or 'kpi_name' not in kpi_data:
            raise dash.exceptions.PreventUpdate
        if ia_data is None:
            ia_data = {}
        kpi_name = kpi_data['kpi_name']
        if kpi_name in ia_data and ia_data[kpi_name]:
            return ia_data, ia_data[kpi_name]
        if painel_data is None:
            painel_data = {}
        if dashboard_data is None:
            dashboard_data = {}
        all_indicators_merged = {**painel_data, **dashboard_data}
        interpretation = interpreter.generate_kpi_interpretation_claude(
            kpi_name=kpi_name,
            kpi_values=kpi_data,
            strategy_info=strategy_info,
            all_indicators=all_indicators_merged
        )
        ia_data[kpi_name] = interpretation
        return ia_data, interpretation
        
    # Callback do Dash para atualizar o termômetro
    @app.callback(
        [Output('thermometer-graph', 'figure'),
        Output('status-icon', 'src'),
        Output('status-text', 'children'),
        Output('status-box', 'style')],
        [Input('kpi-selected-data', 'data')]
    )
    def update_thermometer(kpi_data):
        if not kpi_data or 'kpi_name' not in kpi_data:
            raise dash.exceptions.PreventUpdate

        kpi_name = kpi_data.get('kpi_name')
        resultado_str = kpi_data.get('resultado', '0')
        resultado_num = parse_valor_formatado(resultado_str)

        status, icon_filename = get_kpi_status(kpi_name, resultado_num, kpi_descriptions)
        if status is None:
            status = 'indefinido'
        fig = create_enhanced_thermometer(kpi_name, resultado_num)

        status_color = colors[status]['color']
        r, g, b = [int(status_color.strip('#')[i:i+2], 16) for i in (0, 2, 4)]
        pastel_bg = f"rgba({r},{g},{b},0.1)"

        status_box_style = {
            "backgroundColor": pastel_bg,
            "color": status_color,
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "flex-start",
            "height": "32px",
            "borderRadius": "4px",
            "padding": "0 8px"
        }

        if status == 'controle':
            status_box_style["color"] = "#C89B00"

        return fig, f"/assets/{icon_filename}", status.capitalize(), status_box_style



