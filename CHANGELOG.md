# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado
- Workflow simplificado com branches `main` (produção) e `trabalho` (desenvolvimento)
- Integração MCP com Render para gerenciamento de deploy
- Documentação de workflow de branches (BRANCH_WORKFLOW.md)
- Melhorias no .gitignore para maior segurança

### Modificado
- Branch padrão mudada de `agent5` para `main`
- Atualização da documentação MCP incluindo Render
- Configuração Git local com nome e email

### Removido
- Branches antigas arquivadas (agent5, agent5-production, etc.)

## [2025.06.18] - 2025-06-18

### Adicionado
- Sistema de validação CSV em 3 camadas (essencial/obrigatório/opcional)
- Modal de atualização com UI/UX moderna
- Compatibilidade com Python 3.8 (WSL)
- Arquivo de redirecionamento app/main.py para compatibilidade

### Corrigido
- Erro de modal duplicado (DuplicateIdError)
- Problema de módulo não encontrado no deploy
- Compatibilidade de sintaxe Python 3.8 vs 3.10+

## [2025.06.14] - 2025-06-14

### Adicionado
- Reorganização completa da estrutura do projeto
- Sistema de autenticação melhorado com glassmorphism
- Cache otimizado com Parquet
- Integração completa com MCP (GitHub, Supabase, Playwright)

### Modificado
- Estrutura de diretórios para maior profissionalismo
- Sistema de imports atualizado
- Melhorias de performance com cache em duas camadas

## [2025.05.01] - 2025-05-01

### Inicial
- Lançamento do dashboard de KPIs
- Integração com Supabase
- Sistema básico de autenticação
- Visualizações principais de métricas