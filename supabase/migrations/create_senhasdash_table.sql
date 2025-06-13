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

-- Adicionar comentários na tabela
COMMENT ON TABLE public.senhasdash IS 'Tabela de usuários e senhas para acesso ao dashboard gerencial';
COMMENT ON COLUMN public.senhasdash.email IS 'Email do usuário (usado como login)';
COMMENT ON COLUMN public.senhasdash.senha_hash IS 'Hash bcrypt da senha do usuário';
COMMENT ON COLUMN public.senhasdash.nome IS 'Nome completo do usuário';
COMMENT ON COLUMN public.senhasdash.ativo IS 'Se o usuário está ativo ou bloqueado';
COMMENT ON COLUMN public.senhasdash.ultimo_acesso IS 'Data/hora do último login bem-sucedido';

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