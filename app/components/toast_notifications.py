"""
Sistema de Notificações Toast Moderno
Implementa notificações elegantes e profissionais para o dashboard
"""

import dash_bootstrap_components as dbc
from dash import html, dcc
import uuid


class ToastNotification:
    """Classe para criar notificações toast profissionais"""
    
    @staticmethod
    def create_toast(message, title=None, variant="success", icon=None, duration=5000, actions=None):
        """
        Cria uma notificação toast
        
        Args:
            message: Mensagem principal
            title: Título opcional
            variant: success, error, warning, info
            icon: Ícone FontAwesome (ex: "fas fa-check")
            duration: Tempo em ms antes de auto-dismiss (0 = manual)
            actions: Lista de botões de ação
        """
        toast_id = f"toast-{uuid.uuid4().hex[:8]}"
        
        # Configurações de estilo por variante
        variants = {
            "success": {
                "bg": "#10b981",
                "icon": "fas fa-check-circle",
                "border": "#059669"
            },
            "error": {
                "bg": "#ef4444", 
                "icon": "fas fa-times-circle",
                "border": "#dc2626"
            },
            "warning": {
                "bg": "#f59e0b",
                "icon": "fas fa-exclamation-triangle", 
                "border": "#d97706"
            },
            "info": {
                "bg": "#3b82f6",
                "icon": "fas fa-info-circle",
                "border": "#2563eb"
            }
        }
        
        config = variants.get(variant, variants["info"])
        final_icon = icon or config["icon"]
        
        # Estrutura do toast
        toast_content = [
            html.Div([
                # Ícone
                html.Div([
                    html.I(className=f"{final_icon} fa-lg", 
                          style={"color": "white"})
                ], className="me-3"),
                
                # Conteúdo
                html.Div([
                    html.Div(title, className="fw-bold mb-1") if title else None,
                    html.Div(message, className="toast-message")
                ], className="flex-grow-1"),
                
                # Botão fechar
                html.Button(
                    html.I(className="fas fa-times"),
                    className="btn-close-toast",
                    id={"type": "close-toast", "index": toast_id},
                    style={
                        "background": "none",
                        "border": "none",
                        "color": "white",
                        "opacity": "0.8",
                        "cursor": "pointer",
                        "padding": "0",
                        "marginLeft": "12px"
                    }
                )
            ], className="d-flex align-items-center")
        ]
        
        # Adiciona ações se fornecidas
        if actions:
            action_buttons = html.Div([
                dbc.Button(
                    action["label"],
                    size="sm",
                    color="light",
                    outline=True,
                    className="me-2 mt-2",
                    id=action.get("id"),
                    style={"border": "1px solid rgba(255,255,255,0.3)"}
                ) for action in actions
            ], className="mt-2")
            toast_content.append(action_buttons)
        
        return html.Div([
            html.Div(
                toast_content,
                id=toast_id,
                className="toast-notification show",
                style={
                    "background": config["bg"],
                    "borderLeft": f"4px solid {config['border']}",
                    "borderRadius": "8px",
                    "padding": "16px 20px",
                    "marginBottom": "12px",
                    "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
                    "color": "white",
                    "minWidth": "320px",
                    "maxWidth": "420px",
                    "animation": "slideInRight 0.3s ease-out",
                    "position": "relative"
                },
                **{"data-duration": duration} if duration > 0 else {}
            )
        ])
    
    @staticmethod
    def create_progress_toast(title, current, total, variant="info"):
        """Cria um toast com barra de progresso"""
        progress = (current / total) * 100 if total > 0 else 0
        
        return ToastNotification.create_toast(
            message=html.Div([
                html.Div(f"Processando {current} de {total} itens"),
                dbc.Progress(
                    value=progress,
                    className="mt-2",
                    style={"height": "4px"},
                    color="light"
                )
            ]),
            title=title,
            variant=variant,
            duration=0  # Não auto-dismiss para progresso
        )


def create_toast_container():
    """Cria o container para as notificações toast"""
    return html.Div(
        id="toast-container",
        style={
            "position": "fixed",
            "top": "20px",
            "right": "20px",
            "zIndex": "9999",
            "pointerEvents": "none"
        },
        children=[]
    )


# CSS para animações
toast_css = """
@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes slideOutRight {
    from {
        transform: translateX(0);
        opacity: 1;
    }
    to {
        transform: translateX(100%);
        opacity: 0;
    }
}

.toast-notification {
    transition: all 0.3s ease;
}

.toast-notification.hide {
    animation: slideOutRight 0.3s ease-out forwards;
}

.btn-close-toast:hover {
    opacity: 1 !important;
    transform: scale(1.1);
}

.toast-container > * {
    pointer-events: auto;
}
"""


def create_update_result_notification(results):
    """
    Cria notificação específica para resultados de atualização
    
    Args:
        results: Dict com resultados da atualização por tabela
    """
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    error_count = sum(1 for r in results.values() if r["status"] == "error")
    total_records = sum(r.get("rows", 0) for r in results.values() if r["status"] == "success")
    
    if error_count == 0:
        # Sucesso total
        return ToastNotification.create_toast(
            title="Atualização Concluída! 🎉",
            message=f"{success_count} tabela(s) atualizada(s) com {total_records:,} registros",
            variant="success",
            icon="fas fa-check-circle",
            actions=[
                {"label": "Ver detalhes", "id": "view-details-btn"}
            ]
        )
    elif success_count > 0:
        # Sucesso parcial
        details = []
        for table, result in results.items():
            if result["status"] == "error":
                details.append(f"❌ {table}: {result.get('error', 'Erro')[:50]}...")
        
        return ToastNotification.create_toast(
            title="Atualização Parcial",
            message=html.Div([
                html.P(f"✅ {success_count} sucesso(s), ❌ {error_count} erro(s)"),
                html.Small("\n".join(details), className="d-block mt-2")
            ]),
            variant="warning",
            icon="fas fa-exclamation-triangle",
            duration=10000,  # Mais tempo para ler
            actions=[
                {"label": "Ver logs", "id": "view-logs-btn"},
                {"label": "Tentar novamente", "id": "retry-failed-btn"}
            ]
        )
    else:
        # Falha total
        return ToastNotification.create_toast(
            title="Falha na Atualização",
            message=f"Não foi possível atualizar {error_count} tabela(s)",
            variant="error",
            icon="fas fa-times-circle",
            duration=0,  # Não auto-dismiss em erros
            actions=[
                {"label": "Ver detalhes", "id": "view-error-details-btn"},
                {"label": "Tentar novamente", "id": "retry-all-btn"}
            ]
        )