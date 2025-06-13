# MCP para Supabase SQL

## O que é?

Um servidor MCP (Model Context Protocol) que permite ao Claude executar comandos SQL diretamente no seu banco Supabase, incluindo:
- CREATE TABLE, ALTER TABLE, DROP TABLE
- INSERT, UPDATE, DELETE
- SELECT com resultados formatados
- Listar tabelas e descrever estruturas

## Como configurar no Claude Desktop

### 1. Instale as dependências do MCP

```bash
pip install mcp psycopg2-binary
```

### 2. Configure o Claude Desktop

No Windows, edite: `%APPDATA%\Claude\claude_desktop_config.json`
No macOS/Linux, edite: `~/.config/Claude/claude_desktop_config.json`

Adicione:

```json
{
  "mcpServers": {
    "supabase-sql": {
      "command": "python",
      "args": [
        "C:/Users/octav/Projetos/dashboard-eshows/mcp_supabase_sql.py"
      ],
      "env": {
        "PGURL": "postgresql://postgres:SUA_SENHA@db.SEU_PROJETO.supabase.co:5432/postgres?sslmode=require",
        "SUPABASE_URL": "https://SEU_PROJETO.supabase.co",
        "SUPABASE_DB_PASSWORD": "SUA_SENHA"
      }
    }
  }
}
```

**Importante**: Substitua os valores de `PGURL`, `SUPABASE_URL` e `SUPABASE_DB_PASSWORD` pelos valores reais do seu `.env`.

### 3. Reinicie o Claude Desktop

Feche e abra o Claude Desktop para carregar o MCP.

## Como usar

Após configurar, você terá 3 novas ferramentas disponíveis:

### 1. `execute_sql`
Executa qualquer comando SQL:

```
Use a ferramenta execute_sql para criar a tabela senhasdash com o SQL:
CREATE TABLE IF NOT EXISTS public.senhasdash (...)
```

### 2. `list_tables`
Lista todas as tabelas:

```
Use a ferramenta list_tables para ver todas as tabelas do banco
```

### 3. `describe_table`
Mostra a estrutura de uma tabela:

```
Use a ferramenta describe_table para ver a estrutura da tabela senhasdash
```

## Exemplo de uso completo

1. **Criar a tabela**:
   ```
   Use execute_sql para criar a tabela senhasdash com toda a estrutura necessária
   ```

2. **Verificar se foi criada**:
   ```
   Use list_tables para confirmar que a tabela existe
   ```

3. **Popular com usuários**:
   ```
   Use execute_sql para inserir os usuários na tabela
   ```

## Segurança

- O MCP tem acesso total ao banco de dados
- Use apenas em ambiente de desenvolvimento
- Nunca compartilhe as credenciais do banco
- O Claude Desktop mantém as credenciais localmente

## Troubleshooting

### "Ferramenta não encontrada"
- Verifique se o MCP foi configurado corretamente
- Reinicie o Claude Desktop
- Confirme que o caminho do arquivo está correto

### "Erro de conexão"
- Verifique as credenciais no config
- Confirme que o IP está liberado no Supabase
- Teste a conexão com psql ou outro cliente

### "Permission denied"
- Verifique se o usuário tem permissões adequadas
- Para DDL, geralmente precisa ser o usuário postgres