#!/usr/bin/env python
"""
Carrega app/custosabertos.csv e insere em lote na tabela Supabase.
Execute apenas uma vez (ou ajuste lógica upsert se quiser rodar sempre).
"""

from pathlib import Path
import pandas as pd
from supabase import create_client

# --- Configs ---------------------------------------------------------------
URL = "https://yrvtmgrqxhqltckpfizn.supabase.co"
KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlydnRtZ3JxeGhxbHRja3BmaXpuIiwicm9sZSI6"
    "InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NTY4NjEzMSwiZXhwIjoyMDYxMjYyMTMxfQ."
    "M-oOVld1XwaZ2r2RDqeHVSrMpHb1pwYLqUYEJ041VJg"
)
CSV_PATH = Path(__file__).resolve().parent.parent / "app" / "custosabertos.csv"
TABLE = "custosabertos"
BATCH = 100  # tamanho do lote

# --- Supabase client --------------------------------------------------------
client = create_client(URL, KEY)

# --- Ler CSV ---------------------------------------------------------------
df = pd.read_csv(CSV_PATH)
records = df.to_dict("records")
total = len(records)
print(f"Lendo {total} linhas de {CSV_PATH.name}…")

# --- Inserir em lotes -------------------------------------------------------
for start in range(0, total, BATCH):
    end = start + BATCH
    batch = records[start:end]
    resp = client.table(TABLE).insert(batch).execute()
    if resp.error:
        raise RuntimeError(resp.error.message)
    print(f"✓ Inseridos {end if end < total else total}/{total}")

print("🎉  Importação concluída com sucesso!")
