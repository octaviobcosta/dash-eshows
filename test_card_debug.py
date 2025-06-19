"""
Script de debug para testar a criação de cards
"""

# Teste simples da função criar_card_kpi_shows
def test_card_creation():
    # Simular um card simples
    from dash import html
    import dash_bootstrap_components as dbc
    
    # Valores de teste
    titulo = "GMV"
    valor = "R$20.6M"
    var_str = "+3.7%"
    periodo_comp = "vs YTD 2024"
    arrow_color = "#198754"
    arrow_icon_class = "fa-solid fa-arrow-trend-up"
    
    # Criar estrutura do card manualmente
    card = dbc.Card(
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.Span(titulo, className="card-kpi-title-text"),
                    html.Img(
                        src="/assets/kpiicon.png",
                        className="card-kpi-icon",
                        alt="Ícone do KPI",
                        height="16px",
                        style={"margin-left": "auto"},
                    ),
                ], className="card-kpi-title", style={
                    "display": "flex",
                    "align-items": "center",
                    "justify-content": "space-between",
                    "margin-bottom": "0.25rem",
                }),
                html.H3(
                    valor,
                    className="card-kpi-value",
                    style={"margin-bottom": "0.25rem"},
                ),
                html.Div([
                    html.Div(style={"flex": "1"}),
                    html.Div([
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
                    ], className="card-kpi-variation"),
                ], style={
                    "display": "flex",
                    "align-items": "center",
                    "margin-bottom": "0.25rem",
                }),
                html.Div(f"vs {periodo_comp}", className="card-kpi-period"),
            ], className="card-kpi-inner")
        ]),
        className="card-kpi h-100",
    )
    
    print("Card structure created successfully")
    print(f"Card type: {type(card)}")
    print(f"Card children: {card.children}")
    
    return card

if __name__ == "__main__":
    test_card_creation()