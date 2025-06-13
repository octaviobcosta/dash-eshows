# Sistema de Autenticação - Dashboard Gerencial

## Estrutura de Arquivos

```
dashboard-eshows/
├── app/
│   ├── auth.py                    # Módulo principal de autenticação
│   └── scripts/
│       ├── setup_auth_complete.py # Setup completo (verifica e popula)
│       ├── populate_senhasdash.py # Popula usuários na tabela
│       └── generate_password_hash.py # Utilitário para gerar hash
│
├── assets/
│   └── login.css                  # Estilos da página de login
│
├── supabase/
│   └── migrations/
│       └── create_senhasdash_table.sql # SQL para criar tabela
│
├── mcp/                           # Model Context Protocol
│   ├── mcp_supabase_sql.py       # Servidor MCP para SQL
│   └── mcp_config.json           # Configuração exemplo
│
└── docs/
    ├── auth/
    │   ├── README.md              # Este arquivo
    │   ├── LOGIN_IMPLEMENTATION.md # Detalhes da implementação
    │   └── AUTH_SUPABASE_SETUP.md # Setup do Supabase
    └── mcp/
        └── MCP_SUPABASE_SETUP.md  # Como configurar MCP

```

## Quick Start

### 1. Criar tabela no Supabase
Execute o SQL em `supabase/migrations/create_senhasdash_table.sql`

### 2. Popular usuários
```bash
python -m app.scripts.setup_auth_complete
```

### 3. Testar
```bash
python -m app.main
```

## Arquivos Principais

- **app/auth.py**: Toda lógica de autenticação, login, sessões
- **assets/login.css**: Design minimalista da página de login
- **setup_auth_complete.py**: Script único para configurar tudo

## Documentação Detalhada

- [Implementação do Login](LOGIN_IMPLEMENTATION.md)
- [Setup Supabase](AUTH_SUPABASE_SETUP.md)
- [MCP para SQL](../mcp/MCP_SUPABASE_SETUP.md)