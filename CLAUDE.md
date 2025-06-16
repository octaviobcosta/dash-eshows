# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: This file should be continuously updated with important discoveries, decisions, and patterns identified during development to maintain project memory across sessions.

## Commands

### Running the Application
```bash
# Main application (development mode with hot reload)
python -m app.main

# Alternative: run directly
python app/main.py
```

### Testing
```bash
# Run CAC validation test
python -m app.scripts.test_cac

# Test Supabase connection
python -m app.scripts.test_supabase_connection

# No formal test suite configured - manual testing via running the app is required
```

### Deployment

⚠️ **IMPORTANTE**: SEMPRE execute a verificação pré-deploy antes de fazer push!

```bash
# 1. OBRIGATÓRIO: Executar verificação pré-deploy
python -m scripts.pre_deploy_check

# 2. SE e SOMENTE SE todas as verificações passarem:
git push origin agent5

# 3. Monitorar o deploy
# Verificar logs no dashboard do Render
```

**Checklist manual adicional antes do deploy:**
- [ ] Testou localmente com `python -m app.main`?
- [ ] Verificou se TODOS os arquivos importados existem?
- [ ] Confirmou que não há tokens/senhas nos commits?
- [ ] Testou o login com as credenciais de produção?
- [ ] Verificou se os arquivos CSS estão na pasta assets?

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
7. **Git workflow**: Use feature branches, never commit directly to main
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
This project is configured with MCP integrations for enhanced development capabilities:

1. **GitHub Integration**
   - Full access to repository operations (commits, PRs, issues, etc.)
   - Repository: `octaviobcosta/dash-eshows`
   - Configured via `.mcp.json`

2. **Supabase Integration**
   - Database operations and migrations
   - Edge functions deployment
   - Project management
   - Configured via `.mcp.json`

3. **Browser Tools**
   - Screenshot capture and debugging
   - Performance audits
   - Accessibility checks
   - Network monitoring

4. **Playwright**
   - Browser automation for testing
   - UI interaction testing
   - Test generation

### MCP Configuration
The `.mcp.json` file contains the configuration for all MCP tools. Tokens are managed securely through environment variables:
- GitHub token: Set in MCP configuration
- Supabase credentials: Uses same env vars as the application

### Testing MCP Connections
```bash
# Test script is available to verify connections
# (creates temporary test file, runs connection test, then cleans up)
```