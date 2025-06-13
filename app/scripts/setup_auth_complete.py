#!/usr/bin/env python3
"""
Script completo para configurar autenticação - verifica tabela e popula usuários.

Uso:
    python -m app.scripts.setup_auth_complete
    
Este script:
1. Verifica se a tabela senhasdash existe
2. Se não existir, mostra o SQL para criar
3. Popula com os usuários padrão
"""

import os
import sys
from pathlib import Path
import bcrypt
from datetime import datetime
from dotenv import load_dotenv

# Adiciona o diretório raiz ao path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Carrega variáveis de ambiente
load_dotenv()

from supabase import create_client, Client

# Configuração do Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Erro: Variáveis SUPABASE_URL e SUPABASE_KEY devem estar definidas no .env")
    sys.exit(1)

# Criar cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Lista de usuários para criar
usuarios = [
    {"email": "gabriel.cunha@eshows.com.br", "senha": "gabriel1234", "nome": "Gabriel Cunha"},
    {"email": "octavio@eshows.com.br", "senha": "octavio1234", "nome": "Octavio"},
    {"email": "thiago@eshows.com.br", "senha": "thiago1234", "nome": "Thiago"},
    {"email": "felipe@eshows.com.br", "senha": "felipe1234", "nome": "Felipe"},
    {"email": "joao.bueno@eshows.com.br", "senha": "joao1234", "nome": "João Bueno"},
    {"email": "fabio.pereira@eshows.com.br", "senha": "fabio1234", "nome": "Fábio Pereira"},
    {"email": "kaio.geglio@eshows.com.br", "senha": "kaio1234", "nome": "Kaio Geglio"},
]

def verificar_tabela():
    """Verifica se a tabela existe tentando fazer uma query"""
    try:
        result = supabase.table('senhasdash').select("count", count='exact').execute()
        return True
    except Exception as e:
        if "relation" in str(e) and "does not exist" in str(e):
            return False
        # Se for outro erro, a tabela pode existir mas ter outro problema
        print(f"Aviso ao verificar tabela: {e}")
        return True

def criar_usuarios():
    """Cria os usuários na tabela senhasdash"""
    print("\n=== Populando tabela senhasdash ===\n")
    
    criados = 0
    atualizados = 0
    erros = 0
    
    for usuario in usuarios:
        try:
            # Gera o hash da senha
            senha_hash = bcrypt.hashpw(
                usuario['senha'].encode('utf-8'), 
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # Dados para inserir
            dados = {
                "email": usuario['email'],
                "senha_hash": senha_hash,
                "nome": usuario['nome'],
                "ativo": True
            }
            
            # Tenta inserir o usuário
            result = supabase.table('senhasdash').insert(dados).execute()
            
            if result.data:
                print(f"✅ Usuário criado: {usuario['email']}")
                criados += 1
                
        except Exception as e:
            # Se o usuário já existe, tenta atualizar a senha
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                try:
                    result = supabase.table('senhasdash').update({
                        "senha_hash": senha_hash,
                        "nome": usuario['nome']
                    }).eq('email', usuario['email']).execute()
                    
                    print(f"🔄 Usuário atualizado: {usuario['email']}")
                    atualizados += 1
                except Exception as update_error:
                    print(f"❌ Erro ao atualizar {usuario['email']}: {update_error}")
                    erros += 1
            else:
                print(f"❌ Erro ao criar {usuario['email']}: {e}")
                erros += 1
    
    print(f"\n📊 Resumo:")
    print(f"   - Criados: {criados}")
    print(f"   - Atualizados: {atualizados}")
    print(f"   - Erros: {erros}")
    
    print("\n📋 Credenciais dos usuários:")
    print("-" * 60)
    print(f"{'Email':<40} | {'Senha':<15}")
    print("-" * 60)
    for usuario in usuarios:
        print(f"{usuario['email']:<40} | {usuario['senha']:<15}")
    print("-" * 60)

def main():
    print("=== Configuração do Sistema de Autenticação ===")
    
    # Verifica se a tabela existe
    print("\n1. Verificando tabela senhasdash...")
    if verificar_tabela():
        print("✅ Tabela senhasdash encontrada!")
    else:
        print("❌ Tabela senhasdash não encontrada!")
        print("\n⚠️  ATENÇÃO: Você precisa criar a tabela primeiro!")
        print("\n📝 Execute o seguinte SQL no Supabase Dashboard:")
        print("   (https://app.supabase.com → SQL Editor)\n")
        
        # Mostra o SQL
        sql_file = Path(__file__).parent.parent.parent / "supabase/migrations/create_senhasdash_table.sql"
        if sql_file.exists():
            with open(sql_file, 'r', encoding='utf-8') as f:
                print("=" * 80)
                print(f.read())
                print("=" * 80)
        
        print("\n❌ Execute o SQL acima no Supabase e depois rode este script novamente.")
        return
    
    # Cria/atualiza os usuários
    criar_usuarios()
    
    print("\n✅ Configuração concluída!")
    print("\n🚀 Para testar o login:")
    print("   1. Execute: python -m app.main")
    print("   2. Acesse: http://localhost:8050")
    print("   3. Use um dos emails acima com a senha correspondente")

if __name__ == "__main__":
    main()