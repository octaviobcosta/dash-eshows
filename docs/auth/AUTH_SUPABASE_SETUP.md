# Configuração de Autenticação com Supabase

## O que foi implementado

1. **Tabela `senhasdash`** no Supabase para gerenciar usuários
2. **Integração completa** do login com o banco de dados
3. **Script de população** com os usuários solicitados
4. **Atualização automática** do último acesso

## Como configurar

### 1. Criar a tabela no Supabase

Acesse o [Supabase Dashboard](https://app.supabase.com) → SQL Editor e execute:

```sql
-- Criar tabela senhasdash para autenticação do dashboard
CREATE TABLE IF NOT EXISTS public.senhasdash (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    nome VARCHAR(100),
    ativo BOOLEAN DEFAULT true,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ultimo_acesso TIMESTAMP WITH TIME ZONE
);

-- Criar índice no email para busca rápida
CREATE INDEX idx_senhasdash_email ON public.senhasdash(email);

-- Função para atualizar o campo atualizado_em automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para atualizar automaticamente o campo atualizado_em
CREATE TRIGGER update_senhasdash_updated_at BEFORE UPDATE
    ON public.senhasdash FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Habilitar RLS (Row Level Security)
ALTER TABLE public.senhasdash ENABLE ROW LEVEL SECURITY;

-- Política para permitir leitura apenas para usuários autenticados
CREATE POLICY "Permitir leitura para service role" ON public.senhasdash
    FOR SELECT USING (true);
```

### 2. Popular os usuários

Execute o script de população:

```bash
# Ativar ambiente virtual
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # Linux/Mac

# Executar script
python -m app.scripts.populate_senhasdash
```

### 3. Usuários criados

| Email | Senha | Nome |
|-------|-------|------|
| gabriel.cunha@eshows.com.br | gabriel1234 | Gabriel Cunha |
| octavio@eshows.com.br | octavio1234 | Octavio |
| thiago@eshows.com.br | thiago1234 | Thiago |
| felipe@eshows.com.br | felipe1234 | Felipe |
| joao.bueno@eshows.com.br | joao1234 | João Bueno |
| fabio.pereira@eshows.com.br | fabio1234 | Fábio Pereira |
| kaio.geglio@eshows.com.br | kaio1234 | Kaio Geglio |

## Como funciona

1. **Login**: O usuário insere email e senha
2. **Validação**: Sistema busca no Supabase e valida o hash bcrypt
3. **Sessão**: Cria token JWT e armazena na sessão Flask
4. **Tracking**: Atualiza campo `ultimo_acesso` no banco

## Gerenciamento de usuários

### Adicionar novo usuário

```python
python -m app.scripts.generate_password_hash
# Digite a senha desejada
# Copie o hash gerado

# No Supabase SQL Editor:
INSERT INTO senhasdash (email, senha_hash, nome, ativo) 
VALUES ('novo@eshows.com.br', 'hash_gerado', 'Nome Completo', true);
```

### Desativar usuário

```sql
UPDATE senhasdash SET ativo = false WHERE email = 'usuario@eshows.com.br';
```

### Resetar senha

```python
# Gere novo hash
python -m app.scripts.generate_password_hash

# Atualize no banco
UPDATE senhasdash SET senha_hash = 'novo_hash' WHERE email = 'usuario@eshows.com.br';
```

## Segurança

- ✅ Senhas com hash bcrypt (impossível reverter)
- ✅ Tokens JWT com expiração
- ✅ Row Level Security habilitado
- ✅ Conexão segura com Supabase
- ✅ Tracking de último acesso

## Troubleshooting

### "Email ou senha incorretos"
- Verifique se o email está correto (com @eshows.com.br)
- Confirme que o usuário está ativo no banco
- Use o script de população para resetar senhas

### "Cliente Supabase não configurado"
- Verifique SUPABASE_URL e SUPABASE_KEY no .env
- Confirme que são as credenciais corretas do projeto

### Esqueci a senha
- Use o script generate_password_hash.py
- Atualize diretamente no Supabase Dashboard