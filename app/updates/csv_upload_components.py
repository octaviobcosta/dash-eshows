"""
Componentes para Upload de CSV
Interface melhorada com validação e preview interativo
"""

import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
import pandas as pd
from typing import Dict, List, Any
from app.updates.csv_validator import TABLE_SCHEMAS


def create_status_summary_card(validation_result: Dict[str, Any]) -> dbc.Card:
    """Cria card principal com resumo do status da validação"""
    
    can_proceed = validation_result.get("can_proceed", False)
    stats = validation_result.get("stats", {})
    errors = validation_result.get("errors", [])
    warnings = validation_result.get("warnings", [])
    
    # Determinar status e cores
    if can_proceed and not warnings:
        status_color = "#10b981"  # success
        status_icon = "fa-check-circle"
        status_text = "Pronto para importar"
        border_color = status_color
    elif can_proceed and warnings:
        status_color = "#f59e0b"  # warning
        status_icon = "fa-exclamation-circle"
        status_text = "Importação possível com avisos"
        border_color = status_color
    else:
        status_color = "#ef4444"  # danger
        status_icon = "fa-times-circle"
        status_text = "Correções necessárias"
        border_color = status_color
    
    return dbc.Card([
        dbc.CardBody([
            # Status header
            html.Div([
                html.I(className=f"fas {status_icon} fa-3x mb-3", 
                      style={"color": status_color}),
                html.H4(status_text, className="mb-3"),
                
                # Stats grid
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.H2(f"{stats.get('total_rows', 0):,}", 
                                   className="mb-0", style={"color": "#fc4f22"}),
                            html.Small("Linhas", className="text-muted")
                        ], className="text-center")
                    ], md=4),
                    dbc.Col([
                        html.Div([
                            html.H2(stats.get('total_columns', 0), 
                                   className="mb-0"),
                            html.Small("Colunas", className="text-muted")
                        ], className="text-center")
                    ], md=4),
                    dbc.Col([
                        html.Div([
                            html.H2(stats.get('memory_usage', '0KB'), 
                                   className="mb-0"),
                            html.Small("Tamanho", className="text-muted")
                        ], className="text-center")
                    ], md=4)
                ], className="mt-4"),
                
                # Error/Warning badges
                html.Div([
                    dbc.Badge([
                        html.I(className="fas fa-times me-1"),
                        f"{len(errors)} Erros"
                    ], color="danger" if errors else "secondary", 
                       className="me-2", pill=True),
                    dbc.Badge([
                        html.I(className="fas fa-exclamation me-1"),
                        f"{len(warnings)} Avisos"
                    ], color="warning" if warnings else "secondary", 
                       className="me-2", pill=True)
                ], className="mt-3")
            ], className="text-center")
        ])
    ], style={
        "borderTop": f"4px solid {border_color}",
        "boxShadow": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
    }, className="mb-4")


def create_issues_card(validation_result: Dict[str, Any]) -> dbc.Card:
    """Cria card compacto com erros e avisos"""
    
    errors = validation_result.get("errors", [])
    warnings = validation_result.get("warnings", [])
    
    items = []
    
    # Errors section
    if errors:
        items.append(html.H6("Erros", className="text-danger mb-2"))
        for error in errors[:3]:  # Show max 3 errors
            items.append(
                html.Div([
                    html.I(className="fas fa-times text-danger me-2"),
                    html.Small(error["message"])
                ], className="mb-2")
            )
        if len(errors) > 3:
            items.append(
                html.Small(f"... e {len(errors) - 3} outros erros", 
                          className="text-muted")
            )
    
    # Divider
    if errors and warnings:
        items.append(html.Hr(className="my-3"))
    
    # Warnings section
    if warnings:
        items.append(html.H6("Avisos", className="text-warning mb-2"))
        for warning in warnings[:3]:  # Show max 3 warnings
            items.append(
                html.Div([
                    html.I(className="fas fa-exclamation text-warning me-2"),
                    html.Small(warning["message"])
                ], className="mb-2")
            )
        if len(warnings) > 3:
            items.append(
                html.Small(f"... e {len(warnings) - 3} outros avisos", 
                          className="text-muted")
            )
    
    return dbc.Card([
        dbc.CardBody(items)
    ], className="mb-3", style={"backgroundColor": "#fef2f2"})


def create_column_status_card(validation_result: Dict[str, Any], table_schema: Dict) -> dbc.Card:
    """Cria card compacto mostrando status das colunas"""
    
    # Extrair informações
    csv_columns = set(validation_result.get("stats", {}).get("column_stats", {}).keys())
    essential = set(table_schema.get("essential_columns", []))
    required = set(table_schema.get("required_columns", []))
    auto_generated = set(table_schema.get("auto_generated", []))
    column_mapping = validation_result.get("column_mapping", {})
    default_values = validation_result.get("default_values", {})
    
    # Contar status
    found_essential = len(essential & csv_columns)
    total_essential = len(essential)
    found_required = len((required & csv_columns) - essential)
    total_required = len(required - essential)
    
    # Build compact summary
    summary_items = []
    
    # Essential columns summary
    if essential:
        color = "success" if found_essential == total_essential else "danger"
        summary_items.append(
            html.Div([
                html.Span(f"{found_essential}/{total_essential}", 
                         className=f"fw-bold text-{color} me-2"),
                html.Span("Colunas essenciais", className="text-muted")
            ], className="mb-2")
        )
    
    # Required columns summary
    if required - essential:
        color = "success" if found_required == total_required else "warning"
        summary_items.append(
            html.Div([
                html.Span(f"{found_required}/{total_required}", 
                         className=f"fw-bold text-{color} me-2"),
                html.Span("Colunas recomendadas", className="text-muted")
            ], className="mb-2")
        )
    
    # Mapping count
    if column_mapping:
        summary_items.append(
            html.Div([
                html.Span(f"{len(column_mapping)}", 
                         className="fw-bold text-info me-2"),
                html.Span("Mapeamentos automáticos", className="text-muted")
            ], className="mb-2")
        )
    
    return dbc.Card([
        dbc.CardBody([
            html.H6([
                html.I(className="fas fa-columns me-2"),
                "Status das Colunas"
            ], className="mb-3"),
            *summary_items,
            html.Hr(className="my-3"),
            dbc.Button([
                html.I(className="fas fa-edit me-2"),
                "Editar Mapeamentos"
            ], id="edit-mappings-btn", size="sm", color="link", 
               className="p-0", style={"color": "#fc4f22"})
        ])
    ], className="mb-3", style={"borderLeft": "3px solid #fc4f22"})


def create_validation_report(validation_result: Dict[str, Any]) -> html.Div:
    """Cria um relatório visual dos resultados da validação"""
    
    components = []
    
    # Status Summary Card
    components.append(create_status_summary_card(validation_result))
    
    # Column Status Card (simplified)
    table_schema = TABLE_SCHEMAS.get(validation_result.get("table_name", ""), {})
    if table_schema:
        components.append(create_column_status_card(validation_result, table_schema))
    
    # Errors and Warnings in a single compact card
    if validation_result["errors"] or validation_result["warnings"]:
        components.append(create_issues_card(validation_result))
    
    return html.Div(components)


def create_preview_table(preview_data: Dict[str, Any], show_problems: bool = True, 
                        show_converted: bool = False, table_name: str = None) -> html.Div:
    """Cria uma tabela de preview com dados convertidos/formatados como serão salvos"""
    
    df = pd.DataFrame(preview_data["data"])
    problem_cells = preview_data.get("problem_cells", {})
    
    # Apply data conversion if requested
    if show_converted and table_name:
        df = apply_preview_conversions(df, table_name)
    
    # Format numeric columns for display
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64']:
            # Check if it's a monetary column
            if any(term in col.lower() for term in ['valor', 'gmv', 'fat', 'receita', 'custo']):
                if show_converted:
                    # Show as cents
                    df[col] = df[col].apply(lambda x: f"{int(x):,} cents" if pd.notna(x) else "")
                else:
                    # Show as currency
                    df[col] = df[col].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "")
    
    # Configure column display
    columns = []
    for col in df.columns:
        col_config = {"name": col, "id": col}
        
        # Add type indicators to column headers
        if show_converted:
            col_type = get_column_type_indicator(col, table_name)
            if col_type:
                col_config["name"] = f"{col} ({col_type})"
        
        columns.append(col_config)
    
    # Configurar estilos condicionais
    style_conditions = []
    
    if show_problems and problem_cells:
        for col, rows in problem_cells.items():
            for row in rows:
                style_conditions.append({
                    'if': {'row_index': row, 'column_id': col},
                    'backgroundColor': '#fee2e2',
                    'color': '#991b1b',
                })
    
    # Add conversion highlights if showing converted data
    if show_converted:
        # Highlight monetary columns
        for col in df.columns:
            if any(term in col.lower() for term in ['valor', 'gmv', 'fat', 'receita', 'custo']):
                style_conditions.append({
                    'if': {'column_id': col},
                    'backgroundColor': '#fef3c7',
                })
    
    # Criar tabela
    table = dash_table.DataTable(
        id='preview-table',
        columns=columns,
        data=df.to_dict('records'),
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'whiteSpace': 'normal',
            'height': 'auto',
            'fontSize': '13px',
            'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        },
        style_data_conditional=style_conditions,
        style_header={
            'backgroundColor': '#f9fafb',
            'fontWeight': 'bold',
            'border': '1px solid #e5e7eb',
            'color': '#374151'
        },
        style_table={
            'overflowX': 'auto',
            'border': '1px solid #e5e7eb',
            'borderRadius': '8px'
        },
        style_data={
            'border': '1px solid #e5e7eb',
            'color': '#1f2937'
        },
        page_size=10,
        style_as_list_view=False,
        export_format='csv',
        export_headers='display'
    )
    
    # Create info text
    info_text = []
    if show_converted:
        info_text.append(
            html.Div([
                html.I(className="fas fa-info-circle me-2", style={"color": "#fc4f22"}),
                html.Span("Dados como serão salvos no banco:", className="fw-bold me-2"),
                html.Span("Valores monetários em centavos, datas formatadas", 
                         className="text-muted")
            ], className="mb-2")
        )
    
    if problem_cells:
        info_text.append(
            html.Small(
                "Células com fundo vermelho indicam problemas detectados",
                className="text-muted d-block"
            )
        )
    
    return html.Div([
        html.Div([
            html.H6([
                html.I(className="fas fa-eye me-2"),
                "Preview dos Dados"
            ], className="mb-3"),
            *info_text
        ]),
        table,
        # Toggle button
        html.Div([
            dbc.Button([
                html.I(className="fas fa-exchange-alt me-2"),
                "Alternar Vista" if show_converted else "Ver Dados Convertidos"
            ], id="toggle-preview-view", size="sm", color="link", 
               className="mt-2", style={"color": "#fc4f22"})
        ])
    ])


def apply_preview_conversions(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Apply conversions to show data as it will be saved"""
    # Import here to avoid circular import
    from app.update_modal_improved import brl_to_cents
    
    df_converted = df.copy()
    
    # Get table schema
    schema = TABLE_SCHEMAS.get(table_name, {})
    numeric_cols = schema.get("numeric_columns", [])
    date_cols = schema.get("date_columns", [])
    
    # Convert monetary columns to cents
    for col in df_converted.columns:
        if col in numeric_cols or any(term in col.lower() for term in ['valor', 'gmv', 'fat', 'receita', 'custo']):
            if df_converted[col].dtype == 'object':
                df_converted[col] = df_converted[col].apply(brl_to_cents)
    
    # Format date columns
    for col in date_cols:
        if col in df_converted.columns:
            df_converted[col] = pd.to_datetime(df_converted[col], errors='coerce').dt.strftime('%Y-%m-%d')
    
    return df_converted


def get_column_type_indicator(col: str, table_name: str) -> str:
    """Return type indicator for column"""
    schema = TABLE_SCHEMAS.get(table_name, {})
    
    if col in schema.get("numeric_columns", []):
        if any(term in col.lower() for term in ['valor', 'gmv', 'fat', 'receita', 'custo']):
            return "centavos"
        return "número"
    elif col in schema.get("date_columns", []):
        return "data"
    elif col in schema.get("auto_generated", []):
        return "auto"
    
    return ""


def create_column_mapping_interface(csv_columns: List[str], 
                                  table_columns: List[str], 
                                  suggested_mapping: Dict[str, str],
                                  table_schema: Dict = None) -> html.Div:
    """Cria interface moderna para mapeamento de colunas"""
    
    # Get schema info
    essential_cols = set(table_schema.get("essential_columns", [])) if table_schema else set()
    required_cols = set(table_schema.get("required_columns", [])) if table_schema else set()
    
    mapping_rows = []
    
    for csv_col in csv_columns:
        suggested = suggested_mapping.get(csv_col, "")
        
        # Determine if this mapping is for an essential/required column
        is_essential = suggested in essential_cols
        is_required = suggested in required_cols
        
        # Create status badge
        status_badge = None
        if is_essential:
            status_badge = dbc.Badge("Essencial", color="danger", pill=True, className="ms-2")
        elif is_required:
            status_badge = dbc.Badge("Recomendada", color="warning", pill=True, className="ms-2")
        
        mapping_rows.append(
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Small("Coluna no CSV", className="text-muted d-block"),
                                html.Div([
                                    html.Span(csv_col, className="fw-bold"),
                                    status_badge
                                ])
                            ])
                        ], md=5),
                        dbc.Col([
                            html.I(className="fas fa-arrow-right", 
                                  style={"color": "#fc4f22", "fontSize": "1.2rem"})
                        ], md=2, className="text-center align-self-center"),
                        dbc.Col([
                            html.Div([
                                html.Small("Mapear para", className="text-muted d-block mb-1"),
                                dbc.Select(
                                    id={"type": "column-mapping", "csv_column": csv_col},
                                    options=[
                                        {"label": "-- Ignorar esta coluna --", "value": ""},
                                        *[{"label": tc, "value": tc} for tc in table_columns]
                                    ],
                                    value=suggested,
                                    size="sm",
                                    style={"borderColor": "#fc4f22" if suggested else "#e5e7eb"}
                                )
                            ])
                        ], md=5)
                    ], className="align-items-center")
                ], className="py-2")
            ], className="mb-2", style={"border": "1px solid #e5e7eb"})
        )
    
    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.H6([
                        html.I(className="fas fa-random me-2"),
                        "Mapeamento de Colunas"
                    ], className="mb-1"),
                    html.P(
                        "Ajuste como as colunas do CSV correspondem às colunas da tabela",
                        className="text-muted small mb-4"
                    ),
                ], className="mb-3"),
                
                # Quick stats
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Span(f"{len([m for m in suggested_mapping.values() if m])}/{len(csv_columns)}", 
                                     className="fw-bold", style={"color": "#fc4f22"}),
                            html.Span(" colunas mapeadas", className="text-muted ms-1")
                        ], className="text-center")
                    ], md=6),
                    dbc.Col([
                        html.Div([
                            html.Span(f"{len(csv_columns) - len([m for m in suggested_mapping.values() if m])}", 
                                     className="fw-bold"),
                            html.Span(" ignoradas", className="text-muted ms-1")
                        ], className="text-center")
                    ], md=6)
                ], className="mb-4"),
                
                html.Hr(className="my-3"),
                
                # Mapping cards
                html.Div(mapping_rows, style={"maxHeight": "400px", "overflowY": "auto"}),
                
                html.Hr(className="my-3"),
                
                # Actions
                dbc.Row([
                    dbc.Col([
                        dbc.Button([
                            html.I(className="fas fa-magic me-2"),
                            "Aplicar Sugestões Automáticas"
                        ], id="reset-mapping-btn", color="link", size="sm", 
                           style={"color": "#fc4f22"})
                    ]),
                    dbc.Col([
                        dbc.Button([
                            html.I(className="fas fa-check me-2"),
                            "Confirmar Mapeamento"
                        ], id="confirm-mapping-btn", color="primary", size="sm",
                           style={"backgroundColor": "#fc4f22", "borderColor": "#fc4f22"},
                           className="float-end")
                    ])
                ])
            ])
        ], style={"borderTop": "3px solid #fc4f22"})
    ])


def create_upload_options_card() -> dbc.Card:
    """Cria card com opções de upload"""
    
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-cog me-2"),
            "Opções de Upload"
        ]),
        dbc.CardBody([
            html.Div([
                html.H6("Modo de Inserção:", className="mb-3"),
                dbc.RadioItems(
                    id="upload-mode",
                    options=[
                        {
                            "label": [
                                html.I(className="fas fa-trash-alt me-2 text-danger"),
                                html.Span("Substituir todos os dados", className="fw-bold"),
                                html.Br(),
                                html.Small("Remove todos os dados existentes e insere os novos", 
                                         className="text-muted")
                            ],
                            "value": "replace"
                        },
                        {
                            "label": [
                                html.I(className="fas fa-plus-circle me-2 text-success"),
                                html.Span("Adicionar aos existentes", className="fw-bold"),
                                html.Br(),
                                html.Small("Mantém dados existentes e adiciona os novos", 
                                         className="text-muted")
                            ],
                            "value": "append"
                        },
                        {
                            "label": [
                                html.I(className="fas fa-sync-alt me-2 text-info"),
                                html.Span("Atualizar e adicionar", className="fw-bold"),
                                html.Br(),
                                html.Small("Atualiza registros existentes e adiciona novos", 
                                         className="text-muted")
                            ],
                            "value": "upsert"
                        }
                    ],
                    value="replace",
                    className="mb-4"
                )
            ]),
            
            html.Hr(),
            
            html.Div([
                html.H6("Tratamento de Erros:", className="mb-3"),
                dbc.RadioItems(
                    id="error-handling",
                    options=[
                        {
                            "label": [
                                html.I(className="fas fa-stop-circle me-2"),
                                "Parar no primeiro erro"
                            ],
                            "value": "stop"
                        },
                        {
                            "label": [
                                html.I(className="fas fa-forward me-2"),
                                "Continuar e reportar erros no final"
                            ],
                            "value": "continue"
                        }
                    ],
                    value="stop",
                    inline=True
                )
            ])
        ])
    ])


def create_upload_summary(filename: str, table_name: str, 
                         row_count: int, mode: str,
                         validation_result: Dict[str, Any]) -> html.Div:
    """Cria resumo final antes da confirmação do upload"""
    
    mode_labels = {
        "replace": "Substituir todos os dados",
        "append": "Adicionar aos existentes",
        "upsert": "Atualizar e adicionar"
    }
    
    return html.Div([
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-file-upload me-2"),
                "Resumo do Upload"
            ]),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Small("Arquivo:", className="text-muted"),
                        html.Div(filename, className="fw-bold")
                    ], md=6),
                    dbc.Col([
                        html.Small("Tabela de Destino:", className="text-muted"),
                        html.Div(table_name.upper(), className="fw-bold")
                    ], md=6)
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col([
                        html.Small("Registros a Processar:", className="text-muted"),
                        html.Div(f"{row_count:,}", className="fw-bold text-primary")
                    ], md=6),
                    dbc.Col([
                        html.Small("Modo de Upload:", className="text-muted"),
                        html.Div(mode_labels[mode], className="fw-bold")
                    ], md=6)
                ], className="mb-3"),
                
                # Status da validação
                html.Hr(),
                html.Div([
                    html.I(
                        className="fas fa-check-circle me-2 text-success" 
                        if validation_result["valid"] 
                        else "fas fa-times-circle me-2 text-danger"
                    ),
                    html.Strong(
                        "Validação: Aprovado" 
                        if validation_result["valid"] 
                        else f"Validação: {len(validation_result['errors'])} erro(s)"
                    )
                ])
            ])
        ], className="mb-3"),
        
        # Aviso final
        dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            html.Strong("Atenção: "),
            f"Esta ação {'substituirá TODOS os dados existentes' if mode == 'replace' else 'modificará os dados existentes'} na tabela {table_name.upper()}. Esta operação não pode ser desfeita!"
        ], color="warning" if mode == "replace" else "info")
    ])