"""
logging_config.py
Inicializa a configuração global de logging da aplicação.

Uso:  basta importar este módulo uma única vez,
geramente no entry-point do app (ex.: main.py).
"""

import logging
import os
from pathlib import Path

# 1) Lê o nível de log do ambiente; padrão = INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 2) Valida o nível informado; fallback para INFO
level = getattr(logging, LOG_LEVEL, logging.INFO)

# 3) Formato único para todo o projeto
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"

# 4) Diretório opcional para arquivos de log (ex.: logs/app.log)
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=level,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),  # console
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
    ],
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Evita que bibliotecas externas (ex.: httpx) poluam o output
for noisy in ("httpx", "supabase_py"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
