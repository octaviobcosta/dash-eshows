#!/bin/bash
# Script para sincronizar branch trabalho - Dashboard eShows

echo -e "\033[36m🔄 Sincronizando branch trabalho...\033[0m"

# Verificar se estamos no diretório correto
if [ ! -f "run.py" ]; then
    echo -e "\033[31m❌ Erro: Execute este script da raiz do projeto!\033[0m"
    exit 1
fi

# Mudar para branch trabalho
echo -e "\033[33m📌 Mudando para branch trabalho...\033[0m"
git checkout trabalho

# Buscar atualizações
echo -e "\033[33m🔍 Buscando atualizações do repositório...\033[0m"
git fetch origin

# Verificar status antes do pull
echo -e "\033[33m📊 Status antes da atualização:\033[0m"
git status

# Fazer pull
echo -e "\033[33m⬇️ Baixando atualizações...\033[0m"
git pull origin trabalho

# Mostrar status final
echo -e "\033[32m✅ Branch trabalho atualizada!\033[0m"
echo -e "\033[33m📋 Status atual:\033[0m"
git status

# Mostrar últimos commits
echo -e "\033[36m📝 Últimos 5 commits:\033[0m"
git log --oneline -5

# Lembrete sobre arquivos locais
echo -e "\033[35m💡 Lembrete: Verifique se os seguintes arquivos locais estão atualizados:\033[0m"
echo "   - .env (variáveis de ambiente)"
echo "   - .mcp.json (configuração MCP)"