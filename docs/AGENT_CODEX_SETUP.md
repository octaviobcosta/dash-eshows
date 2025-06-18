# Setup Offline para Agent Codex

## Problema Encontrado
```
ModuleNotFoundError: No module named 'dotenv'
```

## Solução - Setup Offline Completo

### 1. Criar e Ativar Ambiente Virtual
```bash
cd /workspace/dash-eshows
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar Dependências do Wheelhouse (Offline)
```bash
# Instalar python-dotenv primeiro (dependência básica)
pip install --no-index --find-links=wheelhouse/ python-dotenv

# Instalar todas as dependências do wheelhouse
pip install --no-index --find-links=wheelhouse/ -r requirements.txt
```

### 3. Verificar Instalação
```bash
# Testar se dotenv está instalado
python -c "import dotenv; print('dotenv instalado com sucesso!')"

# Testar aplicação
python -m app.main
```

## Arquivos Importantes Incluídos

1. **wheelhouse/** - Contém todos os .whl files necessários para instalação offline
2. **.mcp.json** - Configuração das ferramentas MCP
3. **CLAUDE.md** - Documentação completa do projeto
4. **AGENT.md** - Guia específico para agentes
5. **app/scripts/** - Scripts utilitários incluindo:
   - `check_mcp_connections.py` - Verificar conexões MCP
   - `setup_auth_complete.py` - Configurar autenticação
   - `test_cac.py` - Teste de validação CAC

## Variáveis de Ambiente Necessárias

Criar arquivo `.env` na raiz do projeto:
```env
SUPABASE_URL=sua_url_aqui
SUPABASE_KEY=sua_chave_aqui
SUPABASE_DB_PASSWORD=sua_senha_aqui
JWT_SECRET_KEY=gerar_nova_chave_secreta
FLASK_SECRET_KEY=gerar_nova_chave_secreta
```

## Branch Atual
- Trabalhando em: `agent5trabalho`
- Branch de produção: `agent5`

## Notas Importantes
- O projeto usa Python 3.12
- Todos os wheels necessários estão no diretório `wheelhouse/`
- A instalação deve ser feita com `--no-index` para usar apenas os arquivos locais
- O arquivo `.gitignore` foi mantido para segurança (não commitado)