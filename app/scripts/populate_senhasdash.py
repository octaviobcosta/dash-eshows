#!/usr/bin/env python3
"""
Script para popular a tabela senhasdash com os usuários iniciais.
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

def criar_usuarios():
    """Cria os usuários na tabela senhasdash"""
    print("=== Populando tabela senhasdash ===\n")
    
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
            else:
                print(f"❌ Erro ao criar: {usuario['email']}")
                
        except Exception as e:
            # Se o usuário já existe, tenta atualizar a senha
            if "duplicate key" in str(e).lower():
                try:
                    result = supabase.table('senhasdash').update({
                        "senha_hash": senha_hash,
                        "nome": usuario['nome'],
                        "atualizado_em": datetime.now().isoformat()
                    }).eq('email', usuario['email']).execute()
                    
                    print(f"🔄 Usuário atualizado: {usuario['email']}")
                except Exception as update_error:
                    print(f"❌ Erro ao atualizar {usuario['email']}: {update_error}")
            else:
                print(f"❌ Erro ao criar {usuario['email']}: {e}")
    
    print("\n✅ Processo concluído!")
    print("\nSenhas dos usuários:")
    print("-" * 50)
    for usuario in usuarios:
        print(f"{usuario['email']:<35} | {usuario['senha']}")
    print("-" * 50)

if __name__ == "__main__":
    criar_usuarios()