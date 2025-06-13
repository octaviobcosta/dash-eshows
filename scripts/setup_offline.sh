#!/bin/bash
# Script de setup offline para Linux/macOS

# Cria venv se não existir
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# Ativa a venv
source .venv/bin/activate

# Instala pacotes a partir da wheelhouse
python -m pip install --no-index --find-links ./wheelhouse -r requirements_offline.txt

# Executa o app
python -m app.main