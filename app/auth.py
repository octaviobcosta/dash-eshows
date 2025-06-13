import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from flask import session, redirect
from supabase import create_client, Client
import logging

# Logger
logger = logging.getLogger(__name__)

# Configurações
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Configuração do Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Criar cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def verify_password(plain_password, hashed_password):
    """Verifica se a senha está correta"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(user_data: dict):
    """Cria um token JWT"""
    to_encode = {
        "sub": user_data['email'],
        "nome": user_data['nome'],
        "id": user_data['id']
    }
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Verifica e decodifica um token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def authenticate_user(email: str, password: str):
    """Autentica um usuário usando Supabase"""
    if not supabase:
        logger.error("Cliente Supabase não configurado")
        return None
    
    try:
        # Busca o usuário pelo email
        result = supabase.table('senhasdash').select("*").eq('email', email).eq('ativo', True).execute()
        
        if not result.data or len(result.data) == 0:
            logger.warning(f"Usuário não encontrado ou inativo: {email}")
            return None
        
        user = result.data[0]
        
        # Verifica a senha
        if verify_password(password, user['senha_hash']):
            # Atualiza o último acesso
            try:
                supabase.table('senhasdash').update({
                    'ultimo_acesso': datetime.now().isoformat()
                }).eq('email', email).execute()
            except Exception as e:
                logger.error(f"Erro ao atualizar último acesso: {e}")
            
            return {
                'email': user['email'],
                'nome': user['nome'],
                'id': user['id']
            }
        else:
            logger.warning(f"Senha incorreta para: {email}")
            return None
            
    except Exception as e:
        logger.error(f"Erro ao autenticar usuário: {e}")
        return None

def require_auth(f):
    """Decorator para proteger rotas que requerem autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = session.get('access_token')
        if not token:
            return redirect('/login')
        
        user_data = verify_token(token)
        if not user_data:
            session.pop('access_token', None)
            return redirect('/login')
        
        return f(*args, **kwargs)
    return decorated_function

def create_login_layout():
    """Cria o layout da página de login com design moderno"""
    return html.Div([
        # Link para o CSS de login
        html.Link(href='/assets/login.css', rel='stylesheet'),
        
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        # Logo
                        html.Div([
                            html.Img(
                                src="/assets/logo.png",
                                className="login-logo",
                                alt="eShows Logo"
                            ),
                        ], className="text-center"),
                        
                        # Títulos
                        html.H1("Dashboard Gerencial", className="login-title text-center"),
                        html.P("Acesso Executivo", className="login-subtitle text-center"),
                        
                        # Card de Login
                        dbc.Card([
                            dbc.CardBody([
                                dbc.Form([
                                    # Campo Usuário
                                    dbc.Row([
                                        dbc.Label("Email", html_for="username", className="login-label"),
                                        dbc.Input(
                                            type="email",
                                            id="username",
                                            placeholder="seu.email@eshows.com.br",
                                            className="mb-3 login-input",
                                            autoFocus=True,
                                        ),
                                    ]),
                                    
                                    # Campo Senha
                                    dbc.Row([
                                        dbc.Label("Senha", html_for="password", className="login-label"),
                                        dbc.Input(
                                            type="password",
                                            id="password",
                                            placeholder="Sua senha",
                                            className="mb-2 login-input",
                                        ),
                                        html.Div(id="caps-lock-warning"),
                                    ]),
                                    
                                    # Checkbox Lembrar-me
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Checklist(
                                                options=[{"label": " Lembrar-me", "value": 1}],
                                                value=[],
                                                id="remember-me",
                                                className="login-checkbox mb-3",
                                            ),
                                        ]),
                                    ]),
                                    
                                    # Botão de Login
                                    dbc.Button(
                                        "Entrar",
                                        id="login-button",
                                        className="w-100 login-button",
                                        n_clicks=0,
                                    ),
                                ]),
                                
                                # Feedback de Login
                                html.Div(id="login-feedback", className="mt-3"),
                                
                                # Footer
                                html.Div([
                                    html.P(
                                        "© 2025 eShows | Versão 1.0",
                                        className="mb-0"
                                    )
                                ], className="login-footer"),
                            ])
                        ], className="login-card"),
                    ], className="login-form-container")
                ], width={"size": 10, "offset": 1}, md={"size": 6, "offset": 3}, lg={"size": 4, "offset": 4}),
            ], className="vh-100 align-items-center"),
        ], fluid=True),
    ], className="login-container")

def init_auth_callbacks(app):
    """Inicializa os callbacks de autenticação"""
    
    @app.callback(
        [Output('login-feedback', 'children'),
         Output('url', 'pathname'),
         Output('login-button', 'className')],
        [Input('login-button', 'n_clicks'),
         Input('password', 'n_submit')],
        [State('username', 'value'),
         State('password', 'value'),
         State('remember-me', 'value')],
        prevent_initial_call=True
    )
    def login(n_clicks, n_submit, username, password, remember_me):
        ctx = dash.callback_context
        if not ctx.triggered:
            return "", dash.no_update, "w-100 login-button"
        
        # Adiciona classe loading ao botão
        if not username or not password:
            return dbc.Alert(
                "Por favor, preencha todos os campos.",
                color="warning", 
                className="login-alert"
            ), dash.no_update, "w-100 login-button"
        
        user_data = authenticate_user(username, password)
        if user_data:
            # Criar token e salvar na sessão
            access_token = create_access_token(user_data)
            session['access_token'] = access_token
            session['username'] = user_data['email']
            session['user_nome'] = user_data['nome']
            session['user_id'] = user_data['id']
            
            # Se "Lembrar-me" estiver marcado, aumenta a duração da sessão
            if remember_me:
                session.permanent = True
            
            return dbc.Alert(
                f"Bem-vindo, {user_data['nome']}!",
                color="success", 
                className="login-alert"
            ), "/dashboard", "w-100 login-button"
        else:
            return dbc.Alert(
                "Email ou senha incorretos.",
                color="danger", 
                className="login-alert"
            ), dash.no_update, "w-100 login-button"
    
    # Callback para detectar Caps Lock
    @app.callback(
        Output('caps-lock-warning', 'children'),
        [Input('password', 'id')],
        prevent_initial_call=True
    )
    def check_caps_lock(_):
        # Este callback é apenas para criar o componente
        # A detecção real de Caps Lock seria feita via JavaScript
        return html.Div()

def add_logout_button(navbar_children):
    """Adiciona botão de logout ao navbar"""
    if 'username' in session:
        logout_button = dbc.NavItem([
            dbc.Row([
                dbc.Col(html.Span(f"Olá, {session['username']}", className="navbar-text me-3")),
                dbc.Col(dbc.Button("Sair", id="logout-button", color="light", size="sm", outline=True)),
            ], className="align-items-center g-0")
        ], className="ms-auto")
        
        if isinstance(navbar_children, list):
            navbar_children.append(logout_button)
        else:
            navbar_children = [navbar_children, logout_button]
    
    return navbar_children

def init_logout_callback(app):
    """Inicializa callback de logout"""
    # O logout já é tratado na função render_page_content quando pathname == '/logout'
    # Esta função pode ser usada para callbacks adicionais se necessário
    pass

def init_client_side_callbacks(app):
    """Inicializa callbacks client-side para melhor performance"""
    # Detecção de Caps Lock via JavaScript
    app.clientside_callback(
        """
        function(id) {
            document.getElementById('password').addEventListener('keyup', function(event) {
                const capsLockOn = event.getModifierState('CapsLock');
                const warningDiv = document.getElementById('caps-lock-warning');
                
                if (capsLockOn) {
                    warningDiv.innerHTML = '<div class="caps-lock-warning"><i class="fas fa-exclamation-circle"></i> Caps Lock está ativado</div>';
                } else {
                    warningDiv.innerHTML = '';
                }
            });
            
            // Foco automático no campo usuário
            const usernameField = document.getElementById('username');
            if (usernameField) {
                usernameField.focus();
            }
            
            return window.dash_clientside.no_update;
        }
        """,
        Output('caps-lock-warning', 'id'),
        Input('password', 'id')
    )