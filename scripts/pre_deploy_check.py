#!/usr/bin/env python3
"""
Script de verificação pré-deploy
Executa todas as verificações necessárias antes de fazer push para produção
"""

import sys
import subprocess
import os
from pathlib import Path

def run_command(cmd):
    """Executa comando e retorna resultado"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_imports():
    """Verifica se todas as importações estão corretas"""
    print("🔍 Verificando importações...")
    
    # Lista de arquivos Python principais
    py_files = list(Path("app").glob("*.py"))
    
    errors = []
    for file in py_files:
        print(f"  Verificando {file}...")
        success, stdout, stderr = run_command(f"python3 -m py_compile {file}")
        if not success:
            errors.append(f"❌ Erro em {file}: {stderr}")
    
    if errors:
        print("\n".join(errors))
        return False
    
    print("✅ Todas as importações estão corretas")
    return True

def check_app_startup():
    """Tenta inicializar a aplicação em modo dry-run"""
    print("\n🚀 Verificando inicialização da aplicação...")
    
    # Tenta importar o módulo principal
    try:
        import app.main
        print("✅ Aplicação pode ser importada com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao importar aplicação: {e}")
        return False

def check_required_files():
    """Verifica se todos os arquivos necessários existem"""
    print("\n📁 Verificando arquivos obrigatórios...")
    
    required_files = [
        "app/main.py",
        "app/auth.py",
        "app/auth_improved.py",
        "app/data_manager.py",
        "app/update_processor.py",
        "app/update_executor.py",
        "app/update_modal_improved.py",
        "assets/login.css",
        "assets/login_improved.css",
        "assets/modal_styles.css",
        "assets/custom.css",
        "requirements.txt",
        "runtime.txt",
        "render.yaml",
        ".env.example"
    ]
    
    missing = []
    for file in required_files:
        if not Path(file).exists():
            missing.append(f"❌ Arquivo faltando: {file}")
    
    if missing:
        print("\n".join(missing))
        return False
    
    print("✅ Todos os arquivos obrigatórios presentes")
    return True

def check_env_variables():
    """Verifica se as variáveis de ambiente necessárias estão documentadas"""
    print("\n🔐 Verificando documentação de variáveis de ambiente...")
    
    env_example = Path(".env.example")
    if not env_example.exists():
        print("❌ Arquivo .env.example não encontrado")
        return False
    
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "JWT_SECRET_KEY",
        "FLASK_SECRET_KEY"
    ]
    
    content = env_example.read_text()
    missing = []
    
    for var in required_vars:
        if var not in content:
            missing.append(f"❌ Variável não documentada: {var}")
    
    if missing:
        print("\n".join(missing))
        return False
    
    print("✅ Todas as variáveis obrigatórias documentadas")
    return True

def check_git_status():
    """Verifica status do git"""
    print("\n📊 Verificando status do Git...")
    
    # Verifica se há arquivos não commitados
    success, stdout, stderr = run_command("git status --porcelain")
    if stdout.strip():
        print("⚠️  Arquivos não commitados detectados:")
        print(stdout)
        return False
    
    print("✅ Todos os arquivos commitados")
    return True

def main():
    """Executa todas as verificações"""
    print("=" * 50)
    print("🛡️  VERIFICAÇÃO PRÉ-DEPLOY")
    print("=" * 50)
    
    checks = [
        check_required_files,
        check_imports,
        check_app_startup,
        check_env_variables,
        check_git_status
    ]
    
    all_passed = True
    
    for check in checks:
        if not check():
            all_passed = False
    
    print("\n" + "=" * 50)
    
    if all_passed:
        print("✅ TODAS AS VERIFICAÇÕES PASSARAM!")
        print("👍 Pronto para deploy")
        return 0
    else:
        print("❌ VERIFICAÇÕES FALHARAM!")
        print("🛑 NÃO faça deploy até corrigir os problemas")
        return 1

if __name__ == "__main__":
    sys.exit(main())