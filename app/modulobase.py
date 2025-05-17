"""
modulobase.py — processamento, sanitização e cache dos DataFrames
-----------------------------------------------------------------
• Sanitiza e otimiza:
      – BaseEshows
      – Base2
      – Pessoas
      – Ocorrências
      – Inadimplência  (boleto­­casas + boleto­­artistas)
      – Metas
• Cache em RAM para acelerar chamadas repetidas.
• Otimização de memória: down-cast numéricos e object→category quando útil.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Tuple

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from .data_manager import (
    get_df_eshows,
    get_df_base2,
    get_df_ocorrencias,
    get_df_pessoas,
    get_df_inadimplencia,
    get_df_metas,
    get_df_custosabertos,          # NOVO
    dedup,
    get_df_npsartistas,            # NOVO
)
from .column_mapping import rename_columns, SUPPLIER_TO_SETOR, PERCENT_COLS

# ─────────────────────────────  logging  ────────────────────────────
logger = logging.getLogger("modulobase")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ────────────────────────────  caches  ──────────────────────────────
_df_eshows_cache:            pd.DataFrame | None = None
_df_eshows_excluidos_cache:  pd.DataFrame | None = None
_df_base2_cache:             pd.DataFrame | None = None
_df_pessoas_cache:           pd.DataFrame | None = None
_df_ocorrencias_cache:       pd.DataFrame | None = None
_inad_casas_cache:           pd.DataFrame | None = None
_inad_artistas_cache:        pd.DataFrame | None = None
_df_metas_cache:             pd.DataFrame | None = None
_df_custosabertos_cache:     pd.DataFrame | None = None          # NOVO
_df_npsartistas_cache:       pd.DataFrame | None = None          # NOVO

# Colunas mantidas ao salvar em Parquet
COLUMNS_DASH: dict[str, list[str] | None] = {
    "baseeshows": [
        "Id do Show", "Id da Casa", "Casa", "Cidade", "Estado", "Data",
        "Nome do Artista", "Grupo", "Valor Total do Show", "Valor Artista",
        "Comissão B2B", "Comissão B2C", "Antecipação de Cachês",
        "Curadoria", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais",
        "Avaliação", "Ano", "Mês", "Dia do Show",
    ],
    "base2": ["Data", "Ano", "Mês", "Faturamento", "Custos", "Imposto", "LucroLiquido"],
    "pessoas": [
        "ID", "Nome", "Funcao", "DataInicio", "DataFinal",
        "Salário Mensal", "AnoInicio", "MesInicio", "AnoFinal", "MesFinal", "DataSaida",
    ],
    "ocorrencias": None,
    "boletocasas": ["ID_Boleto", "Casa", "Valor", "Valor Real", "Status", "Data Vencimento"],
    "boletoartistas": ["ID_Boleto", "NOME", "Adiantamento", "Valor Bruto", "ID", "Data Vencimento"],
    "npsartistas": ["Data", "NPS Eshows", "CSAT Eshows", "CSAT Operador 1", "CSAT Operador 2"],
}

# ╭───────────────────────────  helpers  ─────────────────────────────╮
def _slug(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text))
    return re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()


def otimizar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    for col in df.select_dtypes(include="int64").columns:
        df[col] = pd.to_numeric(df[col], downcast="integer", errors="ignore")
    for col in df.select_dtypes(include="float64").columns:
        df[col] = pd.to_numeric(df[col], downcast="float", errors="ignore")

    for col in df.select_dtypes(include="object").columns:
        try:
            nunq = df[col].nunique(dropna=False)
            if nunq and nunq / len(df) < 0.5:
                df[col] = df[col].astype("category", errors="ignore")
        except TypeError:
            pass
    return df

# ──────────────────  SANITIZE NPS Artistas  ───────────────────────
def sanitize_npsartistas_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    • Converte Data → datetime
    • Garante tipos numéricos inteiros nas colunas NPS/CSAT
    """
    df = rename_columns(dedup(df_raw), "npsartistas").copy()

    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

    for col in ("NPS Eshows", "CSAT Eshows", "CSAT Operador 1", "CSAT Operador 2"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int16", errors="ignore")

    return otimizar_tipos(df.reset_index(drop=True))

# ╭──────────────────  SANITIZE Custos Abertos  ──────────────────────╮
def sanitize_custosabertos_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    • Converte data_competencia / data_vencimento para datetime
    • Adiciona coluna Setor via SUPPLIER_TO_SETOR
    • Valor já em centavos (int64)
    """
    df = dedup(df_raw.copy())

    # datas
    for col in ("data_competencia", "data_vencimento"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # numérico
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0).astype("Int64")

    # setor
    if "fornecedor" in df.columns:
        df["Setor"] = df["fornecedor"].map(SUPPLIER_TO_SETOR).fillna("Indefinido")

    return otimizar_tipos(df.reset_index(drop=True))

# ╭──────────────────────  SANITIZE BaseEshows  ──────────────────────╮
def sanitize_eshows_df(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Limpa a BaseEshows.

    – Remove colunas *Primeiro_Dia_Mes* e *Data de Pagamento*
    – Converte Casa / Cidade / Grupo / Estado para category
    – Retorna (df_clean, df_excluidos)
    """
    df_clean = df_raw.copy()
    df_excl = pd.DataFrame(columns=df_clean.columns.tolist() + ["Motivo"])

    # 1) Renomeações ---------------------------------------------------
    mapeamento = {
        "p_ID": "Id do Show",
        "c_ID": "Id da Casa",
        "Data": "Data do Show",
        "Data_Pagamento": "Data de Pagamento",
        "Valor_Bruto": "Valor Total do Show",
        "Valor_Liquido": "Valor Artista",
        "Comissao_Eshows_B2B": "Comissão B2B",
        "Comissao_Eshows_B2C": "Comissão B2C",
        "Taxa_Adiantamento": "Antecipação de Cachês",
        "Curadoria": "Curadoria",
        "SAAS_Percentual": "SaaS Percentual",
        "SAAS_Mensalidade": "SaaS Mensalidade",
        "Taxa_Emissao_NF": "Notas Fiscais",
        "GRUPO_CLIENTES": "Grupo",
        "NOTA": "Avaliação",
        "Ano": "Ano",
        "Mês": "Mês",
        "Dia": "Dia do Show",
    }
    df_clean.rename(columns={k: v for k, v in mapeamento.items() if k in df_clean.columns},
                    inplace=True)

    # 2) Duplicados ----------------------------------------------------
    if "Id do Show" in df_clean.columns:
        dup = df_clean.duplicated("Id do Show", keep="first")
        df_excl = pd.concat([df_excl, df_clean[dup].assign(Motivo="id repetido")])
        df_clean = df_clean[~dup]

    # 3) Linhas de teste ----------------------------------------------
    for col, motivo in [("Nome do Artista", "nome teste"),
                        ("Casa", "casa teste")]:
        if col in df_clean.columns:
            mask = df_clean[col].str.contains("Teste", case=False, na=False)
            df_excl = pd.concat([df_excl, df_clean[mask].assign(Motivo=motivo)])
            df_clean = df_clean[~mask].dropna(subset=[col])

    # 4) Valor Total nulo ---------------------------------------------
    if "Valor Total do Show" in df_clean.columns:
        mask = df_clean["Valor Total do Show"].isna()
        df_excl = pd.concat([df_excl, df_clean[mask].assign(Motivo="valor nulo")])
        df_clean = df_clean[~mask]

    # 5) Datas ---------------------------------------------------------
    if "Data do Show" in df_clean.columns:
        df_clean["Data do Show"] = pd.to_datetime(df_clean["Data do Show"],
                                                  errors="coerce")
        mask = df_clean["Data do Show"].isna()
        df_excl = pd.concat([df_excl,
                             df_clean[mask].assign(Motivo="data show nula/inválida")])
        df_clean = df_clean[~mask]

    if "Data de Pagamento" in df_clean.columns:
        df_clean["Data de Pagamento"] = pd.to_datetime(
            df_clean["Data de Pagamento"], errors="coerce"
        )

    # 6) Remove colunas pesadas não usadas ----------------------------
    for col in ("Primeiro_Dia_Mes", "Data de Pagamento"):
        df_clean.drop(columns=col, errors="ignore", inplace=True)

    # 7) Padroniza Data / Ano / Mês -----------------------------------
    if "Data do Show" in df_clean.columns:
        df_clean.rename(columns={"Data do Show": "Data"}, inplace=True)

    if "Data" in df_clean.columns:
        df_clean["Data"] = pd.to_datetime(df_clean["Data"], errors="coerce")
        df_clean["Ano"] = df_clean["Data"].dt.year
        df_clean["Mês"] = df_clean["Data"].dt.month

    # 8) Alias de compatibilidade -------------------------------------
    if "Data" in df_clean.columns and "Data do Show" not in df_clean.columns:
        df_clean["Data do Show"] = df_clean["Data"]

    # 9) Strings → category -------------------------------------------
    for col in ("Casa", "Cidade", "Grupo", "Estado"):
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype("category")

    df_clean = otimizar_tipos(df_clean.reset_index(drop=True))
    df_excl = df_excl.reset_index(drop=True)
    return df_clean, df_excl

# ╭───────────────────────  SANITIZE Base 2  ─────────────────────────╮
def _parse_mes_abrev(col: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Converte 'abr-24' → (4, 2024).
    Retorna dois Series (mes, ano) com dtype float64 (podem ter NaN).
    """
    mapa = dict(jan=1, fev=2, mar=3, abr=4, mai=5, jun=6,
                jul=7, ago=8, set=9, out=10, nov=11, dez=12)

    partes = col.astype(str).str.lower().str.extract(r"([a-z]{3})-(\d{2})")
    ok     = partes.notna().all(axis=1)

    mes  = pd.Series(np.nan, index=col.index, dtype=float)
    ano  = pd.Series(np.nan, index=col.index, dtype=float)

    mes.loc[ok] = partes.loc[ok, 0].map(mapa)
    ano.loc[ok] = ("20" + partes.loc[ok, 1]).astype(float)

    return mes, ano


# ────────────────────────────────────────────────────────────────
#  SANITIZADOR DA BASE-2  (financeiro mensal)
# ────────────────────────────────────────────────────────────────
def sanitize_base2_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza a Base-2 e devolve Data, Ano, Mês + numéricos castados.
    """
    df = df_raw.copy()

    # 1) Renomeações ---------------------------------------------------
    mapping = {
        "data": "Data", "competencia": "Data", "ref_month": "Data",
        "ano": "Ano",  "ano_ref": "Ano",
        "mes": "Mês",  "mes_ref": "Mês",
        "faturamento_total": "Faturamento",
        "custos_totais":     "Custos",
        "imposto_total":     "Imposto",
        "lucro_liquido":     "LucroLiquido",
    }
    df.rename(columns={k: v for k, v in mapping.items() if k in df.columns},
              inplace=True)

    # 2) Coluna Data ---------------------------------------------------
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        txt = df["Data"].isna() & df["Data"].astype(str).str.match(r"\d{4}-\d{2}$")
        if txt.any():
            df.loc[txt, "Data"] = pd.to_datetime(
                df.loc[txt, "Data"].astype(str) + "-01", errors="coerce"
            )

    # 3) Gerar Data via Ano/Mês se faltar -----------------------------
    if (("Data" not in df.columns) or df["Data"].isna().all()) \
       and {"Ano", "Mês"}.issubset(df.columns):
        df["Data"] = pd.to_datetime(
            dict(year=pd.to_numeric(df["Ano"], errors="coerce"),
                 month=pd.to_numeric(df["Mês"], errors="coerce"),
                 day=1),
            errors="coerce"
        )

    # 4) Fallback para strings "abr-23" / "04/2024" -------------------
    if "Data" not in df.columns or df["Data"].isna().all():
        if "Mês" in df.columns:
            s = df["Mês"].astype(str).str.lower()
            mapa = {"jan":1,"fev":2,"mar":3,"abr":4,"mai":5,"jun":6,
                    "jul":7,"ago":8,"set":9,"out":10,"nov":11,"dez":12}
            m = s.str.extract(r"([a-z]{3})-(\d{2})")
            ok = m.notna().all(axis=1)
            df.loc[ok, "Mes_tmp"] = m.loc[ok, 0].map(mapa)
            df.loc[ok, "Ano_tmp"] = ("20" + m.loc[ok, 1]).astype(float)
            m2 = s.str.extract(r"(\d{1,2})[/-](\d{4})")
            ok2 = m2.notna().all(axis=1)
            df.loc[ok2, "Mes_tmp"] = pd.to_numeric(m2.loc[ok2, 0], errors="coerce")
            df.loc[ok2, "Ano_tmp"] = pd.to_numeric(m2.loc[ok2, 1], errors="coerce")
            miss = df["Data"].isna() & df["Mes_tmp"].notna() & df["Ano_tmp"].notna()
            if miss.any():
                df.loc[miss, "Data"] = pd.to_datetime(
                    dict(year=df.loc[miss, "Ano_tmp"].astype(int),
                         month=df.loc[miss, "Mes_tmp"].astype(int),
                         day=1),
                    errors="coerce"
                )

    # 5) Completa Ano / Mês a partir da Data --------------------------
    if "Data" in df.columns:
        df["Ano"] = df["Data"].dt.year
        df["Mês"] = df["Data"].dt.month

    # 6) Numéricos ----------------------------------------------------
    for c in ["Faturamento","Custos","Imposto","LucroLiquido"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # 7) Remove linhas sem Data válida --------------------------------
    if "Data" in df.columns:
        df = df.dropna(subset=["Data"])

    return otimizar_tipos(df.reset_index(drop=True))

# ╭─────────────────────  SANITIZE Pessoas  ──────────────────────────╮
def sanitize_pessoas_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Limpa a tabela *Pessoas* garantindo DataInicio/DataSaida e Salário."""
    df = rename_columns(df_raw, "pessoas").pipe(dedup).copy()

    # 1) garanta DataInicio/DataFinal
    for col in ("DataInicio", "DataFinal"):
        if col not in df.columns:
            df[col] = pd.NaT

    # 2) converte string → datetime
    for col in ("DataInicio", "DataFinal"):
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # fallback DataInicio
    if df["DataInicio"].isna().all() and {"AnoInicio", "MesInicio"}.issubset(df.columns):
        df["DataInicio"] = pd.to_datetime(
            dict(year=pd.to_numeric(df["AnoInicio"], errors="coerce"),
                 month=pd.to_numeric(df["MesInicio"], errors="coerce"),
                 day=1), errors="coerce"
        )

    # fallback DataFinal
    if df["DataFinal"].isna().all() and {"AnoFinal", "MesFinal"}.issubset(df.columns):
        df["DataFinal"] = pd.to_datetime(
            dict(year=pd.to_numeric(df["AnoFinal"], errors="coerce"),
                 month=pd.to_numeric(df["MesFinal"], errors="coerce"),
                 day=1), errors="coerce"
        )

    # completar Ano/Mês
    df["AnoInicio"] = df["DataInicio"].dt.year.astype("Int16", errors="ignore")
    df["MesInicio"] = df["DataInicio"].dt.month.astype("Int8", errors="ignore")
    df["AnoFinal"] = df["DataFinal"].dt.year.astype("Int16", errors="ignore")
    df["MesFinal"] = df["DataFinal"].dt.month.astype("Int8", errors="ignore")

    # Salário
    if "Salário Mensal" in df.columns:
        df["Salário Mensal"] = pd.to_numeric(df["Salário Mensal"],
                                             errors="coerce").fillna(0.0)
    else:
        df["Salário Mensal"] = 0.0

    # alias DataSaida
    if "DataSaida" not in df.columns:
        df["DataSaida"] = df.get("DataFinal", pd.NaT)

    return otimizar_tipos(df.reset_index(drop=True))

# ╭───────────────  SANITIZE Inadimplência  ─────────────────────────╮
def sanitize_inad_df(df_raw: pd.DataFrame, tabela: str) -> pd.DataFrame:
    """
    Limpa **boletocasas** ou **boletoartistas**:

    – boletoartistas: mantém apenas [ID_Boleto, NOME, Adiantamento, Valor Bruto, ID]
    """
    df = rename_columns(df_raw, tabela).pipe(dedup).copy()

    # boletoartistas — reduz colunas
    if tabela.lower() == "boletoartistas":
        cols_keep = ["ID_Boleto", "NOME", "Adiantamento", "Valor Bruto", "ID"]
        df = df[[c for c in cols_keep if c in df.columns]].copy()

    # Datas
    for col in ("Data Vencimento", "Data_Show", "DATA_PAGAMENTO"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Valores
    for col in ("Valor", "Valor Real", "Valor Bruto"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Status lower-case (boletocasas)
    if "Status" in df.columns:
        df["Status"] = df["Status"].astype(str).str.lower().str.strip()

    return otimizar_tipos(df.reset_index(drop=True))

# ╭───────────────  SANITIZE Metas  ─────────────────────────╮ 
def sanitize_metas_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    • Converte todas as colunas de PERCENT_COLS de 0–100 → 0–1
    """
    df = rename_columns(dedup(df_raw), "metas").copy()

    for col in PERCENT_COLS:
        if col in df.columns:
            # to_numeric resolve texto ('70%') ou '70,00'
            s = pd.to_numeric(
                    df[col]
                    .astype(str)
                    .str.replace('%', '', regex=False)
                    .str.replace(',', '.', regex=False),
                errors="coerce"
            )
            # frações já corridas (<1) ficam como estão; >1 divide por 100
            mask = s.notna() & (s >= 1)
            s.loc[mask] = s.loc[mask] / 100.0
            df[col] = s.astype("float32")

    return otimizar_tipos(df.reset_index(drop=True))

# ╭──────────────────────────  loaders  ──────────────────────────────╮
def carregar_base_eshows(force_reload: bool = False) -> pd.DataFrame:
    global _df_eshows_cache, _df_eshows_excluidos_cache

    if _df_eshows_cache is not None and not force_reload:
        return _df_eshows_cache

    df_raw = get_df_eshows()
    if df_raw.empty:
        raise ValueError("[BaseEshows] Supabase retornou vazio!")

    df_clean, df_excl = sanitize_eshows_df(df_raw)
    logger.info("[BaseEshows] Linhas finais: %s | Excluídas: %s",
                len(df_clean), len(df_excl))

    _df_eshows_cache = otimizar_tipos(df_clean)
    _df_eshows_excluidos_cache = df_excl
    return _df_eshows_cache


def carregar_eshows_excluidos() -> pd.DataFrame:
    global _df_eshows_excluidos_cache
    if _df_eshows_excluidos_cache is None:
        carregar_base_eshows()
    return _df_eshows_excluidos_cache.copy()


def carregar_base2(force_reload: bool = False) -> pd.DataFrame:
    """
    Baixa a Base-2 do Supabase, aplica o sanitizador e mantém cache em RAM.
    """
    global _df_base2_cache
    if _df_base2_cache is not None and not force_reload:
        return _df_base2_cache

    df_raw = dedup(get_df_base2())          # 37 × 53 atualmente
    df_clean = sanitize_base2_df(df_raw)
    _df_base2_cache = df_clean
    logger.info("[modulobase] Base2 carregada: %s", _df_base2_cache.shape)
    return _df_base2_cache


def carregar_pessoas() -> pd.DataFrame:
    global _df_pessoas_cache
    if _df_pessoas_cache is not None:
        return _df_pessoas_cache

    _df_pessoas_cache = sanitize_pessoas_df(dedup(get_df_pessoas()))
    logger.info("[modulobase] Pessoas carregada: %s", _df_pessoas_cache.shape)
    return _df_pessoas_cache


def carregar_ocorrencias() -> pd.DataFrame:
    global _df_ocorrencias_cache
    if _df_ocorrencias_cache is None:
        try:
            _df_ocorrencias_cache = dedup(get_df_ocorrencias())
        except Exception:
            _df_ocorrencias_cache = pd.DataFrame()
    return _df_ocorrencias_cache


def carregar_base_inadimplencia(
    force_reload: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    global _inad_casas_cache, _inad_artistas_cache
    if (not force_reload
            and _inad_casas_cache is not None
            and _inad_artistas_cache is not None):
        return _inad_casas_cache, _inad_artistas_cache

    df_casas_raw, df_art_raw = get_df_inadimplencia()
    _inad_casas_cache = sanitize_inad_df(df_casas_raw, "boletocasas")
    _inad_artistas_cache = sanitize_inad_df(df_art_raw, "boletoartistas")

    logger.info("[modulobase] Inad – casas %s | artistas %s",
                _inad_casas_cache.shape, _inad_artistas_cache.shape)
    return _inad_casas_cache, _inad_artistas_cache


def carregar_base_inad() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Alias legado."""
    return carregar_base_inadimplencia()


def carregar_metas(force_reload: bool = False) -> pd.DataFrame:
    global _df_metas_cache
    if _df_metas_cache is not None and not force_reload:
        return _df_metas_cache

    raw = get_df_metas()
    _df_metas_cache = sanitize_metas_df(raw)
    return _df_metas_cache


# ╭──────────────────────  loader Custos Abertos  ────────────────────╮
def carregar_custosabertos(force_reload: bool = False) -> pd.DataFrame:
    global _df_custosabertos_cache
    if _df_custosabertos_cache is not None and not force_reload:
        return _df_custosabertos_cache

    df_raw = get_df_custosabertos()
    if df_raw.empty:
        logger.warning("[custosabertos] Supabase retornou vazio.")
        _df_custosabertos_cache = pd.DataFrame()
        return _df_custosabertos_cache

    _df_custosabertos_cache = sanitize_custosabertos_df(df_raw)
    logger.info("[modulobase] CustosAbertos carregado: %s",
                _df_custosabertos_cache.shape)
    return _df_custosabertos_cache

# ───────────────────── loader NPS Artistas ────────────────────────
def carregar_npsartistas(force_reload: bool = False) -> pd.DataFrame:
    global _df_npsartistas_cache
    if _df_npsartistas_cache is not None and not force_reload:
        return _df_npsartistas_cache

    df_raw = get_df_npsartistas()
    if df_raw.empty:
        logger.warning("[npsartistas] Supabase retornou vazio.")
        _df_npsartistas_cache = pd.DataFrame()
        return _df_npsartistas_cache

    _df_npsartistas_cache = sanitize_npsartistas_df(df_raw)
    logger.info("[modulobase] NPSArtistas carregado: %s",
                _df_npsartistas_cache.shape)
    return _df_npsartistas_cache