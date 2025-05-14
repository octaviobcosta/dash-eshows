"""
churn_valor_debug.py
--------------------

Gera um Excel com a lista de casas que churnaram num intervalo
e calcula o run-rate mensal perdido (Churn $$).

• Aba única "ChurnValorYTD"
  Colunas:
    Id da Casa | Casa | churn_date | FatMensalMedio
    FirstShow  | LastShow | TempoAtivoDias
"""

from __future__ import annotations

import io
from datetime import timedelta, datetime

import pandas as pd
from dateutil.relativedelta import relativedelta

# ────────────────────────────────────────────────────────────
# Ajuste os imports abaixo ao seu projeto
# ────────────────────────────────────────────────────────────
from app.modulobase import carregar_base_eshows
from app.hist import COLUNAS_FATURAMENTO  # lista de colunas de faturamento (já usada no projeto)
# Se COLUNAS_FATURAMENTO estiver noutro módulo, ajuste o import.


# ===========================================================
# Funções internas
# ===========================================================
def _churn_ids_debug(
    df_eshows: pd.DataFrame,
    dias_sem_show: int,
    dt_ini: pd.Timestamp,
    dt_fim: pd.Timestamp,
    uf: str | None = None,
) -> pd.DataFrame:
    """
    Identifica casas churnadas entre dt_ini..dt_fim.
    Retorna DataFrame com Id da Casa, LastShow, churn_date.
    """
    if uf and uf != "BR":
        df_eshows = df_eshows[df_eshows["Estado"] == uf]

    last = (
        df_eshows.groupby("Id da Casa")["Data do Show"]
        .max()
        .reset_index(name="LastShow")
    )
    last["churn_date"] = last["LastShow"] + timedelta(days=dias_sem_show)

    # Candidatos cujo churn_date já passou do fim do período
    cand = last[last["churn_date"] <= dt_fim].copy()
    if cand.empty:
        return pd.DataFrame(columns=["Id da Casa", "LastShow", "churn_date"])

    # Verifica se a casa voltou a fazer shows depois do LastShow
    shows_cand = df_eshows[df_eshows["Id da Casa"].isin(cand["Id da Casa"])]
    merged = pd.merge(
        cand[["Id da Casa", "LastShow", "churn_date"]],
        shows_cand[["Id da Casa", "Data do Show"]],
        on="Id da Casa",
        how="left",
    )
    merged["Retornou"] = merged["Data do Show"] > merged["LastShow"]
    voltou = (
        merged.groupby("Id da Casa")["Retornou"]
        .any()
        .reset_index()
        .rename(columns={"Retornou": "Voltou"})
    )

    churn_df = pd.merge(cand, voltou, on="Id da Casa")
    churn_df = churn_df[~churn_df["Voltou"]]

    return churn_df[["Id da Casa", "LastShow", "churn_date"]]


# ===========================================================
# Função pública
# ===========================================================
def gerar_excel_churn_valor_debug(
    ano: int = 2025,
    custom_range: tuple[str, str] | None = None,
    dias_sem_show: int = 45,
    janela_media_meses: int = 3,
    uf: str | None = None,
) -> io.BytesIO | None:
    """
    Cria e devolve um objeto BytesIO contendo a planilha Excel.

    Parâmetros
    ----------
    ano : int
        Ano base para YTD caso custom_range seja None.
    custom_range : (str, str) ou None
        Datas no formato 'YYYY-MM-DD'. Se None, usa YTD do `ano`.
    dias_sem_show : int
        Janela sem shows para considerar churn (default = 45).
    janela_media_meses : int
        Quantos meses olhar para trás para calcular média de faturamento.
    uf : str ou None
        Filtra por estado (ex.: 'SP'); use None ou 'BR' para todo o Brasil.

    Retorno
    -------
    BytesIO ou None
        O arquivo Excel em memória; None se não houver dados.
    """
    # --------- carrega base ------------------------------------------------------------------
    df_eshows = carregar_base_eshows()
    if df_eshows is None or df_eshows.empty:
        print("[DEBUG] ➜ df_eshows vazio")
        return None

    # --------- intervalo ---------------------------------------------------------------------
    if custom_range:
        dt_ini, dt_fim = [pd.to_datetime(d).normalize() for d in custom_range]
    else:
        dt_ini = pd.Timestamp(ano, 1, 1)
        dt_fim = pd.Timestamp.today().normalize()

    # --------- casas churnadas ---------------------------------------------------------------
    churn_df = _churn_ids_debug(df_eshows, dias_sem_show, dt_ini, dt_fim, uf)
    if churn_df.empty:
        print("[DEBUG] ➜ Nenhum churn encontrado")
        return None

    ids_churn = churn_df["Id da Casa"].unique()
    df_rel = df_eshows[df_eshows["Id da Casa"].isin(ids_churn)].copy()

    # --------- prepara coluna Faturamento ----------------------------------------------------
    df_rel[COLUNAS_FATURAMENTO] = (
        df_rel[COLUNAS_FATURAMENTO]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )
    df_rel["Faturamento"] = df_rel[COLUNAS_FATURAMENTO].sum(axis=1)

    # FirstShow
    first = (
        df_rel.groupby("Id da Casa")["Data do Show"]
        .min()
        .reset_index(name="FirstShow")
    )
    df_rel = pd.merge(df_rel, first, on="Id da Casa", how="left")

    # --------- média de faturamento mensal ---------------------------------------------------
    def _run_rate(sub: pd.DataFrame) -> float:
        last_show = sub["Data do Show"].max()
        ini_win = last_show - relativedelta(months=janela_media_meses)
        rec = sub[sub["Data do Show"] >= ini_win]
        total = rec["Faturamento"].sum()
        months = max(
            (last_show.year - ini_win.year) * 12 + (last_show.month - ini_win.month) + 1,
            1,
        )
        return total / months if total else 0.0

    run_rate = (
        df_rel.groupby("Id da Casa")
        .apply(_run_rate)
        .rename("FatMensalMedio")
        .reset_index()
    )

    # --------- monta tabela final ------------------------------------------------------------
    tabela = (
        churn_df
        .merge(run_rate, on="Id da Casa", how="left")
        .merge(first,    on="Id da Casa", how="left")
        .merge(df_rel[["Id da Casa", "Casa"]].drop_duplicates(), on="Id da Casa", how="left")
    )
    tabela["TempoAtivoDias"] = (tabela["LastShow"] - tabela["FirstShow"]).dt.days.clip(0)

    tabela = tabela[
        [
            "Id da Casa",
            "Casa",
            "churn_date",
            "FatMensalMedio",
            "FirstShow",
            "LastShow",
            "TempoAtivoDias",
        ]
    ].sort_values("churn_date")

    # --------- exporta para Excel ------------------------------------------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        tabela.to_excel(writer, sheet_name="ChurnValorYTD", index=False)

    output.seek(0)
    return output


# ===========================================================
# Execução direta (teste rápido)
# ===========================================================
if __name__ == "__main__":
    from datetime import datetime

    tabela_df = None  # <- guardaremos o DataFrame

    # Gera o Excel em memória e captura também o DataFrame
    buffer = gerar_excel_churn_valor_debug(
        ano=2025,
        custom_range=("2025-01-01", datetime.today().strftime("%Y-%m-%d")),
    )

    if buffer:
        # --- salvar arquivo (opcional) ---
        with open("ChurnValorYTD.xlsx", "wb") as f:
            f.write(buffer.getvalue())
        print("✓ Arquivo ChurnValorYTD.xlsx gerado com sucesso!\n")

        # --- carregar da memória para DataFrame e printar ---
        import pandas as pd
        buffer.seek(0)
        tabela_df = pd.read_excel(buffer, sheet_name="ChurnValorYTD")

        # imprime tudo no terminal
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        print(tabela_df.to_string(index=False))
    else:
        print("Nenhum churn $$ encontrado para o intervalo informado.")
