"""
logging_config.py
Configuração global de logging + filtros de warnings.

Importe uma única vez no entry-point da aplicação (ex.: main.py).
"""

import logging
import os
import warnings
from pathlib import Path
import pandas as pd

# ───────────────────────────────
# Logging
# ───────────────────────────────

# 1) Nível de log via variável de ambiente (default = INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
level = getattr(logging, LOG_LEVEL, logging.INFO)  # fallback seguro

# 2) Formato padrão
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"

# 3) Saída em console + arquivo
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=level,
    format=LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),                       # terminal
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),  # arquivo
    ],
)

# 4) Silencia bibliotecas barulhentas
for noisy in ("httpx", "supabase_py"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ───────────────────────────────
# Filtros de warnings
# ───────────────────────────────
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
