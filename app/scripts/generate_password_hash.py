#!/usr/bin/env python3
"""
Script para gerar hash de senha para o sistema de autenticação.
Uso: python generate_password_hash.py
"""

import bcrypt
import getpass

def generate_password_hash():
    """Gera um hash bcrypt para uma senha fornecida pelo usuário"""
    print("=== Gerador de Hash de Senha ===\n")
    
    # Solicita a senha sem ecoar na tela
    password = getpass.getpass("Digite a senha para gerar o hash: ")
    
    if not password:
        print("Erro: Senha não pode ser vazia!")
        return
    
    # Confirma a senha
    password_confirm = getpass.getpass("Confirme a senha: ")
    
    if password != password_confirm:
        print("Erro: As senhas não coincidem!")
        return
    
    # Gera o hash
    print("\nGerando hash...")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    hash_string = hashed.decode('utf-8')
    
    print("\n✅ Hash gerado com sucesso!")
    print(f"\nHash: {hash_string}")
    print("\nAdicione esta linha no seu arquivo .env:")
    print(f"ADMIN_PASSWORD_HASH={hash_string}")
    
    # Verifica o hash gerado
    if bcrypt.checkpw(password.encode('utf-8'), hash_string.encode('utf-8')):
        print("\n✅ Hash verificado com sucesso!")
    else:
        print("\n❌ Erro na verificação do hash!")

if __name__ == "__main__":
    generate_password_hash()