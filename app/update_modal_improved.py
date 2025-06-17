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

from app import data_manager
from app.column_mapping import MAPPING as COLUMN_MAPPING

logger = logging.getLogger(__name__)

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

# Store for upload data
update_store_data = dcc.Store(id='update-store-data')

def create_update_modal():
    """Cria o modal de atualização com design moderno e UX otimizada"""
    return dbc.Modal(
        [
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
                    # Upload Section
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
                    ], id="upload-section", style={"display": "none"}),
                    
                    # ERP Tables Section
                    html.Div([
                        html.H5("Selecione as tabelas para atualizar", className="mb-4"),
                        html.P(
                            "Escolha uma ou mais tabelas para buscar do ERP:",
                            className="text-muted mb-3"
                        ),
                        html.Div([
                            dbc.Row([
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "baseeshows"},
                                                label="Base eShows",
                                                value=False,
                                                className="mb-2"
                                            ),
                                            html.Small("Dados principais de shows e eventos", className="text-muted")
                                        ])
                                    ], className="table-option mb-2")
                                ], md=6),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "base2"},
                                                label="Base2",
                                                value=False,
                                                className="mb-2"
                                            ),
                                            html.Small("Dados complementares", className="text-muted")
                                        ])
                                    ], className="table-option mb-2")
                                ], md=6),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "pessoas"},
                                                label="Pessoas",
                                                value=False,
                                                className="mb-2"
                                            ),
                                            html.Small("Cadastro de pessoas", className="text-muted")
                                        ])
                                    ], className="table-option mb-2")
                                ], md=6),
                                dbc.Col([
                                    dbc.Card([
                                        dbc.CardBody([
                                            dbc.Checkbox(
                                                id={"type": "table-checkbox", "index": "ocorrencias"},
                                                label="Ocorrências",
                                                value=False,
                                                className="mb-2"
                                            ),
                                            html.Small("Registro de ocorrências", className="text-muted")
                                        ])
                                    ], className="table-option mb-2")
                                ], md=6)
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
            
            # Read CSV
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            
            # Create file info card
            file_info = dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-file-csv fa-2x text-success mb-2"),
                        html.H6(filename, className="mb-1"),
                        html.Small(f"{len(df)} linhas × {len(df.columns)} colunas", 
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
            
            return file_info, table_style, store_data, False
            
        except Exception as e:
            error_msg = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                f"Erro ao processar arquivo: {str(e)}"
            ], color="danger")
            return error_msg, {"display": "none"}, None, True
    
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
            {"label": "Base eShows", "value": "baseeshows"},
            {"label": "Base2", "value": "base2"},
            {"label": "Pessoas", "value": "pessoas"},
            {"label": "Ocorrências", "value": "ocorrencias"}
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
         State({"type": "table-checkbox", "index": ALL}, "id")],
        prevent_initial_call=True
    )
    def update_summary(style, store_data, upload_table, erp_checks, erp_ids):
        if style.get("display") == "none":
            raise PreventUpdate
        
        summary_items = []
        
        # Check if upload option
        if store_data and upload_table:
            summary_items.append(
                html.Div([
                    html.I(className="fas fa-upload text-primary me-2"),
                    html.Strong("Upload de arquivo: "),
                    html.Span(f"{store_data['filename']} → Tabela {upload_table}")
                ], className="mb-2")
            )
            
            # Preview table
            preview_df = pd.DataFrame(store_data['data']).head(5)
            preview = dbc.Table.from_dataframe(
                preview_df,
                striped=True,
                bordered=True,
                hover=True,
                responsive=True,
                className="mb-0"
            )
            
            return summary_items, preview, False
        
        # Check if ERP option
        selected_tables = []
        for i, checked in enumerate(erp_checks):
            if checked:
                table_name = erp_ids[i]["index"]
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
    
    # Callback para habilitar botão Próximo quando tabelas ERP são selecionadas
    @app.callback(
        Output("btn-next-update", "disabled", allow_duplicate=True),
        [Input({"type": "table-checkbox", "index": ALL}, "value")],
        prevent_initial_call=True
    )
    def toggle_next_button_erp(checkbox_values):
        # Habilita o botão se pelo menos uma checkbox estiver marcada
        return not any(checkbox_values)
    
    # Callback para processar a confirmação da atualização
    @app.callback(
        [Output("update-modal", "is_open", allow_duplicate=True),
         Output("alert-atualiza-base", "children"),
         Output("alert-atualiza-base", "color"),
         Output("alert-atualiza-base", "is_open")],
        [Input("btn-confirm-update", "n_clicks")],
        [State("update-store-data", "data"),
         State("table-select-upload", "value"),
         State({"type": "table-checkbox", "index": ALL}, "value"),
         State({"type": "table-checkbox", "index": ALL}, "id")],
        prevent_initial_call=True
    )
    def process_update_confirmation(n_clicks, store_data, upload_table, erp_checks, erp_ids):
        if not n_clicks:
            raise PreventUpdate
        
        try:
            # Opção 1: Upload de arquivo
            if store_data and upload_table:
                # TODO: Implementar upload para Supabase
                return False, "Upload de arquivo ainda não implementado", "warning", True
            
            # Opção 2: Atualização do ERP
            selected_tables = []
            for i, checked in enumerate(erp_checks):
                if checked:
                    table_name = erp_ids[i]["index"]
                    selected_tables.append(table_name)
            
            if selected_tables:
                # Importa e executa a atualização
                from app.data_manager import reload_tables
                
                results = reload_tables(selected_tables)
                
                # Prepara mensagem de resultado
                success_count = sum(1 for r in results.values() if r["status"] == "success")
                error_count = sum(1 for r in results.values() if r["status"] == "error")
                
                if error_count == 0:
                    message = f"✅ {success_count} tabela(s) atualizada(s) com sucesso!"
                    color = "success"
                elif success_count > 0:
                    message = f"⚠️ {success_count} tabela(s) atualizada(s), {error_count} com erro"
                    color = "warning"
                else:
                    message = f"❌ Erro ao atualizar {error_count} tabela(s)"
                    color = "danger"
                
                # Adiciona detalhes
                details = []
                for table, result in results.items():
                    if result["status"] == "success":
                        details.append(f"• {table}: {result['rows']} registros")
                    else:
                        details.append(f"• {table}: Erro - {result.get('error', 'Desconhecido')}")
                
                if details:
                    message += "\n\n" + "\n".join(details)
                
                # Fecha o modal e mostra o alerta
                return False, message, color, True
            
            return False, "Nenhuma tabela selecionada", "warning", True
            
        except Exception as e:
            logger.error(f"Erro ao processar atualização: {e}")
            return False, f"❌ Erro ao processar atualização: {str(e)}", "danger", True

    return True