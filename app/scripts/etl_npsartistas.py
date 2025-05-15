#!/usr/bin/env python
"""
ETL para npsartistas.xlsx → npsartistas.csv

Mantém apenas:
    • ID                (chave primária no Supabase)
    • Data              (data da pesquisa)
    • NPS Eshows
    • CSAT Eshows
    • Operador_1
    • Operador_2
    • CSAT Operador_1
    • CSAT Operador_2

Salva em: app/npsartistas.csv
"""

from pathlib import Path
import pandas as pd

# ────────── paths ──────────
BASE_DIR  = Path(__file__).resolve().parents[1]         # …/dash-eshows/app
SRC_XLSX  = BASE_DIR / "npsartistas.xlsx"
DST_CSV   = BASE_DIR / "npsartistas.csv"

# ────────── leitura ─────────
df = pd.read_excel(SRC_XLSX, dtype=str)

# ────────── seleção e ordem ─
cols_keep = [
    "ID",
    "Data",
    "NPS Eshows",
    "CSAT Eshows",
    "Operador_1",
    "Operador_2",
    "CSAT Operador_1",
    "CSAT Operador_2",
]
df = df[[c for c in cols_keep if c in df.columns]].copy()
df = df.reindex(columns=cols_keep)          # garante ordem

# ────────── tipos mínimos ───
if "Data" in df.columns:
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date

# ────────── grava CSV ───────
df.to_csv(DST_CSV, index=False)
print(f"✅ CSV gerado em {DST_CSV}")
