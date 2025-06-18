# Workflow de Branches - Dashboard Eshows

## Estrutura de Branches

### main (Produção)
- Branch padrão do repositório
- Deploy automático no Render
- Protegida contra pushes diretos
- Recebe apenas código testado e aprovado

### trabalho (Desenvolvimento)
- Branch principal de desenvolvimento
- Onde novas funcionalidades são implementadas
- Testes locais são realizados aqui
- Mantém arquivo `.mcp.json` localmente (não commitado)

## Fluxo de Trabalho

### 1. Desenvolvimento Local
```bash
# Sempre trabalhe na branch trabalho
git checkout trabalho

# Certifique-se de estar atualizado
git pull origin trabalho

# Faça suas alterações e teste localmente
# ...

# Commit suas mudanças
git add .
git commit -m "feat: descrição da funcionalidade"

# Push para o repositório remoto
git push origin trabalho
```

### 2. Deploy para Produção
```bash
# Após testar na branch trabalho
git checkout main

# Atualize com as mudanças da trabalho
git merge trabalho

# Push para main (trigger deploy automático)
git push origin main

# Volte para trabalho para continuar desenvolvendo
git checkout trabalho
```

### 3. Mantendo Branches Sincronizadas
```bash
# Periodicamente, atualize trabalho com main
git checkout trabalho
git merge main
git push origin trabalho
```

## Comandos Git Essenciais

### Status e Histórico
```bash
git status                    # Ver estado atual
git log --oneline -10        # Ver últimos 10 commits
git branch -a                # Ver todas as branches
```

### Desfazer Mudanças
```bash
git checkout -- arquivo.py    # Descartar mudanças não commitadas
git reset HEAD~1             # Desfazer último commit (mantém mudanças)
git reset --hard HEAD~1      # Desfazer último commit (descarta mudanças)
```

### Resolver Conflitos
```bash
# Se houver conflitos durante merge
git status                   # Ver arquivos em conflito
# Edite os arquivos para resolver conflitos
git add arquivo_resolvido.py
git commit                   # Completar o merge
```

## Configurações Importantes

### Arquivos Ignorados
- `.mcp.json` - Configurações MCP com tokens (apenas local)
- `app/data/_cache_parquet/` - Cache local de dados
- `.env` - Variáveis de ambiente locais

### Proteção da Branch Main
- Requer pull request para merge
- Requer aprovação antes do merge
- Status checks devem passar
- Inclui administradores nas regras

## Backup Realizado

**Data**: 18/06/2025  
**Localização**: `../dashboard-eshows-backup-[timestamp].tar.gz`  
**Conteúdo**: Snapshot completo do projeto antes da reorganização

### Branches Arquivadas
- agent5
- agent5-clean
- agent5-deploy
- agent5-deploy-clean
- agent5trabalho
- agent5-production
- ux-ui-improvements
- ux-ui-improvements-today

## Migração do Fluxo Anterior

### Antes (Múltiplas branches)
- agent5trabalho → desenvolvimento
- agent5-production → produção
- Várias branches experimentais

### Agora (Simplificado)
- trabalho → desenvolvimento
- main → produção
- Fluxo linear e claro

## Notas de Segurança

1. **Nunca commite tokens ou credenciais**
   - Mantenha `.mcp.json` local
   - Use variáveis de ambiente no Render

2. **Sempre teste antes do deploy**
   - Execute localmente na branch trabalho
   - Verifique logs e funcionalidades

3. **Use commits descritivos**
   - feat: nova funcionalidade
   - fix: correção de bug
   - docs: atualização de documentação
   - chore: tarefas de manutenção

## Suporte

Para questões sobre o workflow:
1. Consulte esta documentação
2. Verifique logs do Git
3. Use `git status` para entender o estado atual