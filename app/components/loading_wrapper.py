"""
Loading wrapper para callbacks do Dash
Adiciona indicadores de loading automaticamente durante processamento
"""

from dash import html, dcc, Output, Input, State, clientside_callback, ClientsideFunction
import functools


def with_loading(callback_func):
    """
    Decorator que adiciona loading automático para callbacks pesados
    
    Uso:
        @app.callback(...)
        @with_loading
        def meu_callback(...):
            # processamento pesado
            return resultado
    """
    @functools.wraps(callback_func)
    def wrapper(*args, **kwargs):
        # Callback original continua funcionando normalmente
        return callback_func(*args, **kwargs)
    
    # Marca a função para que possamos identificá-la depois
    wrapper._has_loading = True
    return wrapper


def create_loading_wrapper(component_id, children, loading_type="default"):
    """
    Cria um wrapper com loading para um componente específico
    
    Args:
        component_id: ID único do componente
        children: Conteúdo a ser exibido
        loading_type: Tipo de loading ("default", "skeleton", "overlay")
    """
    if loading_type == "skeleton":
        return html.Div([
            dcc.Loading(
                id=f"loading-{component_id}",
                children=children,
                type="none",  # Desabilita o loading padrão do Dash
                custom_spinner=html.Div(
                    className="skeleton-wrapper",
                    children=[
                        html.Div(className="skeleton-line skeleton-title shimmer"),
                        html.Div(className="skeleton-line skeleton-value shimmer"),
                        html.Div(className="skeleton-line skeleton-description shimmer"),
                    ]
                )
            )
        ], id=f"wrapper-{component_id}")
    
    elif loading_type == "overlay":
        return html.Div([
            children,
            html.Div(
                id=f"loading-overlay-{component_id}",
                className="component-loading-overlay",
                style={"display": "none"},
                children=[
                    html.Div(className="loading-spinner"),
                    html.Div("Carregando...", className="loading-text-small")
                ]
            )
        ], id=f"wrapper-{component_id}", style={"position": "relative"})
    
    else:  # default
        return dcc.Loading(
            id=f"loading-{component_id}",
            children=children,
            type="circle",
            color="#E84D29"
        )


def create_loading_callbacks(app):
    """
    Cria callbacks clientside para gerenciar loading states
    """
    
    # Callback para mostrar loading quando inputs mudam
    app.clientside_callback(
        """
        function(ano, periodo, mes) {
            // Mostra loading quando qualquer input muda
            if (window.loadingManager) {
                window.loadingManager.show('main-loading');
                
                // Mostra skeletons nos cards de KPI
                const kpiCards = document.querySelectorAll('[id$="-col"]');
                kpiCards.forEach(card => {
                    if (!card.dataset.originalContent) {
                        card.dataset.originalContent = card.innerHTML;
                        card.innerHTML = window.loadingManager.createKPISkeleton();
                    }
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("loading-trigger", "data"),
        [
            Input("dashboard-ano-dropdown", "value"),
            Input("dashboard-periodo-dropdown", "value"),
            Input("dashboard-mes-dropdown", "value")
        ],
        prevent_initial_call=True
    )
    
    # Callback para esconder loading quando KPIs são atualizados
    app.clientside_callback(
        """
        function(kpi1) {
            // Esconde loading quando o primeiro KPI é atualizado
            if (window.loadingManager && kpi1) {
                setTimeout(() => {
                    window.loadingManager.hide('main-loading');
                    
                    // Restaura conteúdo dos cards
                    const kpiCards = document.querySelectorAll('[id$="-col"]');
                    kpiCards.forEach(card => {
                        if (card.dataset.originalContent) {
                            card.innerHTML = card.dataset.originalContent;
                            delete card.dataset.originalContent;
                        }
                    });
                }, 300);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("loading-complete", "data"),
        Input("kpi-gmv-col", "children"),
        prevent_initial_call=True
    )


def add_loading_trigger_to_layout(layout):
    """
    Adiciona os componentes necessários para o loading funcionar
    """
    return html.Div([
        layout,
        dcc.Store(id="loading-trigger"),
        dcc.Store(id="loading-complete")
    ])