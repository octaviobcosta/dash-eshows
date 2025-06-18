# Script para sincronizar branch trabalho - Dashboard eShows
# PowerShell version

Write-Host "🔄 Sincronizando branch trabalho..." -ForegroundColor Cyan

# Verificar se estamos no diretório correto
if (-not (Test-Path "run.py")) {
    Write-Host "❌ Erro: Execute este script da raiz do projeto!" -ForegroundColor Red
    exit 1
}

# Mudar para branch trabalho
Write-Host "📌 Mudando para branch trabalho..." -ForegroundColor Yellow
git checkout trabalho

# Buscar atualizações
Write-Host "🔍 Buscando atualizações do repositório..." -ForegroundColor Yellow
git fetch origin

# Verificar status antes do pull
Write-Host "📊 Status antes da atualização:" -ForegroundColor Yellow
git status

# Fazer pull
Write-Host "⬇️ Baixando atualizações..." -ForegroundColor Yellow
git pull origin trabalho

# Mostrar status final
Write-Host "✅ Branch trabalho atualizada!" -ForegroundColor Green
Write-Host "📋 Status atual:" -ForegroundColor Yellow
git status

# Mostrar últimos commits
Write-Host "📝 Últimos 5 commits:" -ForegroundColor Cyan
git log --oneline -5

# Lembrete sobre arquivos locais
Write-Host "`n💡 Lembrete: Verifique se os seguintes arquivos locais estão atualizados:" -ForegroundColor Magenta
Write-Host "   - .env (variáveis de ambiente)" -ForegroundColor White
Write-Host "   - .mcp.json (configuração MCP)" -ForegroundColor White