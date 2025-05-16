"""Lazy-loading wrappers for dataset functions.

Each getter calls the corresponding ``carregar_*`` function only on the first
invocation and reuses the cached DataFrame thereafter.
"""

from __future__ import annotations

import pandas as pd
from functools import lru_cache

from .modulobase import (
    carregar_base_eshows,
    carregar_base2,
    carregar_ocorrencias,
    carregar_base_inad,
    carregar_pessoas,
    carregar_npsartistas,
)


@lru_cache(maxsize=None)
def get_eshows() -> pd.DataFrame:
    return carregar_base_eshows()


@lru_cache(maxsize=None)
def get_base2() -> pd.DataFrame:
    return carregar_base2()


@lru_cache(maxsize=None)
def get_ocorrencias() -> pd.DataFrame:
    return carregar_ocorrencias()


@lru_cache(maxsize=None)
def get_inad() -> tuple[pd.DataFrame, pd.DataFrame]:
    return carregar_base_inad()


@lru_cache(maxsize=None)
def get_pessoas() -> pd.DataFrame:
    return carregar_pessoas()


@lru_cache(maxsize=None)
def get_npsartistas() -> pd.DataFrame:
    return carregar_npsartistas()
