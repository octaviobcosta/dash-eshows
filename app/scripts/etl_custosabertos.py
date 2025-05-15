#!/usr/bin/env python
"""
ETL simples: lê custosabertos.xlsx, limpa colunas,
converte 'Valor' para centavos (int) e gera custosabertos.csv.
"""

from pathlib import Path
import pandas as pd

# --- Configs -----------------------------------------------------------------
SRC_XLSX = Path(__file__).resolve().parents[1] / "data" / "xlsx" / "custosabertos.xlsx"
DST_CSV  = Path(__file__).resolve().parents[1] / "data" / "csv"  / "custosabertos.csv"

# --- 1) Ler planilha ----------------------------------------------------------
df = pd.read_excel(SRC_XLSX, dtype=str)

# --- 2) Remover coluna 'DESCRIÇÃO' -------------------------------------------
if "DESCRIÇÃO" in df.columns:
    df = df.drop(columns=["DESCRIÇÃO"])

# --- 3) Converter 'VALOR' (ex.: "11.250,00") para centavos -------------------
def brl_to_cents(brl_str: str) -> int:
    """
    Converte string em formato brasileiro (1.234,56) para int em centavos (123456).
    """
    if pd.isna(brl_str) or brl_str == "":
        return 0
    # remove pontos de milhar e vírgula decimal
    cent_str = brl_str.replace(".", "").replace(",", "")
    return int(cent_str)

df["VALOR"] = df["VALOR"].apply(brl_to_cents).astype("Int64")  # nullable int64

# --- 4) Ajustar nomes de colunas para snake_case, se quiser padronizar -------
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
    .str.normalize("NFKD")        # remove acentos
    .str.encode("ascii", "ignore")
    .str.decode("ascii")
)

# --- 5) Salvar CSV -----------------------------------------------------------
df.to_csv(DST_CSV, index=False)
print(f"✅ CSV gerado em {DST_CSV}")
