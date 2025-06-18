#!/usr/bin/env python3
"""Script para testar a conexão com Anthropic API"""

import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def test_anthropic():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("[ERRO] ANTHROPIC_API_KEY não encontrada no .env")
        return
    
    print(f"[OK] Chave encontrada: {api_key[:15]}...{api_key[-5:]}")
    print(f"[OK] Tamanho da chave: {len(api_key)} caracteres")
    
    try:
        import anthropic
        client = anthropic.Client(api_key=api_key)
        
        # Teste simples
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Modelo mais barato para teste
            max_tokens=10,
            messages=[{"role": "user", "content": "Diga apenas 'OK'"}]
        )
        
        print(f"[SUCESSO] Conexão bem-sucedida! Resposta: {response.content[0].text}")
        
    except Exception as e:
        print(f"[ERRO] Erro na conexão: {type(e).__name__}: {str(e)}")
        
        # Sugestões
        print("\n[DICA] Possíveis soluções:")
        print("1. Verifique se a chave está correta e não expirou")
        print("2. Gere uma nova chave em: https://console.anthropic.com/settings/keys")
        print("3. Atualize a chave no arquivo .env")

if __name__ == "__main__":
    test_anthropic()