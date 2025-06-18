#!/usr/bin/env python
"""
Entry point para rodar a aplicação
Uso: python run.py
"""
import sys
from pathlib import Path

# Adiciona o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

# Importa e roda a aplicação
from app.core.main import dash_app

if __name__ == "__main__":
    dash_app.run_server(
        debug=True,
        use_reloader=True,  # Habilita hot reload
        host="0.0.0.0",
        port=8050
    )