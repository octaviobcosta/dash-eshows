"""
Modal de Atualização de Base - Versão Melhorada com UX/UI Moderno
Implementa as melhores práticas de design para modais
"""

import os
import logging
import base64
import io
from datetime import datetime
import pandas as pd
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, MATCH, ALL, callback_context
from dash.exceptions import PreventUpdate
import dash

from app.data import data_manager
from app.data.column_mapping import MAPPING as COLUMN_MAPPING
from app.updates.csv_validator import CSVValidator, TABLE_SCHEMAS, suggest_column_mapping
from app.updates.csv_upload_components import (
    create_validation_report,
    create_preview_table,
    create_column_mapping_interface,
    create_upload_options_card,
    create_upload_summary,
    create_column_status_card,
    create_status_summary_card,
    create_issues_card
)
from app.updates.csv_uploader import CSVUploader

logger = logging.getLogger(__name__)

def brl_to_cents(brl_str):
    """
    Converte valor monetário para centavos
    Aceita formatos:
    - Brasileiro: "1.234,56" → 123456 (centavos)
    - Americano: "1,234.56" → 123456 (centavos)
    - Simples: "1234.56" ou "1234,56" → 123456 (centavos)
    - Com moeda: "R$ 1.234,56" → 123456 (centavos)
    """
    if pd.isna(brl_str) or str(brl_str).strip() == "":
        return 0
    
    # Converte para string e limpa
    brl_str = str(brl_str).strip()
    
    # Remove símbolo de moeda se houver
    brl_str = brl_str.replace("R$", "").replace("r$", "").replace("$", "").strip()
    
    # Detecta o formato baseado na posição de vírgulas e pontos
    has_comma = ',' in brl_str
    has_dot = '.' in brl_str
    
    if has_comma and has_dot:
        # Tem ambos - precisamos descobrir qual é o separador decimal
        last_comma = brl_str.rfind(',')
        last_dot = brl_str.rfind('.')
        
        if last_comma > last_dot:
            # Vírgula vem depois do ponto = formato BR (1.234,56)
            brl_str = brl_str.replace(".", "")  # Remove pontos (milhares)
            brl_str = brl_str.replace(",", ".")  # Vírgula vira ponto
        else:
            # Ponto vem depois da vírgula = formato US (1,234.56)
            brl_str = brl_str.replace(",", "")  # Remove vírgulas (milhares)
    elif has_comma and not has_dot:
        # Só tem vírgula - assume que é decimal (formato BR simples)
        brl_str = brl_str.replace(",", ".")
    # Se só tem ponto ou não tem nenhum, mantém como está
    
    try:
        # Converte para float, depois multiplica por 100 para centavos
        value_in_reais = float(brl_str)
        value_in_cents = round(value_in_reais * 100)
        return value_in_cents
    except:
        logger.warning(f"Não foi possível converter valor: {brl_str}")
        return 0

# Design tokens para consistência
COLORS = {
    'primary': '#fc4f22',
    'primary_hover': '#e84318',
    'secondary': '#fdb03d',
    'success': '#10b981',
    'danger': '#ef4444',
    'warning': '#f59e0b',
    'info': '#3b82f6',
    'dark': '#1f2937',
    'light': '#f9fafb',
    'muted': '#6b7280'
}

# CSS customizado para o modal
MODAL_STYLES = """
<style>
    /* Option cards hover effect */
    .option-card {
        transition: all 0.3s ease;
        border: 2px solid transparent;
    }
    
    .option-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
        border-color: #fc4f22 !important;
    }
    
    /* Step indicators */
    .step-indicator {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background-color: #e5e7eb;
        color: #6b7280;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .step-indicator.active {
        background-color: #fc4f22;
        color: white;
        box-shadow: 0 0 0 4px rgba(252, 79, 34, 0.2);
    }
    
    .step-indicator.completed {
        background-color: #10b981;
        color: white;
    }
    
    .step-label {
        font-size: 0.875rem;
        color: #6b7280;
        margin-top: 0.5rem;
    }
    
    /* Upload area hover */
    .upload-area:hover {
        background-color: #fef2f2 !important;
        border-color: #fc4f22 !important;
    }
    
    /* Table option cards */
    .table-option {
        transition: all 0.2s ease;
        border: 1px solid #e5e7eb;
    }
    
    .table-option:hover {
        border-color: #fc4f22;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    /* Primary button override */
    .btn-primary {
        background-color: #fc4f22 !important;
        border-color: #fc4f22 !important;
    }
    
    .btn-primary:hover {
        background-color: #e84318 !important;
        border-color: #e84318 !important;
    }
    
    /* Progress bar color */
    .progress-bar {
        background-color: #fc4f22 !important;
    }
    
    /* Modal header */
    .modal-header {
        border-bottom: 2px solid #fc4f22;
    }
    
    /* Validation cards */
    .validation-card {
        border-left: 4px solid #fc4f22;
    }
    
    /* Custom scrollbar */
    .modal-body::-webkit-scrollbar {
        width: 8px;
    }
    
    .modal-body::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    
    .modal-body::-webkit-scrollbar-thumb {
        background: #fc4f22;
        border-radius: 4px;
    }
    
    .modal-body::-webkit-scrollbar-thumb:hover {
        background: #e84318;
    }
    
    /* Estilos para cards de opção */
    .option-card {
        transition: all 0.2s ease;
        cursor: pointer;
    }
    
    .option-card:hover { 
        transform: translateY(-2px); 
        box-shadow: 0 4px 12px rgba(252, 79, 34, 0.15);
        border-color: #fc4f22;
    }
    
    /* Indicadores de passos */
    .step-indicator {
        transition: all 0.3s ease;
    }
    
    .step-indicator.active { 
        background-color: #fc4f22 !important;
        color: white !important;
    }
    
    /* Botões primários com cor da marca */
    .btn-primary {
        background-color: #fc4f22 !important;
        border-color: #fc4f22 !important;
    }
    
    .btn-primary:hover {
        background-color: #e84318 !important;
        border-color: #e84318 !important;
    }
    
    /* Cards de status */
    .status-card {
        border-left: 4px solid #fc4f22;
    }
    
    /* Toggle switches */
    .custom-switch .custom-control-input:checked ~ .custom-control-label::before {
        background-color: #fc4f22;
        border-color: #fc4f22;
    }
    
    /* Badges de tipo de coluna */
    .column-type-badge {
        font-size: 0.7rem;
        padding: 0.2rem 0.4rem;
    }
    
    /* Preview table styles */
    .preview-converted {
        background-color: #fef3c7 !important;
    }
    
    .preview-problem {
        background-color: #fee2e2 !important;
    }
</style>
"""

def create_update_modal():
    """Cria o modal de atualização com design moderno e UX otimizada"""
    return dbc.Modal(
        [
            # Stores
            dcc.Store(id='update-store-data'),
            dcc.Store(id='validation-store-data'),
            dcc.Store(id='upload-config-store', data={'mode': 'replace', 'error_handling': 'stop'}),
            dcc.Store(id='preview-mode-store', data={'show_converted': True}),
            dcc.Store(id='mapping-store', data={}),
            
            dbc.ModalHeader(
                [
                    html.Div([
                        html.I(className="fas fa-sync-alt me-2"),
                        html.Span("Atualização de Base de Dados", className="modal-title")
                    ], className="d-flex align-items-center")
                ],
                close_button=True,
                className="modal-header"
            ),
            dbc.ModalBody([
                # Inject custom CSS using a hidden div with style tag
                html.Div([
                    dcc.Markdown(f'<style>{MODAL_STYLES}</style>', 
                                dangerously_allow_html=True)
                ], style={'display': 'none'}),
                
                # Progress Indicator
                html.Div([
                    html.Div([
                        html.Div([
                            html.Div([
                                html.Div("1", className="step-indicator active", id="step-1-indicator"),
                                html.Div("Escolher Ação", className="step-label")
                            ], className="step-item"),
                            html.Div([
                                html.Div("2", className="step-indicator", id="step-2-indicator"),
                                html.Div("Selecionar Dados", className="step-label")
                            ], className="step-item"),
                            html.Div([
                                html.Div("3", className="step-indicator", id="step-3-indicator"),
                                html.Div("Confirmar", className="step-label")
                            ], className="step-item"),
                        ], className="d-flex justify-content-between mb-4")
                    ], className="px-4"),
                    
                    # Progress Bar
                    dbc.Progress(
                        value=33,
                        id="update-progress-bar",
                        className="mb-4",
                        style={"height": "4px"}
                    )
                ], className="mb-4"),
                
                # Alert container
                html.Div(id="alert-container-update", className="mb-3"),
                
                # Container principal de alertas para callbacks
                html.Div(id="alert-atualiza-base-container"),
                
                # Step 1: Choose Action
                html.Div([
                    html.H5("Como deseja atualizar a base?", className="text-center mb-4 text-secondary"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="fas fa-file-upload fa-3x text-primary mb-3"),
                                            html.H5("Upload de Arquivo", className="mb-2"),
                                            html.P(
                                                "Envie um arquivo CSV com os dados atualizados",
                                                className="text-muted small mb-0"
                                            )
                                        ], className="text-center")
                                    ], className="p-4")
                                ], 
                                className="option-card h-100")
                            ], id="upload-option-card", n_clicks=0, style={"cursor": "pointer"})
                        ], md=6),
                        
                        dbc.Col([
                            html.Div([
                                dbc.Card([
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="fas fa-cloud-download-alt fa-3x text-warning mb-3"),
                                            html.H5("Buscar do ERP", className="mb-2"),
                                            html.P(
                                                "Importar dados diretamente do sistema ERP",
                                                className="text-muted small mb-0"
                                            )
                                        ], className="text-center")
                                    ], className="p-4")
                                ], 
                                className="option-card h-100")
                            ], id="erp-option-card", n_clicks=0, style={"cursor": "pointer"})
                        ], md=6)
                    ], className="g-3")
                ], id="step-1-content", style={"display": "block"}),
                
                # Step 2: Upload or Select Tables
                html.Div([
                    # Upload Section - Enhanced
                    html.Div([
                        # Step 2A: Upload File
                        html.Div([
                            html.H5("Faça upload do arquivo CSV", className="mb-4"),
                            dcc.Upload(
                                id="upload-data-update",
                                children=html.Div([
                                    html.I(className="fas fa-cloud-upload-alt fa-3x text-muted mb-3"),
                                    html.P("Arraste e solte ou ", className="mb-0"),
                                    html.A("clique para selecionar", className="text-primary fw-bold"),
                                    html.P("Tamanho máximo: 100MB", className="text-muted small mt-2")
                                ], className="text-center py-5"),
                                style={
                                    'borderWidth': '2px',
                                    'borderRadius': '12px',
                                    'borderColor': '#e5e7eb',
                                    'borderStyle': 'dashed',
                                    'backgroundColor': '#f9fafb',
                                    'cursor': 'pointer'
                                },
                                className="upload-area mb-4",
                                multiple=False,
                                max_size=100 * 1024 * 1024  # 100MB
                            ),
                            
                            # File info
                            html.Div(id="file-info-update", className="mb-3"),
                            
                            # Select table for upload
                            html.Div([
                                dbc.Label("Selecione a tabela de destino:", className="fw-bold"),
                                dbc.Select(
                                    id="table-select-upload",
                                    placeholder="Escolha uma tabela...",
                                    className="mb-3"
                                )
                            ], id="table-select-container", style={"display": "none"})
                        ], id="upload-step-file", style={"display": "block"}),
                        
                        # Step 2B: Validation Results
                        html.Div([
                            html.H5([
                                html.I(className="fas fa-check-circle me-2"),
                                "Validação e Preview"
                            ], className="mb-4"),
                            
                            # Validation report
                            html.Div(id="validation-report", className="mb-4"),
                            
                            # Preview table
                            html.Div(id="preview-table-container", className="mb-4"),
                            
                            # Column mapping (if needed)
                            html.Div(id="column-mapping-container", className="mb-4"),
                            
                            # Upload options
                            html.Div([
                                create_upload_options_card()
                            ], className="mb-4"),
                            
                            # Actions
                            dbc.Row([
                                dbc.Col([
                                    dbc.Button([
                                        html.I(className="fas fa-arrow-left me-2"),
                                        "Voltar"
                                    ], id="btn-back-validation", color="secondary", outline=True)
                                ], width="auto"),
                                dbc.Col([
                                    dbc.Button([
                                        html.I(className="fas fa-check me-2"),
                                        "Validar Novamente"
                                    ], id="btn-revalidate", color="info", outline=True)
                                ], width="auto"),
                            ], className="g-2")
                        ], id="upload-step-validation", style={"display": "none"})
                    ], id="upload-section", style={"display": "none"}),
                    
                    # ERP Tables Section
                    html.Div([
                        html.H5("Selecione as tabelas para atualizar", className="mb-4"),
                        html.P(
                            "Escolha uma ou mais tabelas para buscar do ERP:",
                            className="text-muted mb-3"
                        ),
                        html.Div([
                            # Categoria: Dados Principais
                            html.Div([
                                html.H6([html.I(className="fas fa-database me-2", style={"fontSize": "0.875rem"}), "Dados Principais"], className="text-muted mb-2", style={"fontSize": "0.875rem"})
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "baseeshows"},
                                                label="Base eShows",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Shows e eventos", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "base2"},
                                                label="Base2",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Complementar", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                            ], className="g-2 mb-3"),
                            
                            # Categoria: Dados Financeiros
                            html.Div([
                                html.H6([html.I(className="fas fa-dollar-sign me-2", style={"fontSize": "0.875rem"}), "Dados Financeiros"], className="text-muted mb-2", style={"fontSize": "0.875rem"})
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "custosabertos"},
                                                label="Custos Abertos",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Despesas", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "boletoartistas"},
                                                label="Boletos Artistas",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Pagto. artistas", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "boletocasas"},
                                                label="Boletos Casas",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Pagto. casas", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                            ], className="g-2 mb-3"),
                            
                            # Categoria: Gestão de Pessoas
                            html.Div([
                                html.H6([html.I(className="fas fa-users me-2", style={"fontSize": "0.875rem"}), "Gestão de Pessoas"], className="text-muted mb-2", style={"fontSize": "0.875rem"})
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "pessoas"},
                                                label="Pessoas",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Cadastro geral", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "npsartistas"},
                                                label="NPS Artistas",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Satisfação", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                            ], className="g-2 mb-3"),
                            
                            # Categoria: Gestão e Metas
                            html.Div([
                                html.H6([html.I(className="fas fa-chart-line me-2", style={"fontSize": "0.875rem"}), "Gestão e Metas"], className="text-muted mb-2", style={"fontSize": "0.875rem"})
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "metas"},
                                                label="Metas",
                                                value=False,
                                                className="mb-1"
                                            ),
                                            html.Small("Objetivos", className="text-muted", style={"fontSize": "0.75rem"})
                                        ], className="p-3")
                                    ], className="table-option mb-2", style={"height": "100%"})
                                ], md=4),
                            ], className="g-2")
                        ])
                    ], id="erp-section", style={"display": "none"})
                ], id="step-2-content", style={"display": "none"}),
                
                # Step 3: Review and Confirm
                html.Div([
                    html.H5("Revise e confirme a atualização", className="mb-4"),
                    
                    # Summary card
                    dbc.Card([
                        dbc.CardBody([
                            html.Div(id="update-summary", className="mb-3"),
                            
                            # Preview table
                            html.Div(id="preview-container-update", className="mb-3"),
                            
                            # Warning message
                            dbc.Alert([
                                html.I(className="fas fa-exclamation-triangle me-2"),
                                html.Strong("Atenção: "),
                                "Esta ação irá sobrescrever os dados existentes na(s) tabela(s) selecionada(s)."
                            ], color="warning", className="mb-0")
                        ])
                    ], className="mb-3")
                ], id="step-3-content", style={"display": "none"}),
                
                # Loading overlay
                dbc.Spinner(
                    html.Div(id="loading-content-update"),
                    size="lg",
                    color="primary",
                    spinner_style={"width": "3rem", "height": "3rem"}
                )
            ], className="modal-body"),
            
            dbc.ModalFooter([
                dbc.Button(
                    "Voltar",
                    id="btn-back-update",
                    color="light",
                    className="me-2",
                    style={"display": "none"}
                ),
                dbc.Button(
                    "Próximo",
                    id="btn-next-update",
                    color="primary",
                    className="btn-primary-gradient",
                    disabled=True
                ),
                dbc.Button(
                    "Confirmar Atualização",
                    id="btn-confirm-update",
                    color="success",
                    className="btn-primary-gradient",
                    style={"display": "none"},
                    disabled=True
                )
            ], className="modal-footer")
        ],
        id="update-modal",
        size="lg",
        is_open=False,
        centered=True,
        backdrop="static",
        className="modal-update"
        )

def init_update_modal_callbacks(app):
    """Inicializa todos os callbacks do modal de atualização"""
    """Inicializa os callbacks do modal de atualização"""
    
    # Callback para navegação entre steps
    @app.callback(
        [Output("step-1-content", "style"),
         Output("step-2-content", "style"),
         Output("step-3-content", "style"),
         Output("btn-back-update", "style"),
         Output("btn-next-update", "style"),
         Output("btn-next-update", "children"),
         Output("btn-confirm-update", "style"),
         Output("update-progress-bar", "value"),
         Output("step-1-indicator", "className"),
         Output("step-2-indicator", "className"),
         Output("step-3-indicator", "className")],
        [Input("upload-option-card", "n_clicks"),
         Input("erp-option-card", "n_clicks"),
         Input("btn-next-update", "n_clicks"),
         Input("btn-back-update", "n_clicks"),
         Input("btn-confirm-update", "n_clicks")],
        [State("upload-data-update", "contents"),
         State("table-select-upload", "value"),
         State({"type": "table-checkbox", "index": ALL}, "value")],
        prevent_initial_call=True
    )
    def navigate_steps(upload_clicks, erp_clicks, next_clicks, back_clicks, 
                      confirm_clicks, upload_contents, selected_table, table_checkboxes):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        # Determine current step
        current_step = 1
        if trigger_id in ["upload-option-card", "erp-option-card"]:
            current_step = 2
        elif trigger_id == "btn-next-update":
            current_step = 3
        elif trigger_id == "btn-back-update":
            current_step = 1
        
        # Configure display based on step
        step1_style = {"display": "block"} if current_step == 1 else {"display": "none"}
        step2_style = {"display": "block"} if current_step == 2 else {"display": "none"}
        step3_style = {"display": "block"} if current_step == 3 else {"display": "none"}
        
        # Configure buttons
        back_style = {"display": "inline-block"} if current_step > 1 else {"display": "none"}
        next_style = {"display": "inline-block"} if current_step < 3 else {"display": "none"}
        confirm_style = {"display": "inline-block"} if current_step == 3 else {"display": "none"}
        
        next_text = "Próximo" if current_step < 3 else "Próximo"
        
        # Progress bar
        progress = 33 if current_step == 1 else 66 if current_step == 2 else 100
        
        # Step indicators
        step1_class = "step-indicator active" if current_step == 1 else "step-indicator completed"
        step2_class = "step-indicator active" if current_step == 2 else "step-indicator completed" if current_step > 2 else "step-indicator"
        step3_class = "step-indicator active" if current_step == 3 else "step-indicator"
        
        return (step1_style, step2_style, step3_style, back_style, next_style, 
                next_text, confirm_style, progress, step1_class, step2_class, step3_class)
    
    # Callback para mostrar seção apropriada no step 2
    @app.callback(
        [Output("upload-section", "style"),
         Output("erp-section", "style")],
        [Input("upload-option-card", "n_clicks"),
         Input("erp-option-card", "n_clicks")],
        prevent_initial_call=True
    )
    def show_appropriate_section(upload_clicks, erp_clicks):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if trigger_id == "upload-option-card":
            return {"display": "block"}, {"display": "none"}
        elif trigger_id == "erp-option-card":
            return {"display": "none"}, {"display": "block"}
        
        return {"display": "none"}, {"display": "none"}
    
    # Callback para processar upload
    @app.callback(
        [Output("file-info-update", "children"),
         Output("table-select-container", "style"),
         Output("update-store-data", "data"),
         Output("btn-next-update", "disabled")],
        [Input("upload-data-update", "contents")],
        [State("upload-data-update", "filename")],
        prevent_initial_call=True
    )
    def process_upload(contents, filename):
        if not contents:
            return None, {"display": "none"}, None, True
        
        try:
            # Parse the uploaded file
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']
            df = None
            successful_encoding = None
            
            for encoding in encodings:
                try:
                    # Primeiro tenta ler normalmente
                    df = pd.read_csv(
                        io.StringIO(decoded.decode(encoding)),
                        sep=None,  # Detecta automaticamente o separador
                        engine='python',
                        dtype=str       # Lê tudo como string para processar depois
                    )
                    successful_encoding = encoding
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except pd.errors.ParserError as e:
                    # Se falhar por problema de parsing, tenta com on_bad_lines='skip'
                    try:
                        df = pd.read_csv(
                            io.StringIO(decoded.decode(encoding)), 
                            on_bad_lines='skip',  # Nova sintaxe do pandas
                            sep=None,  # Detecta automaticamente o separador
                            engine='python',
                            dtype=str
                        )
                        successful_encoding = encoding
                        logger.warning(f"CSV com linhas problemáticas. Linhas inválidas foram ignoradas: {e}")
                        break
                    except:
                        continue
            
            if df is None:
                raise ValueError("Não foi possível decodificar o arquivo. Tente salvá-lo como UTF-8.")
            
            # Normalizar nomes de colunas (snake_case, sem acentos)
            df.columns = (
                df.columns
                .str.strip()
                .str.lower()
                .str.replace(" ", "_")
                .str.normalize("NFKD")
                .str.encode("ascii", "ignore")
                .str.decode("ascii")
            )
            
            # Create file info card
            file_info = dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-file-csv fa-2x text-success mb-2"),
                        html.H6(filename, className="mb-1"),
                        html.Small(f"{len(df)} linhas × {len(df.columns)} colunas", 
                                 className="text-muted d-block"),
                        html.Small(f"Encoding: {successful_encoding}", 
                                 className="text-muted")
                    ], className="text-center")
                ])
            ], className="mb-3")
            
            # Show table selector
            table_style = {"display": "block"}
            
            # Store data
            store_data = {
                "filename": filename,
                "data": df.to_dict('records'),
                "columns": list(df.columns),
                "rows": len(df)
            }
            
            return file_info, table_style, store_data, True  # Keep button disabled until table selected
            
        except Exception as e:
            error_details = str(e)
            
            # Mensagens específicas para diferentes tipos de erro
            if "codec" in error_details or "decode" in error_details:
                error_details = "Problema com a codificação do arquivo. O sistema tentou múltiplos formatos mas não conseguiu ler o arquivo. Por favor, salve o arquivo como UTF-8 no Excel ou editor de texto."
            elif "Expected" in error_details and "fields" in error_details:
                error_details = ("Problema na estrutura do CSV. O arquivo possui linhas com número diferente de colunas. "
                               "Verifique se:\n"
                               "• Não há vírgulas extras em células\n"
                               "• O delimitador está correto (vírgula, ponto-e-vírgula, etc.)\n"
                               "• Não há quebras de linha dentro de células")
            elif "ParserError" in error_details:
                error_details = "Erro ao processar o CSV. Verifique se o arquivo está no formato correto."
            
            error_msg = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                html.Strong("Erro ao processar arquivo"),
                html.Br(),
                html.Small(error_details, className="d-block mt-2 text-pre-wrap")
            ], color="danger")
            return error_msg, {"display": "none"}, None, True
    
    # Callback para validar quando tabela é selecionada
    @app.callback(
        [Output("upload-step-file", "style"),
         Output("upload-step-validation", "style"),
         Output("validation-report", "children"),
         Output("preview-table-container", "children"),
         Output("column-mapping-container", "children"),
         Output("validation-store-data", "data")],
        [Input("table-select-upload", "value")],
        [State("update-store-data", "data")],
        prevent_initial_call=True
    )
    def validate_csv_data(selected_table, store_data):
        if not selected_table or not store_data:
            raise PreventUpdate
        
        try:
            # Criar DataFrame dos dados
            df = pd.DataFrame(store_data["data"])
            
            # Validar usando CSVValidator
            validator = CSVValidator(df, selected_table)
            validation_result = validator.validate()
            
            # Obter schema da tabela
            schema = TABLE_SCHEMAS.get(selected_table, {})
            
            # Adicionar table_name ao validation_result
            validation_result["table_name"] = selected_table
            
            # Criar componentes de validação
            # 1. Relatório de validação (incluirá status summary e column status)
            logger.info(f"Validation result stats: {validation_result.get('stats', {})}")
            logger.info(f"Can proceed: {validation_result.get('can_proceed', False)}")
            validation_report = create_validation_report(validation_result)
            
            # 2. Preview da tabela com dados convertidos
            preview_table = create_preview_table(
                validation_result["preview_data"],
                show_problems=True,
                show_converted=False,  # Inicialmente mostra dados originais
                table_name=selected_table
            )
            
            # 3. Interface de mapeamento (se necessário)
            column_mapping_interface = None
            
            # Mostrar interface de mapeamento se houver sugestões ou se o usuário solicitar
            if validation_result.get("column_mapping"):
                all_expected_columns = (
                    schema.get("essential_columns", []) +
                    schema.get("required_columns", []) +
                    schema.get("optional_columns", [])
                )
                
                # Criar mapeamento completo incluindo todas as colunas
                full_mapping = {}
                for col in df.columns:
                    if col in validation_result.get("column_mapping", {}):
                        full_mapping[col] = validation_result["column_mapping"][col]
                    else:
                        # Tentar sugerir mapeamento
                        suggested = suggest_column_mapping([col], selected_table)
                        full_mapping[col] = suggested.get(col, "")
                
                column_mapping_interface = create_column_mapping_interface(
                    list(df.columns),
                    all_expected_columns,
                    full_mapping,
                    schema
                )
            
            # Esconder step file, mostrar validation
            return {"display": "none"}, {"display": "block"}, validation_report, preview_table, column_mapping_interface, validation_result
            
        except Exception as e:
            logger.error(f"Erro na validação: {e}")
            error_report = dbc.Alert([
                html.I(className="fas fa-times-circle me-2"),
                f"Erro ao validar dados: {str(e)}"
            ], color="danger")
            return {"display": "block"}, {"display": "none"}, error_report, None, None, None
    
    # Callback para voltar do step de validação
    @app.callback(
        [Output("upload-step-file", "style", allow_duplicate=True),
         Output("upload-step-validation", "style", allow_duplicate=True)],
        Input("btn-back-validation", "n_clicks"),
        prevent_initial_call=True
    )
    def back_from_validation(n_clicks):
        if n_clicks:
            return {"display": "block"}, {"display": "none"}
        raise PreventUpdate
    
    # Callback para atualizar configurações de upload
    @app.callback(
        Output("upload-config-store", "data"),
        [Input("upload-mode", "value"),
         Input("error-handling", "value")],
        prevent_initial_call=True
    )
    def update_upload_config(mode, error_handling):
        return {"mode": mode, "error_handling": error_handling}
    
    # Populate table options
    @app.callback(
        Output("table-select-upload", "options"),
        Input("table-select-container", "style"),
        prevent_initial_call=True
    )
    def populate_table_options(style):
        if style.get("display") == "none":
            raise PreventUpdate
        
        return [
            {"label": "Base eShows - Dados principais de shows", "value": "baseeshows"},
            {"label": "Base2 - Dados complementares", "value": "base2"},
            {"label": "Custos Abertos - Custos e despesas", "value": "custosabertos"},
            {"label": "Boletos Artistas - Pagamentos artistas", "value": "boletoartistas"},
            {"label": "Boletos Casas - Pagamentos casas", "value": "boletocasas"},
            {"label": "Pessoas - Cadastro geral", "value": "pessoas"},
            {"label": "NPS Artistas - Pesquisa satisfação", "value": "npsartistas"},
            {"label": "Metas - Metas e objetivos", "value": "metas"}
        ]
    
    # Callback para atualizar resumo
    @app.callback(
        [Output("update-summary", "children"),
         Output("preview-container-update", "children"),
         Output("btn-confirm-update", "disabled")],
        [Input("step-3-content", "style")],
        [State("update-store-data", "data"),
         State("table-select-upload", "value"),
         State({"type": "table-checkbox", "index": ALL}, "value"),
         State({"type": "table-checkbox", "index": ALL}, "id"),
         State("validation-store-data", "data"),
         State("upload-config-store", "data")],
        prevent_initial_call=True
    )
    def update_summary(style, store_data, upload_table, erp_checks, erp_ids, validation_data, upload_config):
        if style.get("display") == "none":
            raise PreventUpdate
        
        summary_items = []
        
        # Check if upload option
        if store_data and upload_table:
            # Use create_upload_summary for better formatting
            summary = create_upload_summary(
                store_data['filename'],
                upload_table,
                store_data['rows'],
                upload_config.get('mode', 'replace'),
                validation_data if validation_data else {"valid": True, "errors": [], "warnings": []}
            )
            
            return summary, None, not (validation_data and validation_data.get("valid", False))
        
        # Check if ERP option
        selected_tables = []
        for i, (checked, table_id) in enumerate(zip(erp_checks, erp_ids)):
            if checked and i < len(erp_ids):
                table_name = table_id["index"]
                selected_tables.append(table_name)
        
        if selected_tables:
            summary_items.append(
                html.Div([
                    html.I(className="fas fa-database text-warning me-2"),
                    html.Strong("Tabelas do ERP: "),
                    html.Span(", ".join(selected_tables))
                ], className="mb-2")
            )
            
            return summary_items, None, False
        
        return html.P("Nenhuma ação selecionada", className="text-muted"), None, True
    
    # Callback para habilitar botão Próximo quando tabelas são selecionadas (upload ou ERP)
    @app.callback(
        Output("btn-next-update", "disabled", allow_duplicate=True),
        [Input({"type": "table-checkbox", "index": ALL}, "value"),
         Input("table-select-upload", "value")],
        [State("upload-section", "style"),
         State("erp-section", "style")],
        prevent_initial_call=True
    )
    def toggle_next_button(checkbox_values, upload_table_selected, upload_style, erp_style):
        # Verifica qual seção está visível
        if upload_style and upload_style.get("display") != "none":
            # Na seção de upload, verifica se uma tabela foi selecionada no dropdown
            return not bool(upload_table_selected)
        elif erp_style and erp_style.get("display") != "none":
            # Na seção ERP, verifica se pelo menos uma checkbox está marcada
            return not any(checkbox_values)
        
        # Por padrão, mantém desabilitado
        return True
    
    # Callback para processar a confirmação da atualização
    @app.callback(
        [Output("update-modal", "is_open", allow_duplicate=True),
         Output("alert-atualiza-base-container", "children"),
         Output("btn-confirm-update", "children"),
         Output("btn-confirm-update", "disabled", allow_duplicate=True),
         Output("loading-content-update", "children")],
        [Input("btn-confirm-update", "n_clicks")],
        [State("update-store-data", "data"),
         State("table-select-upload", "value"),
         State({"type": "table-checkbox", "index": ALL}, "value"),
         State({"type": "table-checkbox", "index": ALL}, "id"),
         State("validation-store-data", "data"),
         State("upload-config-store", "data")],
        prevent_initial_call=True
    )
    def process_update_confirmation(n_clicks, store_data, upload_table, erp_checks, erp_ids, validation_data, upload_config):
        if not n_clicks:
            raise PreventUpdate
        
        try:
            # Opção 1: Upload de arquivo CSV
            if store_data and upload_table:
                # Verificar se pode prosseguir (colunas essenciais OK)
                if not validation_data or not validation_data.get("can_proceed", False):
                    missing_essential = validation_data.get("missing_essential", []) if validation_data else []
                    return False, dbc.Alert([
                        html.I(className="fas fa-exclamation-triangle me-2"),
                        html.Strong("Não é possível prosseguir!"),
                        html.Br(),
                        f"Faltam colunas essenciais: {', '.join(missing_essential)}" if missing_essential else "Dados não validados."
                    ], color="danger", dismissable=True), "Confirmar Atualização", False, None
                
                # Criar DataFrame
                df = pd.DataFrame(store_data["data"])
                
                # Executar upload
                try:
                    uploader = CSVUploader()
                    
                    # Extrair informações da validação
                    column_mapping = validation_data.get("column_mapping", {})
                    default_values = validation_data.get("default_values", {})
                    
                    # Executar upload com os novos parâmetros
                    upload_result = uploader.upload_data(
                        df=df,
                        table_name=upload_table,
                        mode=upload_config.get("mode", "replace"),
                        error_handling=upload_config.get("error_handling", "stop"),
                        column_mapping=column_mapping,
                        default_values=default_values,
                        generate_ids=True  # Sempre gerar IDs se necessário
                    )
                    
                    # Criar mensagem de resultado
                    if upload_result["success"]:
                        message = dbc.Alert([
                            html.Div([
                                html.I(className="fas fa-check-circle me-2", style={"fontSize": "1.5rem"}),
                                html.Strong("Upload concluído com sucesso!", className="fs-5")
                            ], className="mb-3"),
                            html.Hr(),
                            html.Div([
                                html.P([
                                    html.I(className="fas fa-database me-2"),
                                    f"Tabela: {upload_table.upper()}"
                                ], className="mb-2"),
                                html.P([
                                    html.I(className="fas fa-file me-2"),
                                    f"Arquivo: {store_data['filename']}"
                                ], className="mb-2"),
                                html.P([
                                    html.I(className="fas fa-check me-2"),
                                    f"Registros processados: {upload_result['rows_processed']:,}"
                                ], className="mb-2"),
                                html.P([
                                    html.I(className="fas fa-plus-circle me-2"),
                                    f"Registros inseridos: {upload_result['rows_inserted']:,}"
                                ], className="mb-2"),
                                html.P([
                                    html.I(className="fas fa-clock me-2"),
                                    f"Tempo de processamento: {upload_result['duration']:.2f} segundos"
                                ], className="mb-0")
                            ])
                        ], color="success", dismissable=True)
                    else:
                        # Upload falhou
                        error_details = []
                        for error in upload_result["errors"][:5]:  # Mostrar até 5 erros
                            error_details.append(
                                html.Li([
                                    html.Strong(f"{error['type']}: "),
                                    error["message"]
                                ], className="mb-1")
                            )
                        
                        message = dbc.Alert([
                            html.Div([
                                html.I(className="fas fa-times-circle me-2", style={"fontSize": "1.5rem"}),
                                html.Strong("Falha no upload!", className="fs-5")
                            ], className="mb-3"),
                            html.Hr(),
                            html.P([
                                html.I(className="fas fa-exclamation-triangle me-2"),
                                f"Registros processados: {upload_result['rows_processed']:,} de {store_data['rows']:,}"
                            ]),
                            html.P("Erros encontrados:", className="fw-bold mb-2"),
                            html.Ul(error_details)
                        ], color="danger", dismissable=True)
                    
                    # Limpar cache se sucesso
                    if upload_result["success"]:
                        data_manager.clear_cache()
                    
                    return False, message, "Confirmar Atualização", False, None
                    
                except Exception as e:
                    logger.error(f"Erro no upload: {e}")
                    return False, dbc.Alert([
                        html.I(className="fas fa-times-circle me-2"),
                        html.Strong("Erro ao processar upload: "),
                        str(e)
                    ], color="danger", dismissable=True), "Confirmar Atualização", False, None
            
            # Opção 2: Atualização do ERP
            selected_tables = []
            for i, checked in enumerate(erp_checks):
                if checked:
                    table_name = erp_ids[i]["index"]
                    selected_tables.append(table_name)
            
            if selected_tables:
                # Mostra loading
                loading_msg = html.Div([
                    html.P("🔄 Atualizando tabelas...", className="text-center mb-2"),
                    html.Small(f"Processando {len(selected_tables)} tabela(s)", className="text-muted")
                ], className="text-center")
                
                # Importa e executa a atualização
                from app.data_manager import reload_tables
                
                results = reload_tables(selected_tables)
                
                # Prepara mensagem de resultado
                success_count = sum(1 for r in results.values() if r["status"] == "success")
                error_count = sum(1 for r in results.values() if r["status"] == "error")
                
                # Cria a mensagem principal
                if error_count == 0:
                    message_icon = html.I(className="fas fa-check-circle me-2", style={"color": "#10b981"})
                    message_title = html.Strong(f"Atualização concluída com sucesso!")
                    message_subtitle = html.P(f"{success_count} tabela(s) atualizada(s)", className="mb-0")
                    color = "success"
                elif success_count > 0:
                    message_icon = html.I(className="fas fa-exclamation-circle me-2", style={"color": "#f59e0b"})
                    message_title = html.Strong(f"Atualização parcialmente concluída")
                    message_subtitle = html.P(f"{success_count} sucesso(s), {error_count} erro(s)", className="mb-0")
                    color = "warning"
                else:
                    message_icon = html.I(className="fas fa-times-circle me-2", style={"color": "#ef4444"})
                    message_title = html.Strong(f"Falha na atualização")
                    message_subtitle = html.P(f"{error_count} erro(s) encontrado(s)", className="mb-0")
                    color = "danger"
                
                # Cria lista de detalhes
                details_list = []
                for table, result in results.items():
                    if result["status"] == "success":
                        icon = html.I(className="fas fa-check text-success me-2")
                        text = f"{table.upper()}: {result['rows']:,} registros carregados"
                    else:
                        icon = html.I(className="fas fa-times text-danger me-2")
                        text = f"{table.upper()}: {result.get('error', 'Erro desconhecido')}"
                    
                    details_list.append(html.Li([icon, text], className="mb-1"))
                
                # Monta a mensagem completa
                message = dbc.Alert([
                    html.Div([message_icon, message_title], className="mb-2"),
                    message_subtitle,
                    html.Hr(className="my-3"),
                    html.P("Detalhes da atualização:", className="fw-bold mb-2"),
                    html.Ul(details_list, className="ps-3")
                ], color=color, dismissable=True, fade=True)
                
                # Fecha o modal e mostra o alerta
                return False, message, "Confirmar Atualização", False, None
            
            return False, dbc.Alert([
                html.I(className="fas fa-info-circle me-2"),
                "Nenhuma tabela foi selecionada para atualização"
            ], color="info", dismissable=True), "Confirmar Atualização", False, None
            
        except Exception as e:
            logger.error(f"Erro ao processar atualização: {e}")
            return False, dbc.Alert([
                html.I(className="fas fa-times-circle me-2"),
                html.Strong("Erro ao processar atualização"),
                html.P(str(e), className="mb-0 mt-2")
            ], color="danger", dismissable=True), "Confirmar Atualização", False, None
    
    # Callback para alternar a visualização do preview (dados originais vs convertidos)
    @app.callback(
        Output("preview-table-container", "children", allow_duplicate=True),
        [Input("toggle-preview-view", "n_clicks")],
        [State("validation-store-data", "data"),
         State("table-select-upload", "value")],
        prevent_initial_call=True
    )
    def toggle_preview_view(n_clicks, validation_data, table_name):
        if not n_clicks or not validation_data:
            raise PreventUpdate
        
        # Determinar o estado atual baseado no número de cliques
        show_converted = n_clicks % 2 == 1
        
        # Recriar a tabela de preview com o novo estado
        preview_table = create_preview_table(
            validation_data["preview_data"],
            show_problems=True,
            show_converted=show_converted,
            table_name=table_name
        )
        
        return preview_table
    
    # Callback para mostrar/esconder interface de mapeamento
    @app.callback(
        [Output("column-mapping-container", "children", allow_duplicate=True),
         Output("column-mapping-container", "style", allow_duplicate=True)],
        [Input("edit-mappings-btn", "n_clicks")],
        [State("column-mapping-container", "children"),
         State("update-store-data", "data"),
         State("table-select-upload", "value"),
         State("validation-store-data", "data")],
        prevent_initial_call=True
    )
    def toggle_mapping_interface(n_clicks, current_mapping, store_data, table_name, validation_data):
        if not n_clicks:
            raise PreventUpdate
        
        # Se já está mostrando, esconder
        if current_mapping:
            return None, {"display": "none"}
        
        # Criar interface de mapeamento
        if store_data and table_name:
            df = pd.DataFrame(store_data["data"])
            schema = TABLE_SCHEMAS.get(table_name, {})
            
            all_expected_columns = (
                schema.get("essential_columns", []) +
                schema.get("required_columns", []) +
                schema.get("optional_columns", [])
            )
            
            # Obter mapeamento atual ou criar novo
            current_mapping = validation_data.get("column_mapping", {}) if validation_data else {}
            
            # Criar mapeamento completo
            full_mapping = {}
            for col in df.columns:
                if col in current_mapping:
                    full_mapping[col] = current_mapping[col]
                else:
                    # Tentar sugerir mapeamento
                    suggested = suggest_column_mapping([col], table_name)
                    full_mapping[col] = suggested.get(col, "")
            
            mapping_interface = create_column_mapping_interface(
                list(df.columns),
                all_expected_columns,
                full_mapping,
                schema
            )
            
            return mapping_interface, {"display": "block"}
        
        return None, {"display": "none"}
    
    # Callback para aplicar mudanças de mapeamento
    @app.callback(
        [Output("validation-store-data", "data", allow_duplicate=True),
         Output("validation-report", "children", allow_duplicate=True),
         Output("column-mapping-container", "style", allow_duplicate=True)],
        [Input("confirm-mapping-btn", "n_clicks")],
        [State({"type": "column-mapping", "csv_column": ALL}, "value"),
         State({"type": "column-mapping", "csv_column": ALL}, "id"),
         State("update-store-data", "data"),
         State("table-select-upload", "value")],
        prevent_initial_call=True
    )
    def apply_mapping_changes(n_clicks, mapping_values, mapping_ids, store_data, table_name):
        if not n_clicks or not store_data or not table_name:
            raise PreventUpdate
        
        # Construir novo mapeamento
        new_mapping = {}
        for value, mapping_id in zip(mapping_values, mapping_ids):
            csv_column = mapping_id["csv_column"]
            if value:  # Só incluir se não for vazio (ignorar coluna)
                new_mapping[csv_column] = value
        
        # Revalidar com novo mapeamento
        df = pd.DataFrame(store_data["data"])
        validator = CSVValidator(df, table_name)
        
        # Aplicar o mapeamento customizado
        validator.column_mapping = new_mapping
        validation_result = validator.validate()
        validation_result["table_name"] = table_name
        
        # Recriar relatório de validação
        new_report = create_validation_report(validation_result)
        
        # Esconder interface de mapeamento
        return validation_result, new_report, {"display": "none"}
    
    # Callback para resetar mapeamento para sugestões automáticas
    @app.callback(
        [Output({"type": "column-mapping", "csv_column": ALL}, "value")],
        [Input("reset-mapping-btn", "n_clicks")],
        [State("update-store-data", "data"),
         State("table-select-upload", "value"),
         State({"type": "column-mapping", "csv_column": ALL}, "id")],
        prevent_initial_call=True
    )
    def reset_mapping_to_suggestions(n_clicks, store_data, table_name, mapping_ids):
        if not n_clicks or not store_data or not table_name:
            raise PreventUpdate
        
        # Obter sugestões automáticas
        df = pd.DataFrame(store_data["data"])
        
        # Criar lista de valores sugeridos na mesma ordem dos IDs
        suggested_values = []
        for mapping_id in mapping_ids:
            csv_column = mapping_id["csv_column"]
            suggested = suggest_column_mapping([csv_column], table_name)
            suggested_values.append(suggested.get(csv_column, ""))
        
        return [suggested_values]
    
    # Callback para toggle do modo de preview
    @app.callback(
        [Output("preview-table-container", "children", allow_duplicate=True),
         Output("preview-mode-store", "data", allow_duplicate=True)],
        [Input("preview-mode-switch", "value")],
        [State("validation-store-data", "data"),
         State("table-select-upload", "value")],
        prevent_initial_call=True
    )
    def toggle_preview_view(show_converted, validation_data, table_name):
        if not validation_data:
            raise PreventUpdate
        
        # Atualizar store
        preview_mode_data = {"show_converted": show_converted}
        
        # Recriar preview table com novo modo
        preview_data = validation_data.get("preview", {})
        if preview_data:
            preview_table = create_preview_table(
                preview_data, 
                show_problems=True,
                show_converted=show_converted,
                table_name=table_name
            )
            return preview_table, preview_mode_data
        
        return html.Div("Sem dados para preview"), preview_mode_data
    
    # Callback para mostrar/esconder interface de mapeamento
    @app.callback(
        Output("column-mapping-container", "style", allow_duplicate=True),
        [Input("edit-mapping-btn", "n_clicks"),
         Input("apply-mapping-btn", "n_clicks")],
        [State("column-mapping-container", "style")],
        prevent_initial_call=True
    )
    def toggle_mapping_interface(edit_clicks, apply_clicks, current_style):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if trigger_id == "edit-mapping-btn":
            # Mostrar interface
            return {"display": "block", "marginTop": "20px"}
        elif trigger_id == "apply-mapping-btn":
            # Esconder interface
            return {"display": "none"}
        
        return current_style

    return True