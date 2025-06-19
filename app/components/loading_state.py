"""
Componente de Loading State temático para o Dashboard eShows
Transforma o tempo de espera em uma experiência relacionada à preparação de shows
"""

from dash import html, dcc, callback, Output, Input, MATCH
import random

# Frases temáticas sobre preparação de shows
LOADING_PHRASES = [
    "🎸 Afinando os instrumentos...",
    "🎤 Testando o som...",
    "🎵 Organizando o setlist...",
    "🎪 Montando o palco...",
    "✨ Ajustando as luzes...",
    "📊 Calculando as métricas do show...",
    "🎫 Conferindo os ingressos...",
    "🎶 O show já vai começar!",
    "🌟 Preparando uma performance incrível...",
    "🎭 Aquecendo para o grande espetáculo...",
    "📈 Analisando o público...",
    "🎯 Sincronizando os dados do evento...",
    "🔊 Equalizando o áudio...",
    "🎨 Preparando o visual...",
    "📋 Verificando o rider técnico...",
    "🎼 Ensaiando os últimos detalhes...",
    "🚀 Quase tudo pronto para o show!",
    "💫 Criando a magia do espetáculo..."
]


def create_loading_overlay(loading_id="main-loading", custom_text=None):
    """
    Cria um overlay de loading com o logo da eShows animado e frases temáticas
    
    Args:
        loading_id: ID único para o componente
        custom_text: Texto customizado (opcional)
    """
    return html.Div([
        html.Div([
            # Logo animado
            html.Div([
                html.Img(
                    src="/assets/iconeshows.png",
                    className="loading-logo pulse-rotate",
                    alt="eShows"
                )
            ], className="loading-logo-container"),
            
            # Texto de loading
            html.Div(
                custom_text or random.choice(LOADING_PHRASES),
                id=f"{loading_id}-text",
                className="loading-text fade-in-out"
            ),
            
            # Barra de progresso estilizada como onda sonora
            html.Div([
                html.Div(className="sound-bar", style={"animation-delay": "0s"}),
                html.Div(className="sound-bar", style={"animation-delay": "0.1s"}),
                html.Div(className="sound-bar", style={"animation-delay": "0.2s"}),
                html.Div(className="sound-bar", style={"animation-delay": "0.3s"}),
                html.Div(className="sound-bar", style={"animation-delay": "0.4s"}),
            ], className="sound-wave-loader")
        ], className="loading-content")
    ], id=loading_id, className="loading-overlay", style={"display": "none"})


def create_skeleton_kpi_card():
    """
    Cria um card skeleton para KPIs com shimmer effect
    """
    return html.Div([
        html.Div([
            # Título skeleton
            html.Div(className="skeleton-line skeleton-title"),
            # Valor skeleton
            html.Div(className="skeleton-line skeleton-value"),
            # Descrição skeleton
            html.Div(className="skeleton-line skeleton-description"),
        ], className="skeleton-content shimmer")
    ], className="skeleton-kpi-card")


def create_skeleton_chart():
    """
    Cria um skeleton para gráficos
    """
    return html.Div([
        # Título do gráfico
        html.Div(className="skeleton-line skeleton-chart-title"),
        # Área do gráfico
        html.Div([
            html.Div(className="skeleton-chart-bars"),
        ], className="skeleton-chart-area shimmer")
    ], className="skeleton-chart")


def create_dash_loading_component(children, component_id, custom_loading=True):
    """
    Wrapper para dcc.Loading com nosso loading customizado
    
    Args:
        children: Conteúdo a ser carregado
        component_id: ID do componente
        custom_loading: Se True, usa nosso loading customizado
    """
    if custom_loading:
        return html.Div([
            dcc.Loading(
                id=f"loading-{component_id}",
                children=children,
                type="none",  # Desabilita o loading padrão
                className="custom-loading-wrapper"
            ),
            create_loading_overlay(f"loading-overlay-{component_id}")
        ])
    else:
        return dcc.Loading(
            id=f"loading-{component_id}",
            children=children,
            type="circle"
        )


def register_loading_callbacks(app):
    """
    Registra callbacks para gerenciar o texto rotativo do loading
    """
    @app.callback(
        Output({'type': 'loading-text', 'index': MATCH}, 'children'),
        Input({'type': 'loading-interval', 'index': MATCH}, 'n_intervals'),
        prevent_initial_call=True
    )
    def update_loading_text(n):
        """Atualiza o texto do loading a cada intervalo"""
        if n:
            return random.choice(LOADING_PHRASES)
        return LOADING_PHRASES[0]