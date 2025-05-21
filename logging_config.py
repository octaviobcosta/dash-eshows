"""
logging_config.py
Configuração global de logging + filtros de warnings.

Importe UMA vez (ex.: main.py). Qualquer módulo posterior já herda.
"""

import logging, warnings, os
from pathlib import Path
import pandas as pd   # só para o filtro SettingWithCopy

# ────────────────── Logging ──────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
level     = getattr(logging, LOG_LEVEL, logging.INFO)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level   = level,
    format  = LOG_FORMAT,
    datefmt = "%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
    ],
)

for noisy in ("httpx", "supabase_py"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ────────────────── Warnings ──────────────────
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
