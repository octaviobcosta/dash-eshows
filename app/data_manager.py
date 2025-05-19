from __future__ import annotations

import datetime as _dt
import logging
import os
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from postgrest import APIError

from .column_mapping import rename_columns, divide_cents, CENTS_MAPPING

# ────────────────────────────  logging  ────────────────────────────
logger = logging.getLogger(__name__)

# ───────────────────────  cache em Parquet  ────────────────────────
CACHE_DIR = Path(__file__).resolve().parent / "_cache_parquet"
CACHE_DIR.mkdir(exist_ok=True)

CACHE_EXPIRY_HOURS: int | None = 12

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
supa = None  # lazily-instantiated singleton

def _init_supabase():
    global supa
    if supa is not None:
        return supa

    if (env := find_dotenv()):
        load_dotenv(env)

    url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", "")
    if not (url and key):
        logger.error("SUPABASE_URL/KEY não encontrados.")
        return None

    try:
        from supabase import create_client
        supa = create_client(url, key)
        logger.info("Cliente Supabase inicializado.")
    except Exception as e:
        logger.error("Falha ao criar cliente Supabase: %s", e)

    return supa

supa = _init_supabase()

# ─────────────────────────  helpers comuns  ────────────────────────
_cache: Dict[str, pd.DataFrame] = {}

def dedup(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df

# ────────────────────────  download + limpeza  ─────────────────────
def _fetch(table: str) -> pd.DataFrame:
    if supa is None:
        return pd.DataFrame()

    STEP, page, pages = 1000, 0, []
    while True:
        start, end = page * STEP, (page + 1) * STEP - 1
        try:
            q = supa.table(table).select("*")
            if table.lower() == "baseeshows":
                q = q.gte("Data", "2022-01-01")
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
    df = divide_cents(dedup(rename_columns(df, table)), table)

    for col in CENTS_MAPPING.get(table.lower(), []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    logger.info("[%s] baixado: %s linhas × %s col", table, *df.shape)
    return df

# ───────────────────────  cache RAM + Parquet  ─────────────────────
def _get(table: str, *, force_reload: bool = False) -> pd.DataFrame:
    table = table.lower()
    logger.info("carregando %s…", table)

    if not force_reload and table in _cache:
        return _cache[table]

    if not force_reload:
        if (df_disk := _load_parquet(table)) is not None:
            _cache[table] = df_disk
            logger.info("[%s] carregado do Parquet (%s linhas)", table, len(df_disk))
            return df_disk

    df_live = _fetch(table)
    _cache[table] = df_live
    _save_parquet(table, df_live)
    return df_live

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
