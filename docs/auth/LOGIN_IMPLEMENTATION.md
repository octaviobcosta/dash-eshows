# Sistema de Login - Dashboard eShows

## O que foi implementado

1. **Módulo de Autenticação** (`app/auth.py`)
   - Sistema de login usando JWT e bcrypt
   - Layout responsivo com dash-bootstrap-components
   - Validação de credenciais com hash seguro
   - Gerenciamento de sessão Flask

2. **Integração no Dashboard** (`app/main.py`)
   - Proteção de todas as rotas
   - Redirecionamento automático para login
   - Botão de logout já existente na sidebar
   - Sessão persistente com tokens JWT

3. **Utilitário de Senha** (`app/scripts/generate_password_hash.py`)
   - Script para gerar hash de senhas
   - Verificação automática do hash gerado

## Como testar

### 1. Ativar ambiente virtual e instalar dependências
```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

# Verificar se as dependências estão instaladas
pip install -r requirements.txt
```

### 2. Configurar credenciais (já configurado para teste)
O arquivo `.env` já está configurado com:
- Usuário: `admin`
- Senha: `admin123`

### 3. Executar a aplicação
```bash
python -m app.main
```

### 4. Acessar o dashboard
1. Abra o navegador em: http://localhost:8050
2. Você será redirecionado para `/login`
3. Use as credenciais de teste:
   - Usuário: `admin`
   - Senha: `admin123`

## Fluxo de autenticação

1. **Login**: `/login`
   - Formulário com validação
   - Gera token JWT após sucesso
   - Redireciona para dashboard

2. **Proteção de rotas**
   - Todas as páginas verificam autenticação
   - Redirecionamento automático se não autenticado

3. **Logout**: Clique em "Logout" na sidebar
   - Limpa sessão
   - Redireciona para login

## Personalização

### Alterar credenciais
1. Gere novo hash de senha:
```bash
python -m app.scripts.generate_password_hash
```

2. Atualize no `.env`:
```env
ADMIN_USER=seu_usuario
ADMIN_PASSWORD_HASH=hash_gerado
```

### Adicionar múltiplos usuários
Edite `app/auth.py` e modifique o dicionário `USERS`:
```python
USERS = {
    'admin': 'hash_admin',
    'diretor1': 'hash_diretor1',
    'diretor2': 'hash_diretor2'
}
```

### Usar Supabase Auth (futuramente)
O projeto já tem as dependências necessárias (`gotrue`, `supabase`) para migrar para autenticação Supabase quando necessário.

## Segurança

- ✅ Senhas com hash bcrypt
- ✅ Tokens JWT com expiração
- ✅ Chaves secretas em variáveis de ambiente
- ✅ Sessões Flask seguras
- ⚠️ Em produção: use chaves secretas fortes e únicas