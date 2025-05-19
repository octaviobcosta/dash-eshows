#!/usr/bin/env python
"""
ETL custosabertos: lê custosabertos.xlsx, remove coluna “DESCRIÇÃO”,
converte ‘VALOR’ de texto BR → int (centavos) e gera custosabertos.csv
"""

from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# --- Configs -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SRC_XLSX = ROOT / "data" / "xlsx" / "custosabertos.xlsx"
DST_CSV  = ROOT / "data" / "csv"  / "custosabertos.csv"

# --- 1) Ler planilha ----------------------------------------------------------
df = pd.read_excel(SRC_XLSX, dtype=str)

# --- 2) Remover coluna “DESCRIÇÃO” (se existir) ------------------------------
if "DESCRIÇÃO" in df.columns:
    df = df.drop(columns=["DESCRIÇÃO"])

# --- 3) Converter 'VALOR' → centavos (int) ------------------------------------
def brl_to_cents(brl_str: str) -> int:
    """
    Converte "1.234,56" → 123456 (centavos), de acordo com o formato brasileiro.
    """
    if pd.isna(brl_str) or brl_str.strip() == "":
        return 0
    
    # **Depuração**: Mostra o valor lido
    logger.debug("Valor lido: %s", brl_str)

    # Verificar se já está no formato correto (ponto para milhar, vírgula para decimal)
    if ',' in brl_str:  
        # Remove ponto de milhar (caso haja) e substitui vírgula por ponto para decimal
        brl_str = brl_str.replace(".", "")  # Remove os pontos de milhar
        brl_str = brl_str.replace(",", ".")  # Substitui vírgula por ponto (caso seja decimal)
    elif '.' in brl_str:
        # Se já tem ponto decimal (ex: 8440.77), apenas substitui a vírgula por ponto, se necessário
        brl_str = brl_str.replace(",", ".")  # Troca vírgula por ponto, se existir

    # **Depuração**: Verifica como ficou o valor após substituição
    logger.debug("Valor após substituição: %s", brl_str)

    # Converte para float, depois multiplica por 100 para centavos
    value_in_reais = float(brl_str)
    value_in_cents = round(value_in_reais * 100)  # Multiplica por 100 para centavos

    # **Depuração**: Verifica o valor final convertido
    logger.debug("Valor convertido em centavos: %s", value_in_cents)

    return value_in_cents

# Aplicar a conversão para a coluna 'VALOR'
df["VALOR"] = df["VALOR"].apply(brl_to_cents)

# --- 4) snake_case + sem acentos ---------------------------------------------
df.columns = (
    df.columns
      .str.strip()
      .str.lower()
      .str.replace(" ", "_")
      .str.normalize("NFKD")
      .str.encode("ascii", "ignore")
      .str.decode("ascii")
)

# --- 5) Salvar CSV -----------------------------------------------------------
df.to_csv(DST_CSV, index=False, float_format="%.0f")  # Não queremos casas decimais no CSV
logger.debug("✅ CSV gerado em %s", DST_CSV)
