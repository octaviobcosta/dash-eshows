#!/usr/bin/env python3
"""Script para testar conexões com APIs de IA"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def test_openai():
    print("\n=== Testando OpenAI ===")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("[ERRO] OPENAI_API_KEY não encontrada no .env")
        return False
    
    print(f"[INFO] Chave encontrada: {api_key[:20]}...{api_key[-5:]}")
    print(f"[INFO] Tamanho: {len(api_key)} caracteres")
    
    # Verifica se há duplicação
    if api_key.startswith("sk-sk-") or api_key.count("sk-") > 1:
        print("[AVISO] A chave parece ter prefixo duplicado!")
    
    try:
        import openai
        openai.api_key = api_key
        
        # Teste simples
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Modelo mais barato
            messages=[{"role": "user", "content": "Responda apenas: OK"}],
            max_tokens=5
        )
        
        print(f"[SUCESSO] OpenAI funcionando! Resposta: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"[ERRO] {type(e).__name__}: {str(e)}")
        return False

def test_anthropic():
    print("\n=== Testando Anthropic ===")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("[ERRO] ANTHROPIC_API_KEY não encontrada no .env")
        return False
    
    print(f"[INFO] Chave encontrada: {api_key[:20]}...{api_key[-5:]}")
    print(f"[INFO] Tamanho: {len(api_key)} caracteres")
    
    try:
        import anthropic
        client = anthropic.Client(api_key=api_key)
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "Responda apenas: OK"}]
        )
        
        print(f"[SUCESSO] Anthropic funcionando! Resposta: {response.content[0].text}")
        return True
        
    except Exception as e:
        print(f"[ERRO] {type(e).__name__}: {str(e)}")
        return False

def main():
    print("=== Teste de APIs de IA ===")
    
    openai_ok = test_openai()
    anthropic_ok = test_anthropic()
    
    print("\n=== Resumo ===")
    print(f"OpenAI: {'[OK]' if openai_ok else '[FALHOU]'}")
    print(f"Anthropic: {'[OK]' if anthropic_ok else '[FALHOU]'}")
    
    if not openai_ok and not anthropic_ok:
        print("\n[CRITICO] Nenhuma API está funcionando!")
        print("\nPara corrigir:")
        print("1. Gere novas chaves:")
        print("   - OpenAI: https://platform.openai.com/api-keys")
        print("   - Anthropic: https://console.anthropic.com/settings/keys")
        print("2. Atualize no arquivo .env")
        print("3. Reinicie a aplicação")
    elif not anthropic_ok:
        print("\n[AVISO] Sistema funcionará com fallback para OpenAI")

if __name__ == "__main__":
    main()