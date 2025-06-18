# Configuração das Conexões MCP

## ⚠️ IMPORTANTE: Segurança dos Tokens

**NUNCA** commite tokens reais no repositório. O arquivo `.mcp.json` já está no `.gitignore` para prevenir exposição acidental.

## 1. Obter os Tokens Necessários

### Token do GitHub
1. Acesse: https://github.com/settings/tokens
2. Clique em "Generate new token" → "Generate new token (classic)"
3. Nome: "Claude Code - Dashboard eShows"
4. Selecione os scopes necessários:
   - `repo` (acesso completo aos repositórios)
   - `workflow` (para CI/CD)
   - `read:org` (se trabalhar com organizações)
5. Clique em "Generate token"
6. **COPIE O TOKEN IMEDIATAMENTE** (não será mostrado novamente)

### Token do Supabase
1. Acesse: https://app.supabase.com/account/tokens
2. Clique em "Generate new token"
3. Nome: "Claude Code - Dashboard eShows"
4. Clique em "Generate token"
5. **COPIE O TOKEN IMEDIATAMENTE**

## 2. Configurar os Tokens

### Opção A: Editar `.mcp.json` (Recomendado para uso local)

1. Abra o arquivo `.mcp.json`
2. Substitua os placeholders:
   - `REPLACE_WITH_YOUR_SUPABASE_ACCESS_TOKEN` → Seu token do Supabase
   - `REPLACE_WITH_YOUR_GITHUB_TOKEN` → Seu token do GitHub

### Opção B: Usar Variáveis de Ambiente (Mais seguro)

1. Crie um arquivo `.env.mcp` (adicione ao .gitignore):
```bash
GITHUB_TOKEN=seu_token_github_aqui
SUPABASE_ACCESS_TOKEN=seu_token_supabase_aqui
```

2. Modifique o `.mcp.json` para usar variáveis de ambiente:
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--access-token",
        "${SUPABASE_ACCESS_TOKEN}"
      ]
    },
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github@latest"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

## 3. Testar as Conexões

Após configurar os tokens:

1. Reinicie o Claude Desktop
2. Abra o projeto
3. Teste as conexões usando os comandos MCP

### Teste GitHub:
```
mcp__github__list_branches
```

### Teste Supabase:
```
mcp__supabase__list_tables
```

### Teste Playwright:
```
mcp__playwright__browser_navigate("https://google.com")
```

## 4. Troubleshooting

### Erro: "Token inválido"
- Verifique se copiou o token completo
- Certifique-se de que o token não expirou
- Para GitHub, verifique se os scopes estão corretos

### Erro: "MCP server not found"
- Reinicie o Claude Desktop após modificar `.mcp.json`
- Verifique se o Node.js está instalado
- Tente executar manualmente: `npx @modelcontextprotocol/server-github@latest`

### As ferramentas MCP não aparecem
- Certifique-se de que está usando o Claude Desktop (não o web)
- Verifique se o arquivo `.mcp.json` está na raiz do projeto
- Olhe os logs do Claude Desktop para erros

## 5. Boas Práticas

1. **Rotação de Tokens**: Renove os tokens a cada 90 dias
2. **Permissões Mínimas**: Use apenas os scopes necessários
3. **Backup Seguro**: Guarde os tokens em um gerenciador de senhas
4. **Monitoramento**: Verifique regularmente o uso dos tokens nas configurações do GitHub/Supabase

## 6. Revogação de Emergência

Se um token for comprometido:

### GitHub:
1. https://github.com/settings/tokens
2. Clique em "Revoke" no token comprometido
3. Gere um novo token imediatamente

### Supabase:
1. https://app.supabase.com/account/tokens
2. Clique no ícone de lixeira ao lado do token
3. Gere um novo token imediatamente

---

**Lembre-se**: A segurança dos tokens é sua responsabilidade. Trate-os como senhas!