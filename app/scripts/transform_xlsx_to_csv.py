# transform_xlsx_to_csv.py
import pandas as pd
from pathlib import Path
import csv, re
import logging

logger = logging.getLogger(__name__)

FILE_IN  = Path("dados.xlsx")
FILE_OUT = Path("dados_limpo.csv")

# 1) Carrega todas as abas ou escolha uma
df = pd.read_excel(FILE_IN, sheet_name=0, dtype=str)     # tudo como texto → evita cast errado

# 2) Limpeza básica ----------------------------------------------------------
# Normaliza cabeçalhos: snake_case, sem espaços/acentos
def normalize_header(col: str) -> str:
    col = col.strip()
    col = col.lower()
    col = re.sub(r"[^\w\s]", "", col)        # remove pontuação
    col = re.sub(r"\s+", "_", col)           # troca espaço por _
    return col

df.columns = [normalize_header(c) for c in df.columns]

# Remove linhas e colunas 100 % vazias
df.dropna(how="all", inplace=True)
df.dropna(axis=1, how="all", inplace=True)

# Strip em strings (tira espaços antes/depois)
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

# Exemplo de conversão de data
for col in df.columns:
    if "data" in col:           # ou use um dicionário {col: 'date'}
        df[col] = pd.to_datetime(df[col], errors="coerce")\
                      .dt.strftime("%Y-%m-%d")

# Exemplo de conversão numérica com vírgula decimal
num_cols = ["valor_total", "preco_unitario"]          # ajuste às suas colunas
for col in num_cols:
    df[col] = (
        df[col]
        .str.replace(".", "")         # tira separador de milhar
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

# 3) Exporta CSV seguro ------------------------------------------------------
df.to_csv(
    FILE_OUT,
    index=False,
    encoding="utf-8",
    sep=",",                 # se tiver muitos campos com vírgula, use ; aqui
    quoting=csv.QUOTE_MINIMAL,
    line_terminator="\n",
)

logger.debug("Arquivo salvo em %s", FILE_OUT.resolve())
