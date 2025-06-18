#!/usr/bin/env python3
"""
Script de verificação de segurança
Verifica se há tokens ou credenciais expostas no código
"""

import os
import re
import sys
from pathlib import Path

# Padrões para detectar possíveis credenciais
PATTERNS = [
    # Tokens genéricos
    (r'["\']?[Tt]oken["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{20,}["\']', 'Token genérico'),
    
    # API Keys
    (r'["\']?[Aa]pi[_\-]?[Kk]ey["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{20,}["\']', 'API Key'),
    
    # Senhas
    (r'["\']?[Pp]assword["\']?\s*[:=]\s*["\'][^"\']{8,}["\']', 'Senha'),
    
    # Tokens específicos
    (r'sk[_\-]live[_\-][A-Za-z0-9]{24,}', 'Stripe Live Key'),
    (r'sk[_\-]test[_\-][A-Za-z0-9]{24,}', 'Stripe Test Key'),
    (r'github_pat_[A-Za-z0-9]{22,}', 'GitHub Personal Access Token'),
    (r'ghp_[A-Za-z0-9]{36,}', 'GitHub Personal Access Token'),
    (r'gho_[A-Za-z0-9]{36,}', 'GitHub OAuth Token'),
    (r'sbp_[A-Za-z0-9]{40,}', 'Supabase Access Token'),
    (r'rnd_[A-Za-z0-9]{20,}', 'Render API Key'),
    
    # URLs com credenciais
    (r'["\']?https?://[^"\'\s]*:[^"\'\s]*@[^"\'\s]+["\']?', 'URL com credenciais'),
]

# Arquivos e diretórios para ignorar
IGNORE_PATTERNS = [
    '.git', '.venv', 'venv', '__pycache__', 'node_modules',
    '*.pyc', '*.pyo', '*.pyd', '.env*', '*.log', 
    'security-check.py',  # Este próprio arquivo
]

def should_ignore(path):
    """Verifica se o arquivo/diretório deve ser ignorado."""
    path_str = str(path)
    for pattern in IGNORE_PATTERNS:
        if pattern.startswith('*'):
            if path_str.endswith(pattern[1:]):
                return True
        elif pattern in path_str:
            return True
    return False

def check_file(filepath):
    """Verifica um arquivo em busca de credenciais."""
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern, desc in PATTERNS:
                if re.search(pattern, line):
                    # Ignora se for um exemplo ou placeholder
                    if any(placeholder in line.lower() for placeholder in 
                           ['example', 'placeholder', 'your_', 'replace', 'changeme']):
                        continue
                    
                    issues.append({
                        'file': filepath,
                        'line': line_num,
                        'type': desc,
                        'content': line.strip()[:100] + '...' if len(line) > 100 else line.strip()
                    })
    except Exception as e:
        pass  # Ignora erros de leitura
    
    return issues

def main():
    """Função principal."""
    print("[SEGURANCA] Verificando possiveis credenciais expostas...\n")
    
    root_path = Path.cwd()
    all_issues = []
    
    # Percorre todos os arquivos
    for path in root_path.rglob('*'):
        if path.is_file() and not should_ignore(path):
            issues = check_file(path)
            all_issues.extend(issues)
    
    # Exibe resultados
    if all_issues:
        print(f"[AVISO] Encontrados {len(all_issues)} possiveis problemas de seguranca:\n")
        
        for issue in all_issues:
            print(f"Arquivo: {issue['file']}:{issue['line']}")
            print(f"   Tipo: {issue['type']}")
            print(f"   Conteudo: {issue['content']}")
            print()
        
        print("\n[!] Verifique se estas credenciais sao reais e remova-as do codigo!")
        print("[DICA] Use variaveis de ambiente (.env) para armazenar credenciais.\n")
        return 1
    else:
        print("[OK] Nenhuma credencial suspeita encontrada!\n")
        print("[DICA] Lembre-se sempre de:")
        print("   - Usar variaveis de ambiente para credenciais")
        print("   - Adicionar .env ao .gitignore")
        print("   - Revisar mudancas antes do commit\n")
        return 0

if __name__ == "__main__":
    sys.exit(main())