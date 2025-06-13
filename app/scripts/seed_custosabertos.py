#!/usr/bin/env python
"""
Seed da tabela `custosabertos`.

• Lê app/custosabertos.csv (já em centavos, sem coluna descrição)
• Faz upsert em lotes na Supabase, usando id_custo como chave
• Seguro para rodar mais de uma vez (não duplica)

Execute:
    python app/scripts/seed_custosabertos.py
"""

from pathlib import Path
import os
import pandas as pd
from supabase import create_client
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 1) Configurações
# ──────────────────────────────────────────────────────────────
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

if not URL or not KEY:
    raise ValueError(
        "SUPABASE_URL e SUPABASE_KEY devem estar definidas nas variáveis de ambiente. "
        "Copie .env.example para .env e preencha com suas credenciais."
    )
TABLE_NAME = "custosabertos"
BATCH_SIZE = 100

# Caminho do CSV (um nível acima de app/scripts)
CSV_PATH = Path(__file__).resolve().parents[1] / "custosabertos.csv"

# ──────────────────────────────────────────────────────────────
# 2) Ler CSV
# ──────────────────────────────────────────────────────────────
if not CSV_PATH.exists():
    raise FileNotFoundError(f"Arquivo não encontrado: {CSV_PATH}")

df = pd.read_csv(CSV_PATH)
records = df.to_dict("records")
total = len(records)
logger.debug("🔹 Lidas %s linhas de %s", total, CSV_PATH.relative_to(Path.cwd()))

# ──────────────────────────────────────────────────────────────
# 3) Conectar na Supabase
# ──────────────────────────────────────────────────────────────
client = create_client(URL, KEY)

# ──────────────────────────────────────────────────────────────
# 4) Upsert em lotes
# ──────────────────────────────────────────────────────────────
for start in range(0, total, BATCH_SIZE):
    batch = records[start : start + BATCH_SIZE]
    resp = client.table(TABLE_NAME).upsert(batch, on_conflict="id_custo")  # evita duplic
