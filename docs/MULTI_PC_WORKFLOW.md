# Workflow Multi-PC - Dashboard eShows

## 🖥️ Contexto
Este guia é essencial para desenvolvedores que trabalham no projeto usando múltiplos computadores (casa, trabalho, etc.). Garante que você sempre esteja com a versão mais atualizada e evita conflitos.

## 🚀 Checklist de Início de Sessão

### SEMPRE execute estes comandos ao iniciar o trabalho:

```bash
# 1. Verificar em qual branch você está
git branch --show-current

# 2. Mudar para branch trabalho (se necessário)
git checkout trabalho

# 3. Buscar atualizações do repositório remoto
git fetch origin

# 4. Verificar se há atualizações disponíveis
git status

# 5. Atualizar sua branch trabalho local
git pull origin trabalho

# 6. Verificar novamente o status
git status
```

### Script Rápido (copie e cole):
```bash
git checkout trabalho && git fetch origin && git pull origin trabalho && git status
```

## 📁 Arquivos Locais Importantes

### Arquivos que NÃO são versionados (precisa copiar entre PCs):

1. **`.env`** - Variáveis de ambiente
   ```bash
   SUPABASE_URL=your_url
   SUPABASE_KEY=your_key
   ANTHROPIC_API_KEY=your_key
   OPENAI_API_KEY=your_key
   JWT_SECRET_KEY=your_secret
   FLASK_SECRET_KEY=your_secret
   ```

2. **`.mcp.json`** - Configuração MCP (se usar Claude Desktop)
   - Contém tokens do GitHub, Supabase, Render
   - NUNCA commite este arquivo

3. **`app/data/_cache_parquet/`** - Cache local
   - Pode ser deletado sem problemas
   - Será recriado automaticamente

### Como sincronizar arquivos locais entre PCs:

#### Opção 1: Armazenamento em Nuvem Seguro
```bash
# Criar pasta segura (exemplo com OneDrive)
mkdir ~/OneDrive/eshows-config-secure

# Copiar arquivos sensíveis
cp .env ~/OneDrive/eshows-config-secure/
cp .mcp.json ~/OneDrive/eshows-config-secure/

# No outro PC, copiar de volta
cp ~/OneDrive/eshows-config-secure/.env ./
cp ~/OneDrive/eshows-config-secure/.mcp.json ./
```

#### Opção 2: Variáveis de Ambiente do Sistema
Configure as variáveis diretamente no sistema operacional de cada PC.

## 🔄 Resolvendo Conflitos Entre PCs

### Cenário 1: "Your branch is behind..."
```bash
# Solução simples - atualizar local com remoto
git pull origin trabalho
```

### Cenário 2: "Your branch and 'origin/trabalho' have diverged"
```bash
# Opção A: Manter mudanças locais
git pull origin trabalho --rebase

# Opção B: Descartar mudanças locais e usar remoto
git reset --hard origin/trabalho
```

### Cenário 3: Conflitos durante merge
```bash
# 1. Pull tenta fazer merge automático
git pull origin trabalho

# 2. Se houver conflitos, verá mensagem de erro
# 3. Verificar arquivos em conflito
git status

# 4. Editar arquivos manualmente para resolver
# 5. Adicionar arquivos resolvidos
git add arquivo_resolvido.py

# 6. Completar o merge
git commit
```

## 📝 Boas Práticas Multi-PC

### 1. **SEMPRE faça push ao terminar o trabalho**
```bash
git add .
git commit -m "feat: descrição do que foi feito"
git push origin trabalho
```

### 2. **SEMPRE faça pull ao começar o trabalho**
```bash
git pull origin trabalho
```

### 3. **Commits frequentes e descritivos**
- Facilita identificar o que foi feito em cada PC
- Reduz conflitos grandes

### 4. **Use stash para trabalho não finalizado**
```bash
# Guardar trabalho temporariamente
git stash save "WIP: funcionalidade X no PC do trabalho"

# Listar stashes
git stash list

# Recuperar stash específico
git stash apply stash@{0}
```

## 🛠️ Scripts Auxiliares

### Windows PowerShell (`sync_trabalho.ps1`):
```powershell
Write-Host "🔄 Sincronizando branch trabalho..." -ForegroundColor Cyan
git checkout trabalho
git fetch origin
git pull origin trabalho
Write-Host "✅ Branch trabalho atualizada!" -ForegroundColor Green
Write-Host "📋 Status atual:" -ForegroundColor Yellow
git status
```

### Linux/Mac Bash (`sync_trabalho.sh`):
```bash
#!/bin/bash
echo -e "\033[36m🔄 Sincronizando branch trabalho...\033[0m"
git checkout trabalho
git fetch origin
git pull origin trabalho
echo -e "\033[32m✅ Branch trabalho atualizada!\033[0m"
echo -e "\033[33m📋 Status atual:\033[0m"
git status
```

### Como usar os scripts:
```bash
# Windows PowerShell
./scripts/sync_trabalho.ps1

# Linux/Mac
chmod +x scripts/sync_trabalho.sh
./scripts/sync_trabalho.sh
```

## 🚨 Troubleshooting

### Erro: "Authentication failed"
```bash
# Verificar configuração do Git
git config --list

# Reconfigurar credenciais
git config --global user.name "seu-usuario"
git config --global user.email "seu-email"

# No Windows, limpar credenciais salvas
git config --global --unset credential.helper
```

### Erro: "Permission denied (publickey)"
- Está usando HTTPS, não SSH
- Se mudar para SSH, configure chaves em ambos PCs

### Cache corrompido após sync
```bash
# Limpar cache local
rm -rf app/data/_cache_parquet/
# Ou no Windows:
Remove-Item -Recurse -Force app/data/_cache_parquet/
```

## 📱 Notificações e Lembretes

### Configurar alias Git úteis:
```bash
# Adicionar ao ~/.gitconfig ou usar comandos:
git config --global alias.sync-trabalho '!git checkout trabalho && git fetch origin && git pull origin trabalho'
git config --global alias.status-all '!git fetch origin && git status'
git config --global alias.push-trabalho '!git push origin trabalho'

# Usar assim:
git sync-trabalho
git status-all
git push-trabalho
```

## 🎯 Resumo do Fluxo Diário

### Início do Dia:
1. `git sync-trabalho` (ou script)
2. Verificar/copiar `.env` e `.mcp.json` se necessário
3. `python run.py` para testar

### Durante o Desenvolvimento:
1. Commits frequentes com mensagens claras
2. `git status` regularmente
3. Push a cada funcionalidade completa

### Fim do Dia:
1. `git add .`
2. `git commit -m "descrição"`
3. `git push origin trabalho`
4. Anotar qualquer trabalho pendente

## 🔐 Segurança

1. **NUNCA** commite arquivos com senhas ou tokens
2. **SEMPRE** use `.gitignore` para arquivos sensíveis
3. **VERIFIQUE** antes de fazer push: `git status`
4. **REVOGUE** tokens se acidentalmente expostos

## 📞 Suporte

Se encontrar problemas:
1. Consulte esta documentação
2. Verifique `docs/BRANCH_WORKFLOW.md`
3. Use `git log` para entender o histórico
4. Crie uma issue no GitHub se necessário

---

**Última atualização**: 18/06/2025  
**Maintainer**: Dashboard eShows Team