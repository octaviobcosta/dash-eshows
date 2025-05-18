from __future__ import annotations

import datetime as _dt
import logging
import os
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from postgrest import APIError

from .column_mapping import (
    rename_columns,
    COLS_BASESHOWS,
    COLS_BASE2,
    COLS_BOLETOCASAS,
    COLS_BOLETOARTISTAS,
    COLS_PESSOAS,
    COLS_CUSTOSABERTOS,
    COLS_NPSARTISTAS,
    CENTAVOS_BASESHOWS,
    CENTAVOS_BASE2,
    CENTAVOS_BOLETOCASAS,
    CENTAVOS_BOLETOARTISTAS,
    CENTAVOS_CUSTOSABERTOS,
    MAPPING,
)

# ────────────────────────────  logging  ────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s – %(name)s – %(levelname)s – %(message)s",
)
logger = logging.getLogger("data_manager")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("supabase_py").setLevel(logging.WARNING)

# ───────────────────────  cache em Parquet  ────────────────────────
CACHE_DIR = Path(__file__).resolve().parent / "_cache_parquet"
CACHE_DIR.mkdir(exist_ok=True)

CACHE_EXPIRY_HOURS: int | None = 12

# -----------------------------------------------------------------------------
# helper compatível com modulobase
def _parquet_path(table: str) -> Path:
    """Retorna app/_cache_parquet/{table}.parquet (wrapper para _cache_path)."""
    return _cache_path(table)

def _cache_path(table: str) -> Path:
    return CACHE_DIR / f"{table.lower()}.parquet"

def _is_cache_fresh(p: Path) -> bool:
    if CACHE_EXPIRY_HOURS is None or not p.exists():
        return p.exists()
    age = (_dt.datetime.now() -
           _dt.datetime.fromtimestamp(p.stat().st_mtime)).total_seconds()
    return age < CACHE_EXPIRY_HOURS * 3600

def _load_parquet(table: str) -> pd.DataFrame | None:
    p = _cache_path(table)
    if _is_cache_fresh(p):
        try:
            return pd.read_parquet(p)
        except Exception:
            pass
    return None

def _save_parquet(table: str, df: pd.DataFrame) -> None:
    try:
        df.to_parquet(_cache_path(table),
                      index=False,
                      compression="zstd",
                      use_dictionary=True)
    except Exception:
        pass

# ────────────────────────  Supabase client  ────────────────────────
supa = None  # singleton

def _init_supabase():
    """Cria o cliente se houver URL+KEY; caso contrário, sinaliza MODO OFFLINE."""
    global supa
    if supa is not None:
        return supa

    if (env := find_dotenv()):
        load_dotenv(env)

    url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", "")
    if not (url and key):
        logger.warning("Rodando em MODO OFFLINE – cache Parquet será usado.")
        supa = None
        return None

    try:
        from supabase import create_client
        supa = create_client(url, key)
        logger.info("Cliente Supabase inicializado.")
    except Exception as e:
        logger.error("Falha ao criar cliente Supabase: %s – entrando em MODO OFFLINE", e)
        supa = None

    return supa

supa = _init_supabase()

# ─────────────────────────  helpers comuns  ────────────────────────
_cache: Dict[str, pd.DataFrame] = {}

def dedup(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df

# ────────────────────────  download + limpeza  ─────────────────────
# -----------------------------------------------------------------------------
def _fetch(table: str, mode: str = "online") -> pd.DataFrame:
    """Carrega a tabela do Supabase (``mode='online'``) ou do Parquet
    local (``mode='offline'``) utilizando apenas as colunas mapeadas."""

    table = table.lower()

    cols_map = {
        "baseeshows": COLS_BASESHOWS,
        "base2": COLS_BASE2,
        "boletocasas": COLS_BOLETOCASAS,
        "boletoartistas": COLS_BOLETOARTISTAS,
        "pessoas": COLS_PESSOAS,
        "custosabertos": COLS_CUSTOSABERTOS,
        "npsartistas": COLS_NPSARTISTAS,
    }

    cents_map = {
        "baseeshows": CENTAVOS_BASESHOWS,
        "base2": CENTAVOS_BASE2,
        "boletocasas": CENTAVOS_BOLETOCASAS,
        "boletoartistas": CENTAVOS_BOLETOARTISTAS,
        "custosabertos": CENTAVOS_CUSTOSABERTOS,
    }

    cols = cols_map.get(table)
    if not cols:
        cols = None

    offline_cols = [MAPPING.get(table, {}).get(c, c) for c in cols] if cols else None

    if mode == "offline":
        try:
            df = pd.read_parquet(_cache_path(table), columns=offline_cols)
        except Exception:
            try:
                df = pd.read_parquet(_cache_path(table))
            except Exception as exc:
                logger.error("[%s] erro lendo Parquet: %s", table, exc)
                return pd.DataFrame()
        df = rename_columns(dedup(df), table)
        for col in [c for c in cents_map.get(table, []) if c in df.columns]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) / 100.0
        return df

    if supa is None:
        return pd.DataFrame()

    STEP, page, pages = 1000, 0, []
    while True:
        start, end = page * STEP, (page + 1) * STEP - 1
        try:
            sel = ",".join(cols) if cols else "*"
            q = supa.table(table).select(sel)
            if table.lower() == "baseeshows":
                q = q.gte("Data", "2022-01-01")  # corte opcional
            resp = q.range(start, end).execute()
        except APIError as err:
            logger.error("[%s] página %s: %s", table, page + 1, err.message)
            break

        data = resp.data or []
        if not data:
            break
        pages.append(pd.DataFrame(data))
        if len(data) < STEP:
            break
        page += 1

    if not pages:
        return pd.DataFrame()

    df = pd.concat(pages, ignore_index=True)
    df = rename_columns(dedup(df), table)
    for col in [c for c in cents_map.get(table, []) if c in df.columns]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) / 100.0

    logger.info("[%s] baixado: %s linhas × %s col", table, *df.shape)
    return df

# ───────────────────────  cache RAM + Parquet  ─────────────────────
def _get(table: str, *, force_reload: bool = False) -> pd.DataFrame:
    table = table.lower()
    logger.info("carregando %s…", table)

    if not force_reload and table in _cache:
        return _cache[table]

    mode = "online" if supa is not None else "offline"

    df = _fetch(table, mode=mode)
    _cache[table] = df
    if mode == "online":
        _save_parquet(table, df)
    return df

# ────────────────────  interfaces públicas  ────────────────────────
def get_df_eshows()        -> pd.DataFrame:                      return _get("baseeshows")
def get_df_base2()         -> pd.DataFrame:                      return _get("base2")
def get_df_ocorrencias()   -> pd.DataFrame:                      return _get("ocorrencias")
def get_df_pessoas()       -> pd.DataFrame:                      return _get("pessoas")
def get_df_metas()         -> pd.DataFrame:                      return _get("metas")
def get_df_inadimplencia() -> Tuple[pd.DataFrame, pd.DataFrame]: return _get("boletocasas"), _get("boletoartistas")
def get_df_custosabertos() -> pd.DataFrame:                      return _get("custosabertos")
def get_df_npsartistas()   -> pd.DataFrame:                      return _get("npsartistas")   # ← NOVO


def reset_all_data(clear_disk: bool = False):
    _cache.clear()
    if clear_disk:
        for p in CACHE_DIR.glob("*.parquet"):
            try:
                p.unlink()
            except Exception:
                pass
    logger.info("[data_manager] caches limpos – próxima chamada recarrega do Supabase.")
