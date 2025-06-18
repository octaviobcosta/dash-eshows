# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: This file should be continuously updated with important discoveries, decisions, and patterns identified during development to maintain project memory across sessions.

## 🚨 INÍCIO DE CADA SESSÃO - VERIFICAÇÃO DE CONEXÕES MCP

### Status das Conexões MCP Configuradas:
O arquivo `.mcp.json` está configurado localmente (não versionado no Git):

- ✅ **GitHub MCP**: Configurado localmente
  - Repositório: `octaviobcosta/dash-eshows`
  - ⚠️ **IMPORTANTE**: Renovar token se foi exposto
  
- ✅ **Supabase MCP**: Configurado localmente
  - Projeto ID: `yrvtmgrqxhqltckpfizn`
  - Nome: "Dashboard de KPIs & OKRs"
  - ⚠️ **IMPORTANTE**: Renovar token se foi exposto
  
- ✅ **Playwright MCP**: Pronto para uso
  - Não requer tokens ou configuração adicional

- ✅ **Render MCP**: Configurado localmente
  - Web Service: dashboard-eshows
  - Deploy automático da branch `main`
  - ⚠️ **IMPORTANTE**: API Key sensível configurada

**NOTA DE SEGURANÇA**: Se os tokens foram expostos publicamente, devem ser revogados e regenerados imediatamente. Ver `docs/MCP_SETUP.md` para instruções.

### Verificação Opcional:
Se desejar verificar o status das conexões, execute:
```bash
python -m app.scripts.check_mcp_connections
```
**Nota**: O script pode indicar que o Supabase precisa de configuração, mas na prática o token no `.mcp.json` já está funcionando.

## Commands

### Running the Application

#### Para execução no ambiente Claude (WSL):
```bash
# Usar o Python do ambiente virtual Windows
.venv/Scripts/python.exe run.py

# Ou usando o caminho completo
/mnt/c/Users/octav/Projetos/dashboard-eshows/.venv/Scripts/python.exe run.py
```

#### Para execução normal (Windows/Linux/Mac):
```bash
# Ativar ambiente virtual primeiro
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Executar aplicação
python run.py

# Alternative: run from module
python -m app.core.main
```

### Testing
```bash
# Run CAC validation test
python -m app.scripts.test_cac

# No formal test suite configured - manual testing via running the app is required
```

### Deployment
```bash
# Prepare for deploy (already configured)
# - render.yaml with all settings
# - runtime.txt with Python version
# - requirements.txt with gunicorn

# Deploy happens automatically on push to agent5 branch
git push origin agent5

# Monitor deployment
# Check Render dashboard for logs and status
```

### Authentication Setup
```bash
# Setup authentication (create table and populate users)
python -m app.scripts.setup_auth_complete

# Generate password hash for new users
python -m app.scripts.generate_password_hash
```

### Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# For offline setup with pre-downloaded wheels
.\scripts\setup_offline.ps1  # Windows
./scripts/setup_offline.sh   # Linux/macOS
```

### Database Operations
```bash
# Create new migration
supabase migration new "description"

# Apply migrations to remote
supabase db push

# Pull database changes
supabase db pull -p "$SUPABASE_DB_PASSWORD"
```

## Estrutura Reorganizada do Projeto

A estrutura foi reorganizada para maior profissionalismo:

```
app/
├── core/        # Arquivos principais (main.py, config_data.py)
├── data/        # Gestão de dados (data_manager.py, modulobase.py, column_mapping.py)
├── auth/        # Sistema de autenticação (auth.py, auth_improved.py)
├── kpis/        # Cálculos e controles de KPIs (variacoes.py, controles.py, kpi_interpreter.py)
├── utils/       # Utilitários (utils.py, mem_utils.py, hist.py)
├── ui/          # Componentes de interface (kpis_charts.py)
├── updates/     # Sistema de upload CSV (csv_validator.py, csv_uploader.py, update_modal_improved.py)
├── components/  # Componentes reutilizáveis (toast_notifications.py)
├── okrs/        # Módulo de OKRs
├── scripts/     # Scripts de setup e manutenção
└── assets/      # CSS, JS e imagens
```

Arquivos de configuração movidos para:
- `config/` - render.yaml, runtime.txt, .env.example
- `docs/` - Toda documentação (CLAUDE.md, DEPLOY_GUIDE.md, etc.)
- `scripts/` - Scripts auxiliares (financeiro.py, logging_config.py)

## High-Level Architecture

### Overview
This is a business intelligence dashboard for eShows built with Dash (Python web framework) and Supabase (PostgreSQL). The application displays KPIs, financial metrics, and OKRs for the entertainment/shows management business.

### Key Components

1. **Data Flow Pipeline**
   ```
   Supabase DB → Data Manager → Cache Layer → ModuloBase → Business Logic → UI
                       ↓              ↓
                 API Fetches    Parquet Files
   ```

2. **Core Modules**
   - **app/main.py**: Entry point, Dash app initialization, routing, and UI layout
   - **app/auth.py**: Authentication system, login page, session management
   - **app/data_manager.py**: Supabase connection, caching strategy (RAM + Parquet), lazy loading
   - **app/modulobase.py**: Data sanitization, type optimization, business rules application
   - **app/variacoes.py**: All KPI calculation functions (CMGR, NRR, Churn, EBITDA, etc.)
   - **app/controles.py**: KPI control zones and status determination
   - **app/utils.py**: Period filtering, date calculations, formatting utilities

3. **Caching Strategy**
   - Two-tier caching: optional RAM cache + persistent Parquet file cache
   - Default cache expiry: 12 hours (configurable via CACHE_EXPIRY_HOURS)
   - Cache location: app/_cache_parquet/
   - Automatic cache invalidation based on timestamp

4. **Data Processing**
   - Column mapping applied during fetch (see app/column_mapping.py)
   - Automatic conversion from cents to currency units
   - Memory optimization through dtype downcasting
   - Category conversion for string columns to save memory
   - Removal of test data, duplicates, and invalid records

5. **Period Handling**
   - Supports: YTD, quarters, months, custom ranges, full year
   - Automatic comparison period calculation (previous year/period)
   - Period-aware KPI calculations with proper aggregation

6. **Environment Variables**
   Required in .env:
   - SUPABASE_URL: Project URL
   - SUPABASE_KEY: Anonymous or service role key
   - SUPABASE_DB_PASSWORD: For CLI operations
   - JWT_SECRET_KEY: Secret for JWT tokens
   - FLASK_SECRET_KEY: Secret for Flask sessions
   - USE_RAM_CACHE: Optional, enables RAM caching
   - CACHE_EXPIRY_HOURS: Optional, cache duration

### Important Notes

1. **Before submitting any PR**: Must run `python -m app.main` to test locally
2. **Data tables**: baseeshows, base2, pessoas, ocorrencias, metas, custosabertos, npsartistas, senhasdash
3. **No formal linting setup**: Code style should match existing patterns
4. **Offline capability**: Use setup_offline.ps1/sh scripts with wheelhouse/ directory
5. **Authentication**: Fully implemented with Supabase integration and JWT tokens
6. **Memory management**: Aggressive optimization due to large datasets
7. **Git workflow**: 
   - `agent5`: Branch de produção (auto-deploy no Render)
   - `agent5trabalho`: Branch de desenvolvimento
   - Fluxo: trabalhar em agent5trabalho → merge para agent5 → deploy automático
8. **Login required**: All routes protected, users managed in senhasdash table

## Code Standards

### Style Guidelines
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Line length**: Keep to reasonable lengths (existing code uses ~120 chars)
- **Imports**: Group by type with blank lines (stdlib, third-party, internal)
- **Docstrings**: Use Google-style docstrings for complex functions

### Pull Request Process
1. Test locally with `python -m app.main`
2. Include clear description of changes
3. Reference any related tickets/issues
4. Ensure no sensitive data (API keys, passwords) in commits

## Domain Glossary

| Term | Meaning |
|------|---------|
| **BaseEshows** | Main shows/events data table |
| **Palco Vazio** | Canceled show without replacement |
| **NRR** | Net Revenue Retention |
| **CMGR** | Compound Monthly Growth Rate |
| **CAC** | Customer Acquisition Cost |
| **LTV** | Lifetime Value |
| **Churn** | Customer/revenue loss rate |
| **EBITDA** | Earnings before interest, taxes, depreciation, and amortization |
| **KPI** | Key Performance Indicator |
| **OKR** | Objectives and Key Results |

## Security Guidelines

1. **NEVER commit credentials** - No tokens, keys, or passwords in code
2. **Always use environment variables** for sensitive data
3. **Fail fast** - Scripts should error if env vars are missing, not use defaults
4. **Rotate immediately** if any credential is exposed
5. **Check before commit** - Review changes for accidental credential exposure

## Known Issues & Solutions

### Cache Corruption
If you see "cache file might be corrupted" errors:
```bash
# Clear the cache
rm -rf app/_cache_parquet/
# Or on Windows:
Remove-Item -Recurse -Force app/_cache_parquet/
```

### Git Authentication
- Current setup uses Personal Access Token
- Consider migrating to SSH for better security (see git-credentials-setup.md)
- NEVER commit tokens in files

### Deploy Issues (Render)
1. **Invalid API Key Error**
   - Causa: SUPABASE_KEY quebrada em múltiplas linhas
   - Solução: Colar a chave em uma linha única no Render

2. **Python Version Mismatch**
   - Render pode usar versão diferente da especificada
   - Solução: Verificar runtime.txt e configuração do Render

3. **Memory Issues**
   - Plano Free (512MB) insuficiente para o projeto
   - Solução: Usar plano de $25/mês com 2GB RAM

4. **Environment Variables**
   - SEMPRE gerar novas chaves para JWT_SECRET_KEY e FLASK_SECRET_KEY
   - NUNCA usar valores padrão como "your-secret-key-change-in-production"

## MCP (Model Context Protocol) Integration

### Available MCP Tools
Este projeto está configurado com integrações MCP que expandem significativamente as capacidades de desenvolvimento:

#### 1. **GitHub MCP** ✅
**Status**: Totalmente operacional
- **Capacidades**:
  - Operações completas de repositório (criar, forkar, buscar)
  - Gerenciamento de arquivos (ler, criar, editar, commits, push)
  - Pull Requests (criar, revisar, merge, comentar)
  - Issues (criar, editar, comentar, fechar)
  - Busca de código em todo o GitHub
  - Gerenciamento de branches
- **Configuração**: Token já configurado no `.mcp.json`
- **Repositório**: `octaviobcosta/dash-eshows`

#### 2. **Supabase MCP** ✅
**Status**: Totalmente operacional
- **Capacidades**:
  - **Banco de dados**:
    - Listar e explorar estrutura de tabelas
    - Executar queries SQL (SELECT, INSERT, UPDATE, DELETE)
    - Aplicar migrações DDL
    - Visualizar logs e diagnósticos
  - **Edge Functions**:
    - Criar e fazer deploy de funções serverless
    - Listar funções existentes
  - **Gestão de Projetos**:
    - Criar, pausar e restaurar projetos
    - Gerenciar branches de desenvolvimento
  - **Segurança e Performance**:
    - Verificar advisors de segurança
    - Analisar performance do banco
  - **TypeScript**:
    - Gerar tipos automaticamente das tabelas
- **Configuração**: Access token já configurado no `.mcp.json`
- **Projeto ID**: `yrvtmgrqxhqltckpfizn`
- **Tabelas principais**: baseeshows, base2, pessoas, metas, custosabertos, npsartistas, senhasdash

#### 3. **Playwright MCP** ✅
**Status**: Totalmente operacional
- **Capacidades**:
  - **Navegação**: abrir URLs, voltar, avançar, recarregar
  - **Interação com elementos**:
    - Clicar botões e links
    - Preencher formulários
    - Selecionar opções em dropdowns
    - Arrastar e soltar elementos
  - **Captura**: screenshots e snapshots de acessibilidade
  - **Upload de arquivos**
  - **Gestão de abas**: criar, listar, selecionar, fechar
  - **Automação de testes**: gerar testes Playwright automaticamente
  - **Debug**: console logs, requisições de rede
- **Configuração**: Não requer tokens, funciona imediatamente

#### 4. **Render MCP** ✅
**Status**: Totalmente operacional
- **Capacidades**:
  - **Web Services**:
    - Listar todos os serviços
    - Ver detalhes e status
    - Monitorar logs em tempo real
    - Verificar deployments
  - **Deploy Management**:
    - Iniciar novos deploys
    - Cancelar deploys em andamento
    - Ver histórico de deploys
  - **Static Sites**:
    - Gerenciar sites estáticos
    - Ver configurações
  - **PostgreSQL**:
    - Listar instâncias
    - Monitorar status
- **Configuração**: API Key já configurada no `.mcp.json`
- **Web Service**: dashboard-eshows (deploy automático da branch `main`)

### Casos de Uso Práticos

#### 1. **Atualização de Dados e Deploy**
```python
# Usar Supabase MCP para atualizar dados
mcp__supabase__execute_sql("UPDATE metas SET Fat_Total = 5000000 WHERE Ano = 2024")

# Usar GitHub MCP para commit e push
mcp__github__create_or_update_file(...)
mcp__github__create_pull_request(...)
```

#### 2. **Teste Automatizado da Aplicação**
```python
# Usar Playwright para testar o dashboard
mcp__playwright__browser_navigate("http://localhost:8050")
mcp__playwright__browser_type("login", "usuario@example.com")
mcp__playwright__browser_click("submit")
mcp__playwright__browser_take_screenshot("dashboard-loaded.png")
```

#### 3. **Análise e Debugging**
```python
# Ver logs de erros no Supabase
mcp__supabase__get_logs(project_id="...", service="api")

# Buscar código relacionado no GitHub
mcp__github__search_code("q=erro+repo:octaviobcosta/dash-eshows")
```

### Configuração Atual
Todas as ferramentas MCP já estão configuradas e operacionais através do arquivo `.mcp.json`. Os tokens necessários já estão incluídos:

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase@latest", "--access-token", "TOKEN"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github@latest"],
      "env": {"GITHUB_TOKEN": "TOKEN"}
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    },
    "render": {
      "command": "npx",
      "args": ["-y", "render-mcp-server"],
      "env": {"RENDER_API_KEY": "TOKEN"}
    }
  }
}
```

### Troubleshooting
Se alguma ferramenta MCP não estiver funcionando:
1. Verifique se o Claude Desktop está atualizado
2. Reinicie o Claude Desktop após mudanças no `.mcp.json`
3. Para debug detalhado, verifique os logs do Claude Desktop
4. O script `check_mcp_connections.py` pode dar falsos negativos - teste diretamente as ferramentas