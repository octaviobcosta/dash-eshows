"""
app.test_cac — Validação rápida do KPI CAC
Como rodar:
    (.venv) PS> python -m app.test_cac
"""

# --------------------------------------------------------------------------- #
# Imports                                                                     #
# --------------------------------------------------------------------------- #
import pandas as pd
from .utils import formatar_valor_utils
from .variacoes import get_cac_variables
from .modulobase import (
    carregar_custosabertos,
    carregar_base_eshows,
    carregar_pessoas,
)

# --------------------------------------------------------------------------- #
# Parâmetros                                                                  #
# --------------------------------------------------------------------------- #
ano_teste = 2025
periodo_teste = "YTD"
mes_teste = None
custom_range_teste = None

# --------------------------------------------------------------------------- #
# Função-resumo                                                               #
# --------------------------------------------------------------------------- #
def resumir_cac(resultado: dict) -> None:
    """Resumo detalhado do CAC, exibindo custos por fornecedor e alimentação mensal."""
    vars_ = resultado["variables_values"]
    dbg   = vars_["Debug Info"]

    # ─ Helper para agrupar custos por fornecedor ─────────────────────────── #
    def _totais_por_fornecedor(lista_dict):
        if not lista_dict:
            return []
        df_tmp = pd.DataFrame(lista_dict)
        if {"Fornecedor", "Valor"}.issubset(df_tmp.columns):
            tot = (
                df_tmp.groupby("Fornecedor")["Valor"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            return [
                (row["Fornecedor"], formatar_valor_utils(row["Valor"], "monetario"))
                for _, row in tot.iterrows()
            ]
        return []

    # ─ Totais de custo ───────────────────────────────────────────────────── #
    custo_setor   = dbg.get("Custo_Fornecedores_Comercial_Soma", 0)
    custo_visitas = dbg.get("Custo_Visitas_Clientes_Soma", 0)
    custo_alim    = dbg.get("Custo_Alimentacao_Proporcional_Comercial_Soma", 0)
    cac_raw       = vars_.get("CAC Calculado Raw", 0)

    lista_setor   = _totais_por_fornecedor(dbg.get("custos_fornec_comercial_full_df", []))
    lista_visitas = _totais_por_fornecedor(dbg.get("custos_visitas_full_df", []))

    # Detalhes de alimentação
    alim_df_full  = dbg.get("custo_alimentacao_full_df", [])
    alim_mensal   = dbg.get("Alimentacao_Mensal_Detalhe", [])

    # ─ Quadro principal ──────────────────────────────────────────────────── #
    linhas = [
        f"Período analisado : {resultado['periodo']}",
        f"Status de cálculo : {resultado['status']}",
        "",
        "Setor Comercial",
    ]
    linhas += [f"  • {n}: {v}" for n, v in lista_setor]
    linhas.append(f"  Total Setor Comercial: {formatar_valor_utils(custo_setor, 'monetario')}\n")

    linhas.append("Visita a Clientes")
    linhas += [f"  • {n}: {v}" for n, v in lista_visitas]
    linhas.append(f"  Total Visitas a Clientes: {formatar_valor_utils(custo_visitas, 'monetario')}\n")

    total_func  = dbg.get("Num_Total_Funcionarios_Ativos_Media", "N/A")
    alim_total  = dbg.get("Custo_Alimentacao_TempusFlash_Soma", 0)
    alim_pp     = dbg.get("Custo_Alimentacao_Por_Pessoa_Total_Calculado", 0)
    func_comerc = dbg.get("Num_Funcionarios_Comercial_Contagem", "N/A")

    linhas.extend([
        "Alimentação",
        f"  Total Alimentação            : {formatar_valor_utils(alim_total, 'monetario')}",
        f"  Total de Funcionários        : {total_func}",
        f"  Alimentação p/ pessoa        : {formatar_valor_utils(alim_pp, 'monetario')}",
        f"  Total Funcionários Comercial : {func_comerc}",
        f"  Alimentação Comercial        : {formatar_valor_utils(custo_alim, 'monetario')}\n",
        "CAC Total = Setor Comercial + Visita a Clientes + Alimentação",
        f"💰 CAC Total                    : {formatar_valor_utils(cac_raw, 'monetario')}",
    ])

    print("\n".join(linhas))

    # ─ Detalhe Alimentação (mês × fornecedor) ────────────────────────────── #
    if alim_df_full:
        print("\nDetalhe Alimentação (mês × fornecedor):")
        df_alim = pd.DataFrame(alim_df_full).rename(columns=str.strip)

        # Corrige variações de nome
        if "Forneceedor" in df_alim.columns and "Fornecedor" not in df_alim.columns:
            df_alim.rename(columns={"Forneceedor": "Fornecedor"}, inplace=True)

        # Tenta descobrir coluna de data
        date_col = next(
            (c for c in ["Data Competencia", "Data", "Data Vencimento"] if c in df_alim.columns),
            None,
        )
        if date_col and "Fornecedor" in df_alim.columns:
            df_alim[date_col] = pd.to_datetime(df_alim[date_col], errors="coerce")
            df_alim["Mês"] = df_alim[date_col].dt.strftime("%Y-%m")

            resumo = (
                df_alim.groupby(["Mês", "Fornecedor"])["Valor"]
                .sum()
                .reset_index()
                .sort_values(["Mês", "Fornecedor"])
            )
            for _, row in resumo.iterrows():
                print(f"  {row['Mês']} • {row['Fornecedor']}: {formatar_valor_utils(row['Valor'], 'monetario')}")
        else:
            print("  ⚠️  Não foi possível identificar colunas 'Fornecedor' e data.")

    # ─ Tabela mensal resumida (Total, HC, etc.) ──────────────────────────── #
    if alim_mensal:
        print("\nAlimentação — detalhamento mensal:")
        for m in alim_mensal:
            print(
                f"  {m['Mes']:>7} | "
                f"Tot.: {formatar_valor_utils(m['Alimentacao_Total'], 'monetario'):>8} | "
                f"HC: {m['Headcount_Total']:>3} | "
                f"Alim/pessoa: {formatar_valor_utils(m['Alim_por_Pessoa'], 'monetario'):>7} | "
                f"HC Com.: {m['Headcount_Comercial']:>2} | "
                f"Alim Com.: {formatar_valor_utils(m['Alimentacao_Comercial'], 'monetario')}"
            )
# --------------------------------------------------------------------------- #
# Execução direta                                                             #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    resultado = get_cac_variables(
        ano=ano_teste,
        periodo=periodo_teste,
        mes=mes_teste,
        custom_range=custom_range_teste,
    )
    resumir_cac(resultado)
