"""
Sistema de autenticação melhorado com design moderno
Baseado no login.py com glassmorphism e micro-interações
"""

import os
import jwt
import logging
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, request
import dash
from dash import dcc, html, Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from app import data_manager

logger = logging.getLogger(__name__)

# Configurações JWT
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-here')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Design tokens
COLORS = {
    'primary': '#fc4f22',
    'primary_hover': '#e84318', 
    'secondary': '#fdb03d',
    'glass_bg': 'rgba(255, 255, 255, 0.1)',
    'glass_border': 'rgba(255, 255, 255, 0.2)',
    'text_light': 'rgba(255, 255, 255, 0.9)'
}

def check_password(plain_password, user_data):
    """Verifica se a senha está correta"""
    # Usar apenas senha_hash já que password não existe na tabela
    stored_password = user_data.get('senha_hash', '')
    
    if not stored_password:
        logger.error("Nenhuma senha encontrada para o usuário")
        return False
    
    # Se a senha armazenada começa com $2b$, é um hash bcrypt
    if stored_password.startswith('$2b$'):
        # Verificar com bcrypt
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), stored_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Erro ao verificar senha bcrypt: {e}")
            return False
    else:
        # Comparação direta (para senhas antigas não hasheadas)
        return plain_password == stored_password

def create_jwt_token(username):
    """Cria um token JWT"""
    payload = {
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def verify_jwt_token(token):
    """Verifica e decodifica um token JWT"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload['username']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def authenticate_user(username, password):
    """Autentica um usuário usando Supabase"""
    try:
        # Buscar usuário no Supabase
        logger.info(f"Tentando autenticar usuário: {username}")
        
        # Debug - verificar se session está disponível
        logger.info(f"Session disponível: {session is not None}")
        logger.info(f"Session keys antes do login: {list(session.keys()) if session else 'None'}")
        
        # Query direto ao Supabase
        supabase = data_manager.supa
        if not supabase:
            logger.error("Cliente Supabase não inicializado")
            return False, "Erro de conexão com o banco de dados"
        
        # Buscar na tabela senhasdash
        response = supabase.table('senhasdash').select("*").eq('email', username).execute()
        
        if not response.data:
            logger.warning(f"Usuário não encontrado: {username}")
            return False, "Usuário ou senha incorretos"
        
        user_data = response.data[0]
        
        # Verificar senha
        logger.info(f"Verificando senha para usuário: {username}")
        logger.info(f"Dados do usuário: senha_hash={bool(user_data.get('senha_hash'))}")
        
        if not check_password(password, user_data):
            logger.warning(f"Senha incorreta para usuário: {username}")
            return False, "Usuário ou senha incorretos"
        
        # Criar token JWT
        token = create_jwt_token(username)
        
        # Salvar na sessão
        session['username'] = username
        session['access_token'] = token
        session.permanent = True  # Tornar a sessão persistente
        
        # Debug - verificar se salvou na session
        logger.info(f"Session keys após login: {list(session.keys())}")
        logger.info(f"Usuário autenticado com sucesso: {username}")
        return True, "Login realizado com sucesso!"
        
    except Exception as e:
        logger.error(f"Erro na autenticação: {str(e)}")
        return False, f"Erro ao autenticar: {str(e)}"

def require_auth(f):
    """Decorator para proteger rotas que requerem autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            return redirect('/login')
        
        # Verificar validade do token
        username = verify_jwt_token(session['access_token'])
        if not username:
            session.clear()
            return redirect('/login')
        
        return f(*args, **kwargs)
    return decorated_function

def create_login_layout():
    """Cria o layout da página de login com design moderno baseado no login.py"""
    return html.Div([
        # Location para redirecionamento
        dcc.Location(id='login-redirect', refresh=True),
        
        # Stores para gerenciar estado
        dcc.Store(id='password-visibility', data={'visible': False}),
        dcc.Store(id='forgot-status', data=''),
        dcc.Store(id='modal-state', data={'show': False}),
        
        # Loader profissional
        html.Div([
            html.Div([
                html.Img(
                    src="/assets/logoB.png",
                    className="loader-logo"
                ),
                html.Div(className="loader-spinner")
            ], className="loader-content")
        ], id="login-loader", className="login-loader"),
        
        # Background container
        html.Div([
            html.Img(
                src="/assets/login.png",
                style={
                    "position": "absolute",
                    "top": 0,
                    "left": 0,
                    "width": "100%",
                    "height": "100%",
                    "objectFit": "cover",
                    "opacity": 1,
                    "zIndex": 0
                }
            )
        ], className="login-bg-container"),
        
        # Main container
        html.Div([
            # Login card with glassmorphism
            html.Div([
                # Logo
                html.Div([
                    html.Img(
                        src="/assets/logoB.png",
                        className="login-logo",
                        style={"width": "100px", "height": "auto"}
                    )
                ], className="login-logo-container text-center mb-4"),
                
                # Title
                html.H2("Bem-vindo de volta", className="login-title"),
                html.P("Acesso Executivo", className="login-subtitle"),
                
                # Alert placeholder
                html.Div(id="login-alert-placeholder"),
                
                # Login form
                html.Form([
                    # Email field
                    html.Div([
                        dbc.Label("E-mail", className="login-label"),
                        html.Div([
                            html.I(className="fas fa-envelope input-icon"),
                            dbc.Input(
                                type="email",
                                id="login-username",
                                placeholder="seu@email.com",
                                className="login-input-glass",
                                required=True,
                                style={"paddingLeft": "44px"}
                            )
                        ], className="input-group-glass")
                    ], className="form-group-glass"),
                    
                    # Password field
                    html.Div([
                        dbc.Label("Senha", className="login-label"),
                        html.Div([
                            html.I(className="fas fa-lock input-icon"),
                            dbc.Input(
                                type="password",
                                id="login-password",
                                placeholder="••••••••",
                                className="login-input-glass",
                                required=True,
                                style={"paddingLeft": "44px"}
                            ),
                            html.Span(
                                id="caps-lock-warning",
                                className="caps-lock-indicator",
                                children=[
                                    html.I(className="fas fa-exclamation-triangle me-1"),
                                    "Caps Lock"
                                ]
                            )
                        ], className="input-group-glass")
                    ], className="form-group-glass"),
                    
                    # Remember me checkbox
                    html.Div([
                        dbc.Checkbox(
                            id="remember-me",
                            label="Lembrar-me",
                            value=False,
                            className="form-check-glass"
                        )
                    ], className="mb-3"),
                    
                    # Submit button
                    dbc.Button(
                        [
                            html.Span("Entrar", id="login-btn-text"),
                            dbc.Spinner(
                                size="sm",
                                id="login-spinner",
                                spinner_style={"display": "none", "marginLeft": "0.5rem"}
                            )
                        ],
                        id="login-button",
                        color="primary",
                        className="login-button-glass w-100",
                        n_clicks=0,
                        type="button"  # Mudado de submit para button para evitar refresh do form
                    ),
                    
                    # Forgot password link
                    html.Div([
                        html.A(
                            "Esqueceu sua senha?",
                            href="#",
                            id="forgot-password-link",
                            className="login-link",
                            n_clicks=0
                        )
                    ], className="text-center mt-3")
                ], id="login-form")
            ], className="login-card-glass")
        ], className="login-container", style={
            "position": "fixed",
            "top": 0,
            "left": 0,
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center"
        }),
        
        # Modal de recuperação de senha
        html.Div([
            html.Div([
                html.Div([
                    html.H3("Recuperar Senha", className="modal-title-glass"),
                    html.Button(
                        html.I(className="fas fa-times"),
                        id="modal-close-btn",
                        className="modal-close-glass",
                        n_clicks=0
                    )
                ], className="modal-header-glass"),
                
                html.Div([
                    html.I(className="fas fa-lock")
                ], className="modal-icon-glass"),
                
                html.Div([
                    html.P("Para recuperar sua senha, entre em contato com o administrador do sistema:"),
                    html.Div([
                        html.P([
                            html.I(className="fas fa-envelope me-2"),
                            "Email: ",
                            html.A("octavio@eshows.com.br", href="mailto:octavio@eshows.com.br")
                        ])
                    ], className="contact-info-glass"),
                    html.P("Informe seu email de acesso e solicite uma nova senha.", style={"fontSize": "13px", "opacity": "0.8"})
                ], className="modal-body-glass")
            ], className="modal-content-glass")
        ], id="forgot-password-modal", className="forgot-password-modal")
    ], className="login-page", style={
        "position": "fixed",
        "top": 0,
        "left": 0,
        "width": "100%",
        "height": "100%",
        "margin": 0,
        "padding": 0
    })

def init_auth_callbacks(app):
    """Inicializa os callbacks de autenticação"""
    
    @app.callback(
        [Output("login-alert-placeholder", "children"),
         Output("login-button", "disabled"),
         Output("login-spinner", "spinner_style"),
         Output("login-btn-text", "children"),
         Output("login-redirect", "href")],  # Mudado de pathname para href
        [Input("login-button", "n_clicks")],
        [State("login-username", "value"),
         State("login-password", "value"),
         State("remember-me", "value")],
        prevent_initial_call=True
    )
    def handle_login(n_clicks, username, password, remember_me):
        if n_clicks == 0:
            raise PreventUpdate
        
        # Mostrar loading
        loading_style = {"display": "inline-block", "marginLeft": "0.5rem"}
        
        if not username or not password:
            alert = dbc.Alert(
                [
                    html.I(className="fas fa-exclamation-circle me-2"),
                    "Por favor, preencha todos os campos"
                ],
                color="danger",
                className="alert-glass alert-danger",
                dismissable=True
            )
            return alert, False, {"display": "none"}, "Entrar", dash.no_update
        
        # Autenticar
        success, message = authenticate_user(username, password)
        
        if success:
            alert = dbc.Alert(
                [
                    html.I(className="fas fa-check-circle me-2"),
                    message
                ],
                color="success",
                className="alert-glass alert-success"
            )
            # Redirecionar para dashboard
            return alert, True, {"display": "none"}, "Redirecionando...", "/dashboard"
        else:
            alert = dbc.Alert(
                [
                    html.I(className="fas fa-times-circle me-2"),
                    message
                ],
                color="danger",
                className="alert-glass alert-danger",
                dismissable=True
            )
            return alert, False, {"display": "none"}, "Entrar", dash.no_update
    
    # Callback para detectar Caps Lock
    @app.callback(
        Output("caps-lock-warning", "className"),
        [Input("login-password", "value")],
        prevent_initial_call=True
    )
    def check_caps_lock(value):
        # Este callback seria melhor implementado com JavaScript
        # Por ora, mantemos oculto
        return "caps-lock-indicator"
    
    # Callback para modal de recuperação de senha
    @app.callback(
        Output("forgot-password-modal", "className"),
        [Input("forgot-password-link", "n_clicks"),
         Input("modal-close-btn", "n_clicks")],
        [State("forgot-password-modal", "className")],
        prevent_initial_call=True
    )
    def toggle_forgot_modal(link_clicks, close_clicks, current_class):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
            
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if trigger_id == "forgot-password-link" and link_clicks > 0:
            return "forgot-password-modal show"
        elif trigger_id == "modal-close-btn":
            return "forgot-password-modal"
            
        return current_class

def init_logout_callback(app):
    """Inicializa callback de logout"""
    
    @app.callback(
        Output('logout-redirect', 'pathname'),
        [Input('logout-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def logout(n_clicks):
        if n_clicks:
            session.clear()
            return '/login'
        raise PreventUpdate

def init_client_side_callbacks(app):
    """Inicializa callbacks client-side para melhor performance"""
    # Callback JavaScript para remover o loader após carregamento
    app.clientside_callback(
        """
        function(pathname) {
            setTimeout(function() {
                var loader = document.getElementById('login-loader');
                if (loader) {
                    loader.classList.add('fade-out');
                    setTimeout(function() {
                        loader.style.display = 'none';
                    }, 500);
                }
            }, 800);
            return window.dash_clientside.no_update;
        }
        """,
        Output('login-loader', 'style'),
        Input('login-redirect', 'pathname')
    )

def add_logout_button():
    """Retorna um botão de logout estilizado"""
    return dbc.Button(
        [
            html.I(className="fas fa-sign-out-alt me-2"),
            "Sair"
        ],
        id="logout-button",
        color="danger",
        outline=True,
        size="sm",
        className="ms-auto"
    )