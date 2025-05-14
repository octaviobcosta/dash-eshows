# =============================================================================
#  MÓDULO: financeiro.py  |  Página /financeiro
# =============================================================================
#  • Layout e callbacks iniciais para a DRE com design custom
#  • Requisitos: Dash ≥ 2.10  e dash-bootstrap-components
# =============================================================================

from dash import html, dcc, Input, Output, dash_table
import dash_bootstrap_components as dbc
from dash.dash_table import FormatTemplate

# -----------------------------------------------------------------------------#
# 1) Helpers de dropdowns
# -----------------------------------------------------------------------------#
def _periodo_dropdown(id_suffix: str):
    return dcc.Dropdown(
        id=f"financeiro-periodo-dropdown-{id_suffix}",
        options=[
            {"label": "Year To Date", "value": "YTD"},
            {"label": "1° Trimestre", "value": "1Q"},
            {"label": "2° Trimestre", "value": "2Q"},
            {"label": "3° Trimestre", "value": "3Q"},
            {"label": "4° Trimestre", "value": "4Q"},
            {"label": "Ano Completo", "value": "FY"},
        ],
        value="YTD",
        clearable=False,
        style={"borderRadius": "4px", "border": "1px solid #D1D1D1"},
    )


def _ano_dropdown(id_suffix: str):
    return dcc.Dropdown(
        id=f"financeiro-ano-dropdown-{id_suffix}",
        options=[{"label": str(y), "value": y} for y in range(2025, 2019, -1)],
        value=2025,
        clearable=False,
        style={"borderRadius": "4px", "border": "1px solid #D1D1D1"},
    )

# -----------------------------------------------------------------------------#
# 2) Tabela DRE com design custom
# -----------------------------------------------------------------------------#
numeric_cols = ["ytd_atual", "ytd_ant", "jan", "fev", "mar", "q1"]

dre_table = dash_table.DataTable(
    id="dre-table",
    columns=[
        {"name": "Conta",      "id": "conta", "presentation": "markdown", "editable": False},
        {"name": "YTD Abr/25", "id": "ytd_atual", "type": "numeric",
         "format": FormatTemplate.money(0), "editable": False},
        {"name": "YTD Abr/24", "id": "ytd_ant", "type": "numeric",
         "format": FormatTemplate.money(0), "editable": False},
        {"name": "Jan-24", "id": "jan", "type": "numeric",
         "format": FormatTemplate.money(0), "editable": False},
        {"name": "Fev-24", "id": "fev", "type": "numeric",
         "format": FormatTemplate.money(0), "editable": False},
        {"name": "Mar-24", "id": "mar", "type": "numeric",
         "format": FormatTemplate.money(0), "editable": False},
        {"name": "1Q", "id": "q1", "type": "numeric",
         "format": FormatTemplate.money(0), "editable": False},
    ],
    data=[],  # alimentado via callback
    style_cell={
        "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "padding": "12px 16px",
        "border": "none",
        "fontSize": "14px",
        "textAlign": "left",
        "backgroundColor": "#FFFFFF",
        "color": "#1F2937",
        "whiteSpace": "normal",
        "height": "auto",
        "minWidth": "120px",
        "width": "120px",
        "maxWidth": "180px",
    },
    style_cell_conditional=[
        {"if": {"column_id": "conta"},
         "textAlign": "left",
         "width": "200px", "minWidth": "180px", "maxWidth": "220px",
         "paddingLeft": "20px",
         "fontWeight": "500",
         "color": "#111827"},
        {"if": {"column_id": numeric_cols},
         "textAlign": "right",
         "paddingRight": "20px",
         "fontFamily": "SF Mono, Monaco, Consolas, 'Courier New', monospace",
         "fontSize": "14px"},
        {"if": {"column_id": "ytd_atual"},
         "fontWeight": "600",
         "color": "#059669",
         "backgroundColor": "#F0FDF4"},
    ],
    style_header={
        "backgroundColor": "#F9FAFB",
        "fontWeight": "600",
        "color": "#374151",
        "border": "none",
        "borderBottom": "2px solid #E5E7EB",
        "fontSize": "13px",
        "textAlign": "left",
        "padding": "16px",
        "textTransform": "uppercase",
        "letterSpacing": "0.05em",
    },
    style_header_conditional=[
        {"if": {"column_id": numeric_cols}, "textAlign": "right"},
        {"if": {"column_id": "ytd_atual"}, "color": "#059669", "fontWeight": "700"},
    ],
    style_data_conditional=[
        {"if": {"row_index": "odd"}, "backgroundColor": "#FCFCFC"},
        {"if": {"filter_query": "{conta} contains '**'"},
         "fontWeight": "700", "backgroundColor": "#F3F4F6",
         "borderTop": "1px solid #E5E7EB", "borderBottom": "1px solid #E5E7EB",
         "fontSize": "15px", "color": "#1F2937"},
        {"if": {"filter_query": "{conta} = '**EBITDA**'"},
         "backgroundColor": "#EBF5FF", "color": "#1E40AF",
         "borderTop": "2px solid #3B82F6", "borderBottom": "1px solid #93C5FD"},
        {"if": {"filter_query": "{conta} = 'Lucro Líquido'"},
         "backgroundColor": "#F0FDF4", "color": "#059669",
         "borderBottom": "2px solid #10B981", "fontWeight": "600"},
        {"if": {"filter_query": "{conta} contains 'Margem'"},
         "fontStyle": "italic", "color": "#6B7280", "fontSize": "13px"},
        # valores negativos (regra por coluna)
        *[
            {
                "if": {"filter_query": f"{{{col}}} < 0", "column_id": col},
                "color": "#DC2626", "fontWeight": "500",
            } for col in numeric_cols
        ],
        {"if": {"state": "active"},
         "backgroundColor": "#F3F4F6", "border": "1px solid #93C5FD"},
    ],
    style_table={
        "borderRadius": "12px",
        "overflow": "hidden",
        "boxShadow": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        "border": "1px solid #E5E7EB",
    },
    page_size=20,
    sort_action="native",
    filter_action="native",
    merge_duplicate_headers=True,
)

dre_table_styled = dbc.Card(
    dbc.CardBody(
        [
            dre_table,
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(style={
                                "width": "12px", "height": "12px", "borderRadius": "2px",
                                "backgroundColor": "#059669", "display": "inline-block",
                                "marginRight": "8px"}),
                            html.Span("Valores positivos",
                                      style={"fontSize": "12px", "color": "#6B7280", "marginRight": "24px"}),
                        ],
                        style={"display": "inline-flex", "alignItems": "center"},
                    ),
                    html.Div(
                        [
                            html.Div(style={
                                "width": "12px", "height": "12px", "borderRadius": "2px",
                                "backgroundColor": "#DC2626", "display": "inline-block",
                                "marginRight": "8px"}),
                            html.Span("Valores negativos",
                                      style={"fontSize": "12px", "color": "#6B7280"}),
                        ],
                        style={"display": "inline-flex", "alignItems": "center"},
                    ),
                ],
                style={"marginTop": "16px", "display": "flex", "gap": "24px",
                       "justifyContent": "flex-start", "paddingLeft": "16px"},
            ),
        ],
        style={"padding": "0"},
    ),
    style={"border": "none", "borderRadius": "12px", "backgroundColor": "transparent", "boxShadow": "none"},
)

# -----------------------------------------------------------------------------#
# 3) Layout principal da página
# -----------------------------------------------------------------------------#
financeiro_layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Financeiro – DRE",
                        style={"fontFamily": "Inter", "fontWeight": 700,
                               "fontSize": "48px", "color": "#4A4A4A"}),
                className="mb-4",
            )
        ),
        dbc.Row(
            [
                dbc.Col([html.Label("Ano:"), _ano_dropdown("main")],
                        xs=4, sm=2, md=1, lg=1),
                dbc.Col([html.Label("Período:"), _periodo_dropdown("main")],
                        xs=8, sm=4, md=2, lg=2),
                dbc.Col([html.Label("Mês:"),
                         dcc.Dropdown(id="financeiro-mes-dropdown-main", clearable=False)],
                        xs=8, sm=4, md=2, lg=2),
            ],
            className="g-2 mb-3",
        ),
        dre_table_styled,
        html.Br(),
        html.P("Versão de rascunho – valores simulados.",
               style={"fontStyle": "italic", "fontSize": "0.9rem", "color": "#6B7280"}),
    ],
    fluid=True,
    style={"padding": "1rem"},
)

# -----------------------------------------------------------------------------#
# 4) Callbacks iniciais (mock)
# -----------------------------------------------------------------------------#
def register_financeiro_callbacks(app):
    @app.callback(
        Output("financeiro-mes-dropdown-main", "options"),
        Input("financeiro-periodo-dropdown-main", "value"),
        prevent_initial_call=True,
    )
    def _toggle_mes_dropdown(periodo):
        if periodo == "Mês Aberto":
            meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                     "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            return [{"label": m, "value": i} for i, m in enumerate(meses, 1)]
        return []

    @app.callback(
        Output("dre-table", "data"),
        [Input("financeiro-ano-dropdown-main", "value"),
         Input("financeiro-periodo-dropdown-main", "value"),
         Input("financeiro-mes-dropdown-main", "value")],
        prevent_initial_call=True,
    )
    def _preencher_tabela(ano, periodo, mes):
        contas = [
            "**Receita Total**",
            "Operacional", "Comissão", "SaaS", "Adiantamentos", "Não Operacional",
            "**Custo Total**",
            "Operacional", "Equipe", "Terceiros", "Op. Shows",
            "**EBITDA**", "Margem EBITDA",
            "Lucro Líquido", "Margem Lucro Líquido",
        ]
        linha = {col: 0 for col in numeric_cols}
        return [{"conta": c, **linha} for c in contas]

# -----------------------------------------------------------------------------#
# 5) Teste standalone
# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    app.layout = financeiro_layout
    register_financeiro_callbacks(app)
    app.run_server(debug=True, port=8051)
