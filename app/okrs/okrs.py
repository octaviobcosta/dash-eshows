#orks.py
import pandas as pd
import json
import os
import tiktoken
import numbers
from datetime import datetime, timedelta
import calendar

import dash
import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, Input, Output, State, callback, MATCH
import uuid
import math
import sys
sys.stdout.reconfigure(encoding='utf-8')

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# IMPORTAÇÃO DE FUNÇÕES (modulobase) E FORMATAÇÃO (utils)
# =============================================================================
from ..modulobase import (
    carregar_base_eshows,
    carregar_eshows_excluidos,
    carregar_base2,
    carregar_ocorrencias,
    carregar_base_inad,
    carregar_metas,
    carregar_pessoas
)
from ..utils import (
    filtrar_periodo_principal,
    filtrar_periodo_comparacao,
    get_period_start,
    get_period_end,
    get_period_range,
    mes_nome,
    mes_nome_intervalo,
    carregar_kpi_descriptions,
    obter_top5_grupos_ano_anterior,
    faturamento_dos_grupos,
    novos_palcos_dos_grupos,
    formatar_valor_utils,
    calcular_churn,
    calcular_periodo_anterior,
    parse_valor_formatado,
    
)
from ..controles import zonas_de_controle, get_kpi_status
from ..variacoes import (
    get_nrr_variables,
    get_churn_variables,
    get_turnover_variables,
    get_lucratividade_variables,
    get_crescimento_sustentavel_variables,
    get_palcos_vazios_variables,  # Nova importação
    get_inadimplencia_real_variables,
    get_autonomia_usuario_variables,
    get_estabilidade_variables,
    get_eficiencia_atendimento_variables,
    get_rpc_variables,
    get_perdas_operacionais_variables,
    get_nps_artistas_variables,
    get_nps_equipe_variables,
    get_ltv_cac_variables  
)

# =============================================================================
# Variáveis globais
# =============================================================================
df_eshows = carregar_base_eshows()
df_base2 = carregar_base2()
df_ocorrencias = carregar_ocorrencias()


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
def filtrar_novos_palcos(df_completo, ano, periodo, mes, custom_range=None):
    """
    Filtra os palcos (casas) que são considerados novos no período especificado.
    
    Args:
        df_completo (DataFrame): DataFrame com todos os dados de shows
        ano (int): Ano de referência
        periodo (str): Período selecionado
        mes (int, optional): Mês específico para 'Mês Aberto'
        custom_range (tuple, optional): (data_inicial, data_final) para período personalizado
        
    Returns:
        set: Conjunto de IDs de casas consideradas novas
    """
    if df_completo is None or df_completo.empty:
        return set()
        
    # Se custom_range foi fornecido, usamos a data inicial dele
    if custom_range is not None and periodo == "custom-range":
        start_date = custom_range[0]
        print(f"Filtrando novos palcos a partir de {start_date.strftime('%d/%m/%Y')}")
    else:
        # Caso contrário, usamos get_period_start como antes
        start_date = get_period_start(ano, periodo, mes, custom_range)
    
    df_min = df_completo.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")
    df_min["EarliestShow"] = pd.to_datetime(df_min["EarliestShow"], errors="coerce")
    df_new = df_min[df_min["EarliestShow"] >= start_date]
    
    return set(df_new["Id da Casa"].unique())

def filtrar_key_accounts(df_completo, ano):
    """
    Filtra as casas consideradas Key Accounts com base no top 5 grupos do ano anterior.
    
    Args:
        df_completo (DataFrame): DataFrame com todos os dados de shows
        ano (int): Ano de referência
        
    Returns:
        set: Conjunto de IDs de casas consideradas Key Accounts
    """
    if df_completo is None or df_completo.empty or "Grupo" not in df_completo.columns:
        return set()
    top5_list = obter_top5_grupos_ano_anterior(df_completo, ano)
    if not top5_list:
        return set()
    grupos_top5 = [tpl[0] for tpl in top5_list]
    df_kas = df_completo[df_completo["Grupo"].isin(grupos_top5)].copy()
    if df_kas.empty:
        return set()
    return set(df_kas["Id da Casa"].unique())

def define_progress_color(perc):
    """
    Mantém a lógica de 'danger', 'warning' e 'success' para colorir a barra do card.
    
    Args:
        perc (float): Percentual de progresso (0-100)
        
    Returns:
        str: String com o nome da cor ("danger", "warning" ou "success")
    """
    if perc <= 0:
        return "danger"
    elif perc < 40:
        return "danger"
    elif perc < 70:
        return "warning"
    else:
        return "success"

def criar_custom_range(ano, mes_inicial, mes_final):
    """
    Cria um custom_range (start_date, end_date) baseado no ano e nos meses selecionados.
    
    Args:
        ano (int): Ano de referência
        mes_inicial (int): Mês inicial (1-12)
        mes_final (int): Mês final (1-12)
        
    Returns:
        tuple: (start_date, end_date) como objetos datetime
    """
    if not mes_inicial or not mes_final:
        return None
    
    start_date = datetime(ano, mes_inicial, 1)
    end_date = datetime(ano, mes_final, calendar.monthrange(ano, mes_final)[1])
    
    return (start_date, end_date)

# =============================================================================
# CALCULAR PROGRESSO PARA METAS "MAIOR" X "MENOR"
# =============================================================================
def calcular_progresso(valor_atual, meta, tipo_meta="maior"):
    """
    Se tipo_meta='maior':
       - 100% se valor_atual >= meta
       - caso contrário (valor_atual < meta): (valor_atual / meta)*100
    Se tipo_meta='menor':
       - 100% se valor_atual <= meta
       - se valor_atual > meta, definimos um 'start' = valor_atual (pior caso).
    """
    if tipo_meta == "menor":
        if valor_atual <= meta:
            return 100.0
        else:
            start = valor_atual
            if start == meta:
                return 0.0
            progress = 1 - ((valor_atual - meta) / (start - meta))
            if progress < 0:
                progress = 0
            return progress * 100
    else:
        # tipo_meta='maior'
        if valor_atual >= meta:
            return 100.0
        else:
            if meta == 0:
                return 0.0
            return (valor_atual / meta) * 100
        
# =============================================================================
# CALCULAR PROGRESSO GERAL
# =============================================================================
def calcular_progresso_geral(periodo, mes_selecionado, mes_inicial=None, mes_final=None):
    """
    Calcula o progresso geral baseado nos 3 objetivos principais (obj 1, 3 e 4).
    Cada objetivo contribui com 33,33% para o total.
    
    Args:
        periodo (str): Período selecionado (trimestre, mês aberto, etc)
        mes_selecionado (int): Mês selecionado (relevante para "Mês Aberto")
        mes_inicial (int, optional): Mês inicial para período personalizado
        mes_final (int, optional): Mês final para período personalizado
        
    Returns:
        float: Valor percentual do progresso geral (0-100)
    """
    print("\n" + "="*80)
    print(f"INICIANDO CÁLCULO DO PROGRESSO GERAL - PARÂMETROS RECEBIDOS:")
    print(f"  Período: {periodo}")
    print(f"  Mês selecionado: {mes_selecionado}")
    print(f"  Mês inicial: {mes_inicial}")
    print(f"  Mês final: {mes_final}")
    print("-"*80)
    
    # *** CORREÇÃO FUNDAMENTAL: Para resolver o problema de inconsistência nas metas ***
    # *** Vamos armazenar o período original E todas as variáveis necessárias para recuperá-lo ***
    original_periodo = periodo  # Guarda o período original para log
    original_mes_inicial = mes_inicial  # Guardar também o mês inicial original
    original_mes_final = mes_final  # Guardar também o mês final original
    ano = 2025
    custom_range = None
    
    # Flag para controlar se usamos as metas do período convertido
    usar_metas_periodo_convertido = False
    periodo_convertido = None
    
    if periodo == "custom-range" and mes_inicial and mes_final:
        print(f"Período personalizado: De {mes_nome(mes_inicial)} até {mes_nome(mes_final)} de {ano}")
        
        # Criar o custom_range apenas para manter compatibilidade inicial
        custom_range = criar_custom_range(ano, mes_inicial, mes_final)
        if custom_range:
            print(f"custom_range inicial: {custom_range[0].strftime('%Y-%m-%d %H:%M:%S')} até {custom_range[1].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Verificar se o período personalizado é equivalente a algum período predefinido
        if mes_inicial == 1 and mes_final == 3:
            print(f"⚠️ CORREÇÃO APLICADA: Período personalizado (Jan-Mar) equivale a 1° Trimestre")
            # IMPORTANTE: Não convertemos ainda, apenas marcamos
            periodo_convertido = "1° Trimestre"
            usar_metas_periodo_convertido = True
            
        elif mes_inicial == 4 and mes_final == 6:
            print(f"⚠️ CORREÇÃO APLICADA: Período personalizado (Abr-Jun) equivale a 2° Trimestre")
            periodo_convertido = "2° Trimestre"
            usar_metas_periodo_convertido = True
            
        elif mes_inicial == 7 and mes_final == 9:
            print(f"⚠️ CORREÇÃO APLICADA: Período personalizado (Jul-Set) equivale a 3° Trimestre")
            periodo_convertido = "3° Trimestre"
            usar_metas_periodo_convertido = True
            
        elif mes_inicial == 10 and mes_final == 12:
            print(f"⚠️ CORREÇÃO APLICADA: Período personalizado (Out-Dez) equivale a 4° Trimestre")
            periodo_convertido = "4° Trimestre"
            usar_metas_periodo_convertido = True
            
        elif mes_inicial == 1 and mes_final == 12:
            print(f"⚠️ CORREÇÃO APLICADA: Período personalizado (Jan-Dez) equivale a Ano Completo")
            periodo_convertido = "Ano Completo"
            usar_metas_periodo_convertido = True
    
    # Carregamento dos dados necessários para os cálculos
    print(f"Carregando dados para cálculos...")
    df_eshows_completo = df_eshows  # Já carregado globalmente
    df_eshows_global = df_eshows    # Referência para manter compatibilidade com o resto da função
    df_pessoas = carregar_pessoas()
    df_base2_global = df_base2      # Para o cálculo da Lucratividade e Crescimento Sustentável
    df_ocorrencias_global = df_ocorrencias  # Para o cálculo dos Palcos Vazios
    df_inad_casas, df_inad_artistas = carregar_base_inad()  # Para o cálculo da Inadimplência Real
    
    # Gerar df_casas_earliest e df_casas_latest para LTV/CAC
    df_casas_earliest = df_eshows.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow") if df_eshows is not None and not df_eshows.empty else None
    df_casas_latest = df_eshows.groupby("Id da Casa")["Data do Show"].max().reset_index(name="LastShow") if df_eshows is not None and not df_eshows.empty else None
    
    # Obtenção de todas as metas utilizando a função ler_todas_as_metas
    mes = None
    if periodo == "Mês Aberto":
        mes = mes_selecionado
    
    # Carregamos primeiro as metas do período original (para custom-range)
    metas = ler_todas_as_metas(ano, periodo, mes, custom_range)
    print(f"Metas obtidas para período original: {metas}")
    
    # Se há um período convertido, carregamos também as metas desse período
    metas_periodo_convertido = None
    if usar_metas_periodo_convertido and periodo_convertido:
        print(f"⚠️ CORREÇÃO AVANÇADA: Carregando também metas para período equivalente '{periodo_convertido}'")
        metas_periodo_convertido = ler_todas_as_metas(ano, periodo_convertido, None, None)
        print(f"Metas obtidas para período equivalente: {metas_periodo_convertido}")
        
        # CRÍTICO: Usar as metas do período convertido em vez das originais
        metas = metas_periodo_convertido
        print(f"⚠️ CORREÇÃO FINAL: Usando metas do período '{periodo_convertido}' em vez de 'custom-range', MAS MANTENDO TIPO DE PERÍODO ORIGINAL")
        
        # *** CORREÇÃO CRUCIAL: NÃO converter o período nem anular custom_range ***
        # Isso foi a causa da inconsistência nos cálculos de progresso
        # periodo = periodo_convertido
        # custom_range = None
    
    # ----- OBJETIVO 1: Retomar o Crescimento -----
    print("\n" + "-"*80)
    print("CALCULANDO OBJETIVO 1: Retomar o Crescimento")
    print("-"*80)
    
    # Obtém as metas do dicionário
    meta_novos = metas["NovosClientes"]
    meta_key = metas["KeyAccount"]
    meta_outros = metas["OutrosClientes"]
    meta_plat = metas["Plataforma"]
    meta_fint = metas["Fintech"]

    meta_curadoria = meta_novos + meta_key + meta_outros
    meta_obj_principal = meta_curadoria + meta_plat + meta_fint

    ano_real = 2025
    mes_real = None
    if periodo == "Mês Aberto":
        mes_real = mes_selecionado

    print(f"Filtrando dados para período: ano={ano_real}, período={periodo}, mês={mes_real}, custom_range={custom_range}")
    df_periodo_eshows = filtrar_periodo_principal(df_eshows_completo, ano_real, periodo, mes_real, custom_range)
    print(f"Registros filtrados: {len(df_periodo_eshows) if df_periodo_eshows is not None and not df_periodo_eshows.empty else 0}")

    if df_periodo_eshows is None or df_periodo_eshows.empty:
        print("⚠️ Nenhum dado encontrado para o período. Utilizando valores zerados.")
        real_novos = real_key = real_outros = real_plat = real_fint = 0.0
    else:
        COLUNAS_CURADORIA = ["Comissão B2B", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"]
        FINTECH_COLUNA    = "Antecipação de Cachês"

        # Converter colunas para numérico
        for c in COLUNAS_CURADORIA:
            if c in df_periodo_eshows.columns:
                df_periodo_eshows[c] = pd.to_numeric(df_periodo_eshows[c], errors='coerce').fillna(0)
        if FINTECH_COLUNA in df_periodo_eshows.columns:
            df_periodo_eshows[FINTECH_COLUNA] = pd.to_numeric(df_periodo_eshows[FINTECH_COLUNA], errors='coerce').fillna(0)

        # Identificação de novos palcos
        print("Identificando novos palcos...")
        if periodo == "custom-range" and custom_range:
            start_date = custom_range[0]
            df_min = df_eshows_completo.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")
            df_min["EarliestShow"] = pd.to_datetime(df_min["EarliestShow"], errors='coerce')
            novos_ids = set(df_min.loc[df_min["EarliestShow"] >= start_date, "Id da Casa"])
            print(f"Identificados {len(novos_ids)} novos palcos a partir de {start_date.strftime('%d/%m/%Y')}")
        elif periodo == "Mês Aberto":
            janeiro_1 = datetime(ano_real, 1, 1)
            df_min = df_eshows_completo.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")
            df_min["EarliestShow"] = pd.to_datetime(df_min["EarliestShow"], errors='coerce')
            novos_ids = set(df_min.loc[df_min["EarliestShow"] >= janeiro_1, "Id da Casa"])
            print(f"Identificados {len(novos_ids)} novos palcos a partir de {janeiro_1.strftime('%d/%m/%Y')}")
        else:
            novos_ids = filtrar_novos_palcos(df_eshows_completo, ano_real, periodo, mes_real, custom_range)
            print(f"Identificados {len(novos_ids)} novos palcos para {periodo}")

        # Identificação de Key Accounts
        print("Identificando Key Accounts...")
        kas_ids = filtrar_key_accounts(df_eshows_completo, ano_real)
        print(f"Identificados {len(kas_ids)} Key Accounts")
        
        # Cálculos de valores reais
        real_fint = df_periodo_eshows[FINTECH_COLUNA].sum() if FINTECH_COLUNA in df_periodo_eshows.columns else 0.0
        real_plat = 0.0

        df_novos = df_periodo_eshows[df_periodo_eshows["Id da Casa"].isin(novos_ids)]
        real_novos = df_novos[COLUNAS_CURADORIA].sum().sum() if not df_novos.empty else 0.0

        df_kas = df_periodo_eshows[df_periodo_eshows["Id da Casa"].isin(kas_ids)]
        df_kas = df_kas[~df_kas["Id da Casa"].isin(novos_ids)]
        real_key = df_kas[COLUNAS_CURADORIA].sum().sum() if not df_kas.empty else 0.0

        df_demais = df_periodo_eshows[
            ~df_periodo_eshows["Id da Casa"].isin(novos_ids)
            & ~df_periodo_eshows["Id da Casa"].isin(kas_ids)
        ]
        real_outros = df_demais[COLUNAS_CURADORIA].sum().sum() if not df_demais.empty else 0.0

    real_curadoria = real_novos + real_key + real_outros
    real_obj_principal = real_curadoria + real_plat + real_fint

    def perc(r, m):
        return (r / m) * 100 if m else 0

    progresso_obj1 = perc(real_obj_principal, meta_obj_principal)
    progresso_obj1 = min(progresso_obj1, 100.0)  # Limitar a 100%
    
    print(f"RESULTADOS DO OBJETIVO 1:")
    print(f"Meta Novos: {meta_novos:.2f} | Real Novos: {real_novos:.2f}")
    print(f"Meta Key: {meta_key:.2f} | Real Key: {real_key:.2f}")
    print(f"Meta Outros: {meta_outros:.2f} | Real Outros: {real_outros:.2f}")
    print(f"Meta Plat: {meta_plat:.2f} | Real Plat: {real_plat:.2f}")
    print(f"Meta Fint: {meta_fint:.2f} | Real Fint: {real_fint:.2f}")
    print(f"Meta Obj Principal: {meta_obj_principal:.2f} | Real Obj Principal: {real_obj_principal:.2f}")
    print(f"Progresso Obj1: {progresso_obj1:.2f}%")

    # ----- OBJETIVO 3: Ser uma empresa enxuta e eficiente -----
    print("\n" + "-"*80)
    print("CALCULANDO OBJETIVO 3: Ser uma empresa enxuta e eficiente")
    print("-"*80)

    # Extrair as metas específicas do dicionário
    meta_nrr = metas["NRR"]
    meta_churn = metas["Churn"]
    meta_turnover = metas["TurnOver"]
    meta_lucratividade = metas["Lucratividade"]
    meta_crescimento_sustentavel = metas["CrescimentoSustentavel"]
    meta_palcos_vazios = metas["PalcosVazios"]
    meta_inadimplencia_real = metas["InadimplenciaReal"]
    meta_estabilidade = metas["Estabilidade"]
    meta_eficiencia = metas["EficienciaAtendimento"]
    meta_autonomia = metas["AutonomiaUsuario"]
    meta_perdas = metas["PerdasOperacionais"]
    meta_rpc = metas["ReceitaPorColaborador"]
    meta_ltv_cac = metas["LtvCac"]
    
    print("VALORES DAS METAS OBJETIVO 3:")
    print(f"NRR: {meta_nrr}, Churn: {meta_churn}, TurnOver: {meta_turnover}")
    print(f"Lucratividade: {meta_lucratividade}, Crescimento Sustentável: {meta_crescimento_sustentavel}")
    print(f"Palcos Vazios: {meta_palcos_vazios}, Inadimplência Real: {meta_inadimplencia_real}")
    print(f"Estabilidade: {meta_estabilidade}, Eficiência: {meta_eficiencia}, Autonomia: {meta_autonomia}")
    print(f"Perdas: {meta_perdas}, RPC: {meta_rpc}, LTV/CAC: {meta_ltv_cac}")
    
    # Cálculo do NRR
    print("\nCalculando NRR...")
    nrr_data = get_nrr_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global
    )
    
    # Extrai o valor do NRR do resultado
    resultado_nrr_str = nrr_data.get("resultado", "0.00%")
    try:
        realizado_nrr = float(resultado_nrr_str.replace("%", ""))
    except ValueError:
        realizado_nrr = 0.0
        
    # *** CORREÇÃO: Calcular o progresso do NRR ***
    progresso_nrr = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_nrr, 
        tipo_meta="maior", 
        kpi_name="Net Revenue Retention",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_eshows_global,
        funcao_kpi=get_nrr_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"NRR: valor={realizado_nrr:.2f}%, progresso={progresso_nrr:.2f}%")
    
    # Cálculo do Churn
    print("Calculando Churn...")
    churn_data = get_churn_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global
    )
    
    # Extrai o valor do Churn do resultado
    resultado_churn_str = churn_data.get("resultado", "0.00%")
    try:
        realizado_churn = float(resultado_churn_str.replace("%", ""))
    except ValueError:
        realizado_churn = 0.0
        
    # *** CORREÇÃO: Calcular o progresso do Churn ***
    progresso_churn = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_churn, 
        tipo_meta="menor", 
        kpi_name="Churn %",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_eshows_global,
        funcao_kpi=get_churn_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Churn: valor={realizado_churn:.2f}%, progresso={progresso_churn:.2f}%")

    # Cálculo do Turn Over
    print("Calculando Turn Over...")
    turnover_data = get_turnover_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_pessoas_global=df_pessoas
    )
    
    # Extrai o valor do Turn Over do resultado
    resultado_turnover_str = turnover_data.get("resultado", "0.00%")
    try:
        realizado_turnover = float(resultado_turnover_str.replace("%", ""))
    except ValueError:
        realizado_turnover = 0.0
        
    # *** CORREÇÃO: Calcular o progresso do TurnOver ***
    progresso_turnover = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_turnover, 
        tipo_meta="menor", 
        kpi_name="Turn Over",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_pessoas,
        funcao_kpi=get_turnover_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Turn Over: valor={realizado_turnover:.2f}%, progresso={progresso_turnover:.2f}%")
    
    # Cálculo da Lucratividade
    print("Calculando Lucratividade...")
    lucratividade_data = get_lucratividade_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global,
        df_base2_global=df_base2_global
    )
    
    # Extrai o valor da Lucratividade do resultado
    resultado_lucratividade_str = lucratividade_data.get("resultado", "0.00%")
    try:
        realizado_lucratividade = float(resultado_lucratividade_str.replace("%", ""))
    except ValueError:
        realizado_lucratividade = 0.0
        
    # *** CORREÇÃO: Calcular o progresso da Lucratividade ***
    progresso_lucratividade = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_lucratividade, 
        tipo_meta="maior", 
        kpi_name="Lucratividade",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_eshows_global,
        funcao_kpi=get_lucratividade_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Lucratividade: valor={realizado_lucratividade:.2f}%, progresso={progresso_lucratividade:.2f}%")
        
    # Cálculo do Crescimento Sustentável
    print("Calculando Crescimento Sustentável...")
    crescimento_sustentavel_data = get_crescimento_sustentavel_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global,
        df_base2_global=df_base2_global
    )
    
    # Extrai o valor do Crescimento Sustentável do resultado
    resultado_crescimento_sustentavel_str = crescimento_sustentavel_data.get("resultado", "0.00%")
    try:
        realizado_crescimento_sustentavel = float(resultado_crescimento_sustentavel_str.replace("%", ""))
    except ValueError:
        realizado_crescimento_sustentavel = 0.0
        
    # *** CORREÇÃO: Calcular o progresso do Crescimento Sustentável ***
    progresso_crescimento_sustentavel = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_crescimento_sustentavel, 
        tipo_meta="maior", 
        kpi_name="Crescimento Sustentável",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_eshows_global,
        funcao_kpi=get_crescimento_sustentavel_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Crescimento Sustentável: valor={realizado_crescimento_sustentavel:.2f}%, progresso={progresso_crescimento_sustentavel:.2f}%")

    # Cálculo dos Palcos Vazios
    print("Calculando Palcos Vazios...")
    palcos_vazios_data = get_palcos_vazios_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_ocorrencias_global=df_ocorrencias_global
    )
    
    # Extrai o valor de Palcos Vazios do resultado
    resultado_palcos_vazios_str = palcos_vazios_data.get("resultado", "0")
    try:
        realizado_palcos_vazios = float(resultado_palcos_vazios_str.replace("%", ""))
    except ValueError:
        realizado_palcos_vazios = 0.0
        
    # *** CORREÇÃO: Calcular o progresso dos Palcos Vazios ***
    progresso_palcos_vazios = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_palcos_vazios, 
        tipo_meta="menor", 
        kpi_name="Palcos Vazios",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_ocorrencias_global,
        funcao_kpi=get_palcos_vazios_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Palcos Vazios: valor={realizado_palcos_vazios:.2f}, progresso={progresso_palcos_vazios:.2f}%")
        
    # Cálculo da Inadimplência Real
    print("Calculando Inadimplência Real...")
    inadimplencia_real_data = get_inadimplencia_real_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global,
        df_inad_casas=df_inad_casas,
        df_inad_artistas=df_inad_artistas
    )
    
    # Extrai o valor da Inadimplência Real do resultado
    resultado_inadimplencia_real_str = inadimplencia_real_data.get("resultado", "0.00%")
    try:
        realizado_inadimplencia_real = float(resultado_inadimplencia_real_str.replace("%", ""))
    except ValueError:
        realizado_inadimplencia_real = 0.0
        
    # *** CORREÇÃO: Calcular o progresso da Inadimplência Real ***
    progresso_inadimplencia_real = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_inadimplencia_real, 
        tipo_meta="menor", 
        kpi_name="Inadimplência Real",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_eshows_global,
        funcao_kpi=get_inadimplencia_real_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Inadimplência Real: valor={realizado_inadimplencia_real:.2f}%, progresso={progresso_inadimplencia_real:.2f}%")

    # Cálculo da Estabilidade
    print("Calculando Estabilidade...")
    estabilidade_data = get_estabilidade_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_base2_global=df_base2_global
    )
    
    # Extrai o valor da Estabilidade do resultado
    resultado_estabilidade_str = estabilidade_data.get("resultado", "0.00%")
    try:
        realizado_estabilidade = float(resultado_estabilidade_str.replace("%", ""))
    except ValueError:
        realizado_estabilidade = 0.0
        
    # *** CORREÇÃO: Calcular o progresso da Estabilidade ***
    progresso_estabilidade = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_estabilidade, 
        tipo_meta="maior", 
        kpi_name="Estabilidade",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_base2_global,
        funcao_kpi=get_estabilidade_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Estabilidade: valor={realizado_estabilidade:.2f}%, progresso={progresso_estabilidade:.2f}%")
    
    # Cálculo da Eficiência de Atendimento
    print("Calculando Eficiência de Atendimento...")
    eficiencia_data = get_eficiencia_atendimento_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_base2_global=df_base2_global
    )
    
    # Extrai o valor da Eficiência de Atendimento do resultado
    resultado_eficiencia_str = eficiencia_data.get("resultado", "0.00%")
    try:
        realizado_eficiencia = float(resultado_eficiencia_str.replace("%", ""))
    except ValueError:
        realizado_eficiencia = 0.0
        
    # *** CORREÇÃO: Calcular o progresso da Eficiência de Atendimento ***
    progresso_eficiencia = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_eficiencia, 
        tipo_meta="maior", 
        kpi_name="Eficiência de Atendimento",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_base2_global,
        funcao_kpi=get_eficiencia_atendimento_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Eficiência de Atendimento: valor={realizado_eficiencia:.2f}%, progresso={progresso_eficiencia:.2f}%")
    
    # Cálculo da Autonomia do Usuário
    print("Calculando Autonomia do Usuário...")
    autonomia_data = get_autonomia_usuario_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_base2_global=df_base2_global
    )
    
    # Extrai o valor da Autonomia do Usuário do resultado
    resultado_autonomia_str = autonomia_data.get("resultado", "0.00%")
    try:
        realizado_autonomia = float(resultado_autonomia_str.replace("%", ""))
    except ValueError:
        realizado_autonomia = 0.0
        
    # *** CORREÇÃO: Calcular o progresso da Autonomia do Usuário ***
    progresso_autonomia = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_autonomia, 
        tipo_meta="maior", 
        kpi_name="Autonomia do Usuário",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_base2_global,
        funcao_kpi=get_autonomia_usuario_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Autonomia do Usuário: valor={realizado_autonomia:.2f}%, progresso={progresso_autonomia:.2f}%")
    
    # Cálculo das Perdas Operacionais
    print("Calculando Perdas Operacionais...")
    perdas_data = get_perdas_operacionais_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global,
        df_base2_global=df_base2_global
    )
    
    # Extrai o valor das Perdas Operacionais do resultado
    resultado_perdas_str = perdas_data.get("resultado", "0.00%")
    try:
        realizado_perdas = float(resultado_perdas_str.replace("%", ""))
    except ValueError:
        realizado_perdas = 0.0
        
    # *** CORREÇÃO: Calcular o progresso das Perdas Operacionais ***
    progresso_perdas = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_perdas, 
        tipo_meta="menor", 
        kpi_name="Perdas Operacionais",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_eshows_global,
        funcao_kpi=get_perdas_operacionais_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Perdas Operacionais: valor={realizado_perdas:.2f}%, progresso={progresso_perdas:.2f}%")
    
    # Cálculo da Receita por Colaborador
    print("Calculando Receita por Colaborador...")
    rpc_data = get_rpc_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global,
        df_pessoas_global=df_pessoas
    )
    
    # Extrai o valor da Receita por Colaborador do resultado
    resultado_rpc_str = rpc_data.get("resultado", "R$0")
    try:
        # Para Receita por Colaborador, precisamos tratar o formato monetário
        valor_str = resultado_rpc_str.replace("R$", "").replace("k", "000").replace("M", "000000")
        valor_str = valor_str.replace(",", ".")
        realizado_rpc = float(valor_str)
    except ValueError:
        realizado_rpc = 0.0
        
    # *** CORREÇÃO: Calcular o progresso da Receita por Colaborador ***
    progresso_rpc = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_rpc, 
        tipo_meta="maior", 
        kpi_name="Receita por Colaborador",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_pessoas,
        funcao_kpi=get_rpc_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"Receita por Colaborador: valor={realizado_rpc:.2f}, progresso={progresso_rpc:.2f}%")
        
    # Cálculo do LTV/CAC
    print("Calculando LTV/CAC...")
    ltv_cac_data = get_ltv_cac_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_eshows_global=df_eshows_global,
        df_base2_global=df_base2_global,
        df_casas_earliest_global=df_casas_earliest,
        df_casas_latest_global=df_casas_latest
    )
    
    # Extrai o valor do LTV/CAC do resultado
    resultado_ltv_cac_str = ltv_cac_data.get("resultado", "0.00")
    try:
        # Para LTV/CAC, temos um valor numérico simples
        realizado_ltv_cac = float(resultado_ltv_cac_str.replace(",", "."))
    except ValueError:
        realizado_ltv_cac = 0.0
        
    # *** CORREÇÃO: Calcular o progresso do LTV/CAC ***
    progresso_ltv_cac = calcular_progresso_kpi_com_historico(
        valor_atual=realizado_ltv_cac, 
        tipo_meta="maior", 
        kpi_name="LTV/CAC",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_eshows_global,
        funcao_kpi=get_ltv_cac_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"LTV/CAC: valor={realizado_ltv_cac:.2f}, progresso={progresso_ltv_cac:.2f}%")

    # Média dos progressos para o objetivo 3 (todos os 13 KPIs)
    todos_progressos_obj3 = [
        progresso_nrr,
        progresso_churn,
        progresso_turnover,
        progresso_lucratividade,
        progresso_crescimento_sustentavel,
        progresso_palcos_vazios,
        progresso_inadimplencia_real,
        progresso_estabilidade,
        progresso_eficiencia,
        progresso_autonomia,
        progresso_perdas,
        progresso_rpc,
        progresso_ltv_cac
    ]
    
    # Filtra valores válidos (maiores que zero)
    progressos_validos_obj3 = [p for p in todos_progressos_obj3 if p > 0]
    
    if progressos_validos_obj3:
        progresso_obj3 = sum(progressos_validos_obj3) / len(progressos_validos_obj3)
    else:
        progresso_obj3 = 0
        
    print(f"Progresso Obj3: {progresso_obj3:.2f}% (média de {len(progressos_validos_obj3)} KPIs válidos)")
    
    # ----- OBJETIVO 4: Melhorar a reputação da eshows -----
    print("\n" + "-"*80)
    print("CALCULANDO OBJETIVO 4: Melhorar a reputação da eshows")
    print("-"*80)
    
    # Cálculo do NPS de Artistas
    print("Calculando NPS Artistas...")
    nps_artistas_data = get_nps_artistas_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_nps_global=df_base2_global
    )
    try:
        val_nps_artistas = float(nps_artistas_data["resultado"].replace("%", ""))
    except:
        val_nps_artistas = 0.0

    progresso_nps_artistas = calcular_progresso_kpi_com_historico(
        valor_atual=val_nps_artistas,
        tipo_meta="maior",
        kpi_name="NPS Artistas",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_base2_global,
        funcao_kpi=get_nps_artistas_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"NPS Artistas: valor={val_nps_artistas:.2f}%, progresso={progresso_nps_artistas:.2f}%")

    # Cálculo do NPS de Equipe
    print("Calculando NPS Equipe...")
    nps_equipe_data = get_nps_equipe_variables(
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_nps_global=df_base2_global
    )
    try:
        val_nps_equipe = float(nps_equipe_data["resultado"].replace("%", ""))
    except:
        val_nps_equipe = 0.0

    progresso_nps_equipe = calcular_progresso_kpi_com_historico(
        valor_atual=val_nps_equipe,
        tipo_meta="maior",
        kpi_name="NPS Equipe",
        ano=ano,
        periodo=periodo,
        mes=mes_selecionado if periodo == "Mês Aberto" else None,
        custom_range=custom_range if periodo == "custom-range" else None,
        df_global=df_base2_global,
        funcao_kpi=get_nps_equipe_variables,
        dicionario_metas=metas,
        debug=False
    )
    print(f"NPS Equipe: valor={val_nps_equipe:.2f}%, progresso={progresso_nps_equipe:.2f}%")

    # Média dos progressos para o objetivo 4
    progressos_obj4 = [progresso_nps_artistas, progresso_nps_equipe]
    progresso_obj4 = sum(progressos_obj4) / len(progressos_obj4) if progressos_obj4 else 0
    print(f"Progresso Obj4: {progresso_obj4:.2f}%")
    
    # Calcula o progresso geral (média dos objetivos 1, 3 e 4)
    progresso_geral = (progresso_obj1 + progresso_obj3 + progresso_obj4) / 3
    
    # Limita entre 0 e 100
    progresso_geral = max(0, min(100, progresso_geral))
    
    # Imprime os valores para debug
    print("\n" + "="*80)
    print(f"RESUMO DO CÁLCULO DO PROGRESSO GERAL:")
    print(f"Período original: {original_periodo}, Período usado: {periodo}")
    print(f"Progresso Obj1: {progresso_obj1:.2f}%")
    print(f"Progresso Obj3: {progresso_obj3:.2f}%")
    print(f"Progresso Obj4: {progresso_obj4:.2f}%")
    print(f"Progresso Geral: {progresso_geral:.2f}%")
    print("="*80)
    
    # Forçar a saída imediata dos logs (pode ajudar em ambientes com redirecionamento)
    import sys
    sys.stdout.flush()
    
    return progresso_geral

# =============================================================================
# CALCULAR PROGRESSO PARA KPIs
# =============================================================================
def obter_periodo_cronologico_anterior(ano, periodo, mes=None, custom_range=None):
    """
    Retorna o período cronologicamente anterior ao informado.
    
    Exemplos:
    - fev/2025 -> jan/2025 (não fev/2024)
    - 1º Trim/2025 -> 4º Trim/2024 (não 1º Trim/2024)
    - Mês Aberto(mar/2025) -> Mês Aberto(fev/2025)
    - custom-range -> mês anterior ou trimestre anterior, dependendo da duração do intervalo
    
    Args:
        ano (int): Ano de referência
        periodo (str): Tipo de período
        mes (int, optional): Mês específico para 'Mês Aberto'
        custom_range (tuple, optional): (data_inicial, data_final) para período personalizado
    
    Returns:
        tuple: (ano_anterior, periodo_anterior, mes_anterior)
    """
    anterior_ano = ano
    anterior_periodo = periodo
    anterior_mes = mes
    anterior_custom_range = None  # Não retornamos isso, mas usamos nas operações
    
    # Para período personalizado, vamos calcular um período anterior proporcional
    if periodo == "custom-range" and custom_range:
        start_date, end_date = custom_range
        
        # Calcular a duração do intervalo em dias
        import math
        from datetime import timedelta
        
        # Defina diferença em dias
        delta_dias = (end_date - start_date).days + 1
        
        # Caso 1: Se o intervalo for menor que 45 dias, tratamos como "Mês Aberto"
        if delta_dias <= 45:
            # Pegamos o mês da data inicial e tratamos como um "Mês Aberto"
            mes_custom = start_date.month
            ano_custom = start_date.year
            
            # Determinamos o mês anterior
            if mes_custom == 1:  # janeiro -> dezembro do ano anterior
                anterior_mes = 12
                anterior_ano = ano_custom - 1
                anterior_periodo = "Mês Aberto"
            else:
                anterior_mes = mes_custom - 1
                anterior_ano = ano_custom
                anterior_periodo = "Mês Aberto"
        
        # Caso 2: Se o intervalo for entre 45 e 120 dias, tratamos como "Trimestre"
        elif delta_dias <= 120:
            # Determinar o trimestre baseado no mês da data inicial
            mes_custom = start_date.month
            ano_custom = start_date.year
            
            # Mapear para trimestre
            trim_num = math.ceil(mes_custom / 3)
            
            # Determinar trimestre anterior
            if trim_num == 1:  # 1º Trim -> 4º Trim do ano anterior
                anterior_periodo = "4° Trimestre"
                anterior_ano = ano_custom - 1
            else:  # Outros trimestres, só decrementar
                anterior_periodo = f"{trim_num - 1}° Trimestre"
                anterior_ano = ano_custom
            
            # Limpamos o mes para não confundir
            anterior_mes = None
        
        # Caso 3: Se o intervalo for maior que 120 dias, tratamos como "Ano Completo"
        else:
            anterior_periodo = "Ano Completo"
            anterior_ano = start_date.year - 1
            anterior_mes = None
    
    # Para Mês Aberto, é só decrementar o mês
    elif periodo == "Mês Aberto" and mes is not None:
        if mes == 1:  # janeiro -> dezembro do ano anterior
            anterior_mes = 12
            anterior_ano = ano - 1
        else:
            anterior_mes = mes - 1
            
    # Para trimestres, é preciso voltar para o trimestre anterior
    elif "Trimestre" in periodo:
        # Mapear número do trimestre
        trim_map = {
            "1° Trimestre": 1,
            "2° Trimestre": 2,
            "3° Trimestre": 3,
            "4° Trimestre": 4
        }
        
        # Obter número do trimestre atual
        trim_num = trim_map.get(periodo, 1)
        
        if trim_num == 1:  # 1º Trim -> 4º Trim do ano anterior
            anterior_periodo = "4° Trimestre"
            anterior_ano = ano - 1
        else:  # Outros trimestres, só decrementar
            anterior_periodo = f"{trim_num - 1}° Trimestre"
    
    # Para Ano Completo, é só decrementar o ano
    elif periodo == "Ano Completo":
        anterior_ano = ano - 1
    
    # Para YTD, é mais complexo (não implementado aqui)
    
    return anterior_ano, anterior_periodo, anterior_mes

def calcular_progresso_kpi_com_historico(
    valor_atual, 
    meta=None, 
    tipo_meta="maior", 
    kpi_name=None,
    ano=None,
    periodo=None,
    mes=None,
    custom_range=None,
    df_global=None,
    funcao_kpi=None,
    max_periodos_anteriores=2,
    debug=True,
    dicionario_metas=None
):
    """
    Calcula o progresso percentual baseado na proximidade da meta (70%) e evolução (30%).
    Utiliza ajustes fixos baseados no status atual do KPI.
    
    Args:
        valor_atual (float): Valor atual do KPI
        meta (float, optional): Meta para o KPI. Se None e dicionario_metas fornecido, 
                               tenta obter do dicionário.
        tipo_meta (str): "maior" ou "menor", indica se valor maior é melhor
        kpi_name (str): Nome do KPI para logs e referência no dicionário de metas
        ano (int): Ano da análise
        periodo (str): Período da análise
        mes (int, optional): Mês específico, se aplicável
        custom_range (tuple, optional): (data_inicial, data_final) para período personalizado
        df_global (DataFrame): DataFrame com dados relevantes
        funcao_kpi (function): Função que calcula o KPI para períodos históricos
        max_periodos_anteriores (int): Quantidade máxima de períodos anteriores a verificar
        debug (bool): Flag para imprimir informações de debug
        dicionario_metas (dict, optional): Dicionário com todas as metas, conforme retornado 
                                         pela função ler_todas_as_metas
    """
    # Remover as duas linhas abaixo se existirem
    # from .controles import zonas_de_controle 
    # from .utils import kpi_bases_mapping
    
    # Se meta não foi fornecida diretamente, tenta obter do dicionário de metas
    if meta is None and dicionario_metas is not None and kpi_name is not None:
        # Mapeia nomes de KPIs para chaves no dicionário de metas
        kpi_to_meta_key = {
            "Net Revenue Retention": "NRR",
            "Churn %": "Churn",
            "Turn Over": "TurnOver",
            "Lucratividade": "Lucratividade",
            "Crescimento Sustentável": "CrescimentoSustentavel",
            "Palcos Vazios": "PalcosVazios",
            "Inadimplência Real": "InadimplenciaReal",
            "Estabilidade": "Estabilidade",
            "Eficiência de Atendimento": "EficienciaAtendimento",
            "Autonomia do Usuário": "AutonomiaUsuario",
            "Perdas Operacionais": "PerdasOperacionais",
            "Receita por Colaborador": "ReceitaPorColaborador",
            "LTV/CAC": "LtvCac",  # Nova chave para LTV/CAC
            "NPS Artistas": "NPSArtistas",
            "NPS Equipe": "NPSEquipe",
            # Adicione mapeamentos para KPIs do Objetivo 1 se necessário
        }
        
        # Obter a chave correspondente no dicionário de metas
        meta_key = kpi_to_meta_key.get(kpi_name)
        if meta_key and meta_key in dicionario_metas:
            meta = dicionario_metas[meta_key]
            if debug:
                print(f"Meta para {kpi_name} obtida do dicionário: {meta}")
    
    # Iniciar impressão de debug
    if debug:
        print(f"\n{'=' * 60}")
        print(f"CÁLCULO DE PROGRESSO SIMPLIFICADO: {kpi_name}")
        print(f"  Valor atual: {valor_atual:.2f}% ({periodo}/{ano}/{mes if mes else 'N/A'})")
        if periodo == "custom-range" and custom_range:
            print(f"  Período personalizado: {custom_range[0].strftime('%d/%m/%Y')} até {custom_range[1].strftime('%d/%m/%Y')}")
        print(f"  Meta: {meta:.2f}%")
        print(f"  Tipo: {tipo_meta} é melhor")
        print(f"{'=' * 60}")
    
    # 1. Premissa principal: Bateu meta = 100% de progresso
    if (tipo_meta == "maior" and valor_atual >= meta) or \
       (tipo_meta == "menor" and valor_atual <= meta):
        if debug:
            print(f"✓ Valor atual atingiu ou superou a meta - Progresso = 100%")
            print(f"{'=' * 60}")
        return 100.0
    
    # 2. Determinar status atual para ajuste posterior
    status_atual = "controle"  # Valor padrão
    try:
        # Criar um dicionário compatível com a função get_kpi_status
        kpi_descriptions = {}
        if kpi_name in zonas_de_controle:
            zonas = zonas_de_controle[kpi_name]
            kpi_descriptions[kpi_name] = {
                'behavior': zonas.get('comportamento', 'Positivo'),
                'control_values': {
                    'critico': [zonas.get('critico', [-float('inf'), -5])[0], zonas.get('critico', [-float('inf'), -5])[1]],
                    'ruim': [zonas.get('ruim', [-5, 0])[0], zonas.get('ruim', [-5, 0])[1]],
                    'controle': [zonas.get('controle', [0, 10])[0], zonas.get('controle', [0, 10])[1]],
                    'bom': [zonas.get('bom', [10, 20])[0], zonas.get('bom', [10, 20])[1]],
                    'excelente': [zonas.get('excelente', [20, float('inf')])[0], zonas.get('excelente', [20, float('inf')])[1]]
                }
            }
        status_atual, _ = get_kpi_status(kpi_name, valor_atual, kpi_descriptions)
    except Exception as e:
        if debug:
            print(f"⚠️ Erro ao obter status: {str(e)}")
    
    if debug:
        print(f"📊 Status atual: {status_atual.upper()}")
    
    # 3. Buscar valor do período cronologicamente anterior
    valor_anterior = None
    periodo_anterior_str = "desconhecido"
    
    if ano is not None and periodo is not None and funcao_kpi is not None:
        # Inicializar com o período atual
        ano_ant = ano
        periodo_ant = periodo
        mes_ant = mes
        custom_range_ant = custom_range  # Para período personalizado
        periodos_verificados = 0
        
        if debug:
            print("\n🔍 Buscando dados históricos cronológicos...")
        
        # Loop para buscar até max_periodos_anteriores
        while periodos_verificados < max_periodos_anteriores and valor_anterior is None:
            # Obter período cronologicamente anterior
            ano_ant, periodo_ant, mes_ant = obter_periodo_cronologico_anterior(
                ano_ant, periodo_ant, mes_ant, custom_range_ant
            )
            periodos_verificados += 1
            
            # Reset custom_range após a primeira iteração, pois só é relevante para o período atual
            custom_range_ant = None
            
            if periodo_ant == "custom-range":
                periodo_str = f"Período personalizado/{ano_ant}"
            else:
                periodo_str = f"{periodo_ant}/{ano_ant}/{mes_ant if mes_ant else 'N/A'}"
            
            if debug:
                print(f"  • Verificando período: {periodo_str}")
            
            # Tentar obter valor para esse período
            try:
                # Determine qual parâmetro passar com base no nome da função
                if 'nrr' in funcao_kpi.__name__.lower():
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,  # Não passamos custom_range para períodos anteriores
                        df_eshows_global=df_global
                    )
                elif 'churn' in funcao_kpi.__name__.lower():
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_eshows_global=df_global
                    )
                elif 'turnover' in funcao_kpi.__name__.lower():
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_pessoas_global=df_global
                    )
                elif 'lucratividade' in funcao_kpi.__name__.lower():
                    # Caso específico para Lucratividade que precisa de df_base2_global
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_eshows_global=df_global,
                        df_base2_global=df_base2  # Usando a variável global df_base2
                    )
                elif 'crescimento_sustentavel' in funcao_kpi.__name__.lower():
                    # Caso específico para Crescimento Sustentável que também precisa de df_base2_global
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_eshows_global=df_global,
                        df_base2_global=df_base2  # Usando a variável global df_base2
                    )
                elif 'palcos_vazios' in funcao_kpi.__name__.lower():
                    # Caso específico para Palcos Vazios
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_ocorrencias_global=df_global
                    )
                elif 'inadimplencia_real' in funcao_kpi.__name__.lower():
                    # Caso específico para Inadimplência Real
                    # Aqui precisamos de duas bases de dados adicionais (inad_casas e inad_artistas)
                    # que seriam passadas via injeção, mas como usamos df_global para o df_eshows_global,
                    # vamos carregar as outras bases diretamente
                    df_inad_casas, df_inad_artistas = carregar_base_inad()
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_eshows_global=df_global,
                        df_inad_casas=df_inad_casas,
                        df_inad_artistas=df_inad_artistas
                    )
                elif 'estabilidade' in funcao_kpi.__name__.lower():
                    # Caso específico para Estabilidade
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_base2_global=df_global
                    )
                elif 'eficiencia_atendimento' in funcao_kpi.__name__.lower():
                    # Caso específico para Eficiência de Atendimento
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_base2_global=df_global
                    )
                elif 'autonomia_usuario' in funcao_kpi.__name__.lower():
                    # Caso específico para Autonomia do Usuário
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_base2_global=df_global
                    )
                elif 'perdas_operacionais' in funcao_kpi.__name__.lower():
                    # Caso específico para Perdas Operacionais
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_eshows_global=df_global,
                        df_base2_global=df_base2  # Usando a variável global df_base2
                    )
                elif 'rpc' in funcao_kpi.__name__.lower():
                    # Caso específico para Receita por Colaborador
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_eshows_global=df_eshows,  # Usando a variável global df_eshows
                        df_pessoas_global=df_global
                    )
                elif 'ltv_cac' in funcao_kpi.__name__.lower():
                    # Caso específico para LTV/CAC
                    # Calcular df_casas_earliest e df_casas_latest
                    df_casas_earliest = df_eshows.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow") if df_eshows is not None and not df_eshows.empty else None
                    df_casas_latest = df_eshows.groupby("Id da Casa")["Data do Show"].max().reset_index(name="LastShow") if df_eshows is not None and not df_eshows.empty else None
                    
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_eshows_global=df_global,
                        df_base2_global=df_base2,
                        df_casas_earliest_global=df_casas_earliest,
                        df_casas_latest_global=df_casas_latest
                    )
                elif 'nps_artistas' in funcao_kpi.__name__.lower() or 'nps_equipe' in funcao_kpi.__name__.lower():
                    # Caso específico para NPS
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None,
                        df_base2_global=df_global
                    )
                else:
                    # Comportamento genérico para outras funções
                    # Nota: isso pode causar erros se a função esperar parâmetros específicos
                    resultado_anterior = funcao_kpi(
                        ano=ano_ant,
                        periodo=periodo_ant,
                        mes=mes_ant,
                        custom_range=None
                    )
                
                if "resultado" in resultado_anterior:
                    try:
                        valor_temp = float(resultado_anterior["resultado"].replace("%", "").replace("R$", "").replace("k", "000").replace("M", "000000"))
                        has_values = "variables_values" in resultado_anterior and any(resultado_anterior["variables_values"].values())
                        
                        # Considerar válido se não for zero ou se tem dados
                        if valor_temp != 0.0 or has_values:
                            valor_anterior = valor_temp
                            periodo_anterior_str = periodo_str
                            
                            if debug:
                                print(f"  ✓ Encontrado: {valor_anterior:.2f}% em {periodo_str}")
                                break
                    except (ValueError, AttributeError):
                        if debug:
                            print(f"  ✗ Formato inválido no período {periodo_str}")
                else:
                    if debug:
                        print(f"  ✗ Sem resultado válido no período {periodo_str}")
            except Exception as e:
                if debug:
                    print(f"  ✗ Erro ao buscar período {periodo_str}: {str(e)}")
        
        if valor_anterior is None and debug:
            print(f"  ✗ Não foi possível encontrar dados históricos após {periodos_verificados} tentativas")
    
    # 4. NOVA ABORDAGEM SIMPLIFICADA
    
    # 4.1 Calcular contribuição da proximidade da meta (70% do peso)
    if tipo_meta == "maior":
        prox_meta = valor_atual / meta if meta != 0 else 0
    else:
        prox_meta = meta / valor_atual if valor_atual != 0 else 0
    
    prox_meta = min(max(prox_meta, 0), 1)  # Limitar entre 0-1
    contribuicao_prox_meta = prox_meta * 70  # 70% do peso total
    
    if debug:
        print(f"\n📏 Contribuição da proximidade da meta (70%):")
        print(f"  • Razão: {prox_meta:.2f}")
        print(f"  • Contribuição: {contribuicao_prox_meta:.2f}%")
    
    # 4.2 Calcular contribuição da evolução (30% do peso)
    if valor_anterior is not None and valor_anterior != 0:
        if tipo_meta == "maior":
            evolucao = (valor_atual - valor_anterior) / abs(valor_anterior)
        else:
            evolucao = (valor_anterior - valor_atual) / abs(valor_anterior)
        
        # Limitar a evolução entre -1 e 1 (para casos extremos)
        evolucao = min(max(evolucao, -1), 1)
        
        # Transformar evolução de -1~1 para 0~30
        contribuicao_evolucao = ((evolucao + 1) / 2) * 30
        
        evolucao_descricao = "✓ Positiva" if evolucao >= 0 else "✗ Negativa"
        evolucao_percentual = evolucao * 100
    else:
        # MODIFICAÇÃO: Se não há histórico, a contribuição da evolução é baseada apenas no status atual
        # e na distância da meta (já coberta pela contribuição_prox_meta)
        contribuicao_evolucao = 15  # Valor neutro (50% de 30)
        
        # Ajuste baseado no status atual
        if status_atual in ["bom", "excelente"]:
            contribuicao_evolucao = 25  # 83% de 30
        elif status_atual in ["critico", "ruim"]:
            contribuicao_evolucao = 5   # 17% de 30
        
        evolucao_descricao = "● Sem histórico, status atual: " + status_atual.upper()
        evolucao_percentual = 0
    
    if debug:
        print(f"\n📈 Contribuição da evolução (30%):")
        print(f"  • Período anterior: {valor_anterior:.2f}% ({periodo_anterior_str})" if valor_anterior is not None else "  • Sem dados do período anterior")
        print(f"  • Evolução: {evolucao_descricao} ({evolucao_percentual:.2f}%)")
        print(f"  • Contribuição: {contribuicao_evolucao:.2f}%")
    
    # 4.3 Combinar as contribuições
    progresso_base = contribuicao_prox_meta + contribuicao_evolucao
    
    if debug:
        print(f"\n🧮 Progresso base (proximidade + evolução):")
        print(f"  • {contribuicao_prox_meta:.2f}% + {contribuicao_evolucao:.2f}% = {progresso_base:.2f}%")
    
    # 4.4 Aplicar ajuste baseado no status
    ajustes_status = {
        "critico": -30,
        "ruim": -15,
        "controle": 0,
        "bom": 10,
        "excelente": 15
    }
    ajuste = ajustes_status.get(status_atual, 0)
    
    if debug:
        dir_ajuste = "+" if ajuste >= 0 else ""
        print(f"\n🛠️ Ajuste por status ({status_atual.upper()}):")
        print(f"  • Ajuste: {dir_ajuste}{ajuste}%")
    
    progresso_final = progresso_base + ajuste
    
    # 4.5 Limitar entre 0 e 100%
    progresso_final = max(0.0, min(100.0, progresso_final))
    
    # Log final
    if debug:
        print(f"\n{'=' * 60}")
        print(f"RESULTADO FINAL: {kpi_name}")
        print(f"  • Proximidade da meta: {contribuicao_prox_meta:.2f}%")
        print(f"  • Evolução: {contribuicao_evolucao:.2f}%")
        print(f"  • Ajuste por status: {ajuste}%")
        print(f"  • PROGRESSO FINAL: {progresso_final:.2f}%")
        print(f"{'=' * 60}")
    
    return progresso_final

# =============================================================================
# VERSÃO SIMPLES (antiga) DE CRIAR INDICADOR COM BARRA
# (Continuamos usando para alguns subcards que usem use_svg=True,
#  mas que seja "progress bar". Para status, criamos a outra.)
# =============================================================================
def create_status_svg(
    current_value_percent,    # valor do KPI
    meta_value_percent,       # meta do KPI
    kpi_name="Net Revenue Retention",
    kpi_descriptions=None,
    margin_lower=5.0,
    margin_upper=5.0,
    force_negative_behavior=False
):
    """
    Gera um SVG com o layout otimizado que:
    - Usa faixas definidas em controles.zonas_de_controle
    - Plota um degradê do 'pior' para o 'melhor' e posiciona o valor atual e a meta
    - Permite exibir valores como percentual, monetário ou numérico.
    - Garante que todas as zonas de controle sejam visíveis com espaçamento adequado
    """


    # --------------------------------------------------
    # 1) Mapeamento Nome->Formato (você pode customizar)
    # --------------------------------------------------
    #  - "percentual": mostra "10.0%"
    #  - "monetario": mostra "R$10.0k"
    #  - "numero_2f":    mostra "10.0" (2 casas decimais)
    kpi_display_format = {
        "receita por colaborador": "monetario",
        "palcos vazios": "numero",
        "ltv/cac": "numero_2f",  # Adicionado LTV/CAC como formato numero_2f
        "inadimplência real": "percentual",
        "inadimplencia real": "percentual",
        # etc.
    }

    # Função para descobrir o formato do KPI
    def detectar_formato(kpi_nm):
        # padrão = percentual
        formato = "percentual"
        if not kpi_nm:
            return formato
        nm_lower = kpi_nm.lower()

        for kpi_substring, form in kpi_display_format.items():
            if kpi_substring in nm_lower:
                formato = form
                break
        return formato

    # Qual formato usar para este KPI?
    kpi_formato = detectar_formato(kpi_name)
    
    # Substituir a formatação interna pela formatar_valor_utils
    def formatar_valor_interno(valor, formato):
        # Usamos formatar_valor_utils diretamente
        return formatar_valor_utils(valor, formato)

    # Debug para verificar os valores
    print(f"SVG: {kpi_name} - Atual={current_value_percent}, Meta={meta_value_percent}")

    # --------------------------------------------------
    # 3) Resto da lógica do gradiente
    # --------------------------------------------------

    # 1) Identifica comportamento (Positivo/Negativo)
    if kpi_name not in zonas_de_controle:
        intervals = {
            "critico":   [-float('inf'), -5],
            "ruim":      [-5, 0],
            "controle":  [0, 10],
            "bom":       [10, 20],
            "excelente": [20, float('inf')]
        }
        comportamento = "Positivo"
    else:
        intervals = {
            k: v for k, v in zonas_de_controle[kpi_name].items()
            if k not in ['comportamento']
        }
        comportamento = zonas_de_controle[kpi_name].get('comportamento', 'Positivo')

    if force_negative_behavior:
        comportamento = "Negativo"

    # Cores no gradiente
    colors_left_to_right = [
        "#f87171",  # Vermelho
        "#fb923c",  # Laranja
        "#fbbf24",  # Amarelo
        "#4ade80",  # Verde claro
        "#22c55e",  # Verde escuro
    ]
    if comportamento == "Negativo":
        colors_left_to_right.reverse()

    # Monta faixas
    raw_intervals = []
    for key in ["critico", "ruim", "controle", "bom", "excelente"]:
        if key in intervals:
            vmin, vmax = intervals[key]
            if isinstance(vmin, str) or vmin == float('-inf'):
                vmin = -999999
            if isinstance(vmax, str) or vmax == float('inf'):
                vmax = 999999
            raw_intervals.append({
                "key": key,
                "vmin": float(vmin),
                "vmax": float(vmax)
            })
    raw_intervals.sort(key=lambda x: x["vmin"])

    faixas = []
    for i, interval in enumerate(raw_intervals):
        color = colors_left_to_right[i % len(colors_left_to_right)]
        faixas.append((interval["vmin"], interval["vmax"], color, interval["key"]))

    if not faixas:
        # Fallback
        if comportamento == "Negativo":
            faixas = [
                (-999999, -5, colors_left_to_right[0], "critico"),
                (-5, 0, colors_left_to_right[1], "ruim"),
                (0, 10, colors_left_to_right[2], "controle"),
                (10, 20, colors_left_to_right[3], "bom"),
                (20, 999999, colors_left_to_right[4], "excelente")
            ]
        else:
            faixas = [
                (-999999, -5, colors_left_to_right[0], "critico"),
                (-5, 0, colors_left_to_right[1], "ruim"),
                (0, 10, colors_left_to_right[2], "controle"),
                (10, 20, colors_left_to_right[3], "bom"),
                (20, 999999, colors_left_to_right[4], "excelente")
            ]

    # Determinar os limites reais dos intervalos (excluindo infinitos)
    limites_reais = []
    
    # Extrair todos os limites finitos das faixas
    for faixa in faixas:
        vmin, vmax = faixa[0], faixa[1]
        if vmin > -90000 and vmin not in limites_reais:
            limites_reais.append(vmin)
        if vmax < 90000 and vmax not in limites_reais:
            limites_reais.append(vmax)
    
    limites_reais.sort()
    
    # Se não houver limites suficientes, criar padrões
    if len(limites_reais) < 2:
        if comportamento == "Negativo":
            limites_reais = [0, 0.5, 1, 2, 5]
        else:
            limites_reais = [-5, 0, 5, 10, 20]
    
    # Adicionar o valor atual e a meta aos limites, se estiverem dentro de um range razoável
    if current_value_percent is not None and -90000 < current_value_percent < 90000:
        limites_reais.append(current_value_percent)
    
    if meta_value_percent is not None and -90000 < meta_value_percent < 90000:
        limites_reais.append(meta_value_percent)
    
    limites_reais.sort()
    
    # Definir os limites de visualização
    # Aqui está a chave: usaremos os limites reais em vez dos valores min/max absolutos
    
    # Encontrar o limite mínimo e máximo a serem exibidos
    min_display = min(limites_reais)
    max_display = max(limites_reais)
    
    # Garantir que o valor atual esteja dentro do range visível
    if current_value_percent < min_display:
        min_display = current_value_percent
    if current_value_percent > max_display:
        max_display = current_value_percent
    
    # Garantir que a meta esteja dentro do range visível
    if meta_value_percent is not None:
        if meta_value_percent < min_display:
            min_display = meta_value_percent
        if meta_value_percent > max_display:
            max_display = meta_value_percent
    
    # Calcular o span (intervalo total)
    total_span = max_display - min_display
    
    # IMPORTANTE: Se o span for muito pequeno, ajustamos para garantir
    # que todas as faixas sejam visíveis
    min_required_span = 0
    
    # Calcular o span mínimo necessário para mostrar todas as faixas
    for i in range(len(limites_reais) - 1):
        min_required_span += (limites_reais[i+1] - limites_reais[i])
    
    # Se o span atual for menor que o necessário, expandir
    if total_span < min_required_span or total_span <= 0:
        # Expandir proporcionalmente
        min_display -= min_required_span * 0.2
        max_display += min_required_span * 0.2
        total_span = max_display - min_display
    
    # Aplicar margens extras
    low_margin = total_span * (margin_lower / 100.0)
    high_margin = total_span * (margin_upper / 100.0)
    
    # Corrigir para comportamento negativo (não permitir valores negativos)
    if comportamento == "Negativo" and min_display - low_margin < 0:
        min_display = 0
    else:
        min_display -= low_margin
        
    max_display += high_margin
    
    # Função para mapear valores para a posição na barra (0-1)
    def ratio(v):
        if max_display == min_display:  # Evitar divisão por zero
            return 0.5
        return max(0, min(1, (v - min_display) / (max_display - min_display)))
    
    # Valor atual e meta
    cv = float(current_value_percent)
    mv = float(meta_value_percent if meta_value_percent else 0.0)
    cv_r = ratio(cv)
    mv_r = ratio(mv)

    # Dimensões
    svg_w = 1100
    svg_h = 120
    bar_x = 15
    bar_y = 60
    bar_w = svg_w - 40
    bar_h = 22
    corner_r = 10

    # Triângulo
    cv_x = bar_x + (bar_w * cv_r)
    tri_cx = cv_x
    tri_size = 12
    tri_path = f"M{tri_cx},{bar_y-(tri_size/2)} L{tri_cx+tri_size},{bar_y+bar_h+4} L{tri_cx-tri_size},{bar_y+bar_h+4} Z"

    mv_x = bar_x + (bar_w * mv_r)
    line_top = bar_y - 8
    line_bottom = bar_y + bar_h + 8

    tip_w = 65
    tip_h = 24
    tip_left = cv_x - (tip_w / 2)
    if tip_left < bar_x:
        tip_left = bar_x
    if tip_left + tip_w > bar_x + bar_w:
        tip_left = (bar_x + bar_w) - tip_w

    # IMPORTANTE: Distribuição das cores no gradiente
    # Garantir que cada faixa tenha uma representação proporcional no gradiente
    
    # Primeiro, vamos calcular as posições de cada faixa no espaço normalizado (0-1)
    faixas_normalizadas = []
    for vmin, vmax, color, key in faixas:
        # Limitar os valores infinitos
        if vmin < -90000:
            vmin = min_display
        if vmax > 90000:
            vmax = max_display
            
        # Converter para o espaço normalizado
        r_min = ratio(vmin)
        r_max = ratio(vmax)
        
        # Garantir que cada faixa ocupe pelo menos 5% do espaço visual
        if r_max - r_min < 0.05:
            center = (r_min + r_max) / 2
            r_min = max(0, center - 0.025)
            r_max = min(1, center + 0.025)
            
        faixas_normalizadas.append((r_min, r_max, color, key))
    
    # Gerar os stops do gradiente com degradê contínuo
    gradient_stops = []
    
    # Adicionar stop inicial
    gradient_stops.append((0, faixas_normalizadas[0][2]))
    
    # Para criar um degradê contínuo, vamos distribuir os stops uniformemente
    for i in range(len(faixas_normalizadas)):
        r_min, r_max, color, _ = faixas_normalizadas[i]
        
        # Converter para percentual
        pos_min = r_min * 100
        pos_max = r_max * 100
        
        # Para faixas estreitas, garantir uma transição suave
        if i < len(faixas_normalizadas) - 1:
            next_color = faixas_normalizadas[i+1][2]
            mid_point = (pos_max + pos_min) / 2
            
            # Usar posição intermediária para cor atual (degradê suave)
            gradient_stops.append((mid_point, color))
            
            # Se a próxima faixa estiver muito próxima, criar uma transição gradual
            if pos_max < 100:
                # Ponto intermediário para garantir degradê entre cores
                blend_point = pos_max
                gradient_stops.append((blend_point, color))
    
    # Adicionar stop final
    gradient_stops.append((100, faixas_normalizadas[-1][2]))
    
    # Remover duplicatas próximas
    filtered_stops = []
    last_pos = -1
    last_color = None
    
    for pos, color in sorted(gradient_stops, key=lambda x: x[0]):
        # Evitar stops muito próximos
        if last_pos == -1 or abs(pos - last_pos) > 0.01 or color != last_color:
            filtered_stops.append((pos, color))
            last_pos = pos
            last_color = color
    
    gradient_stops = filtered_stops
    
    # HTML para os stops do gradiente
    gradient_stops_html = [
        f'<stop offset="{offset:.2f}%" stop-color="{color}"/>' 
        for (offset, color) in gradient_stops
    ]

    # Função para obter a cor e rótulo para um valor
    def get_color_for_value(val):
        for vmin, vmax, color, label in faixas:
            if vmin <= val <= vmax:
                return color, label
        # Fallback
        if val < faixas[0][0]:
            return faixas[0][2], faixas[0][3]
        return faixas[-1][2], faixas[-1][3]

    # IMPORTANTE: Selecionar quais limites exibir como marcações/rótulos
    # Queremos mostrar os limites significativos sem sobreposição
    
    boundaries = list(limites_reais)
    
    # Determinar os limites a serem exibidos
    # Queremos mostrar no máximo 8-10 marcações para evitar sobreposição
    max_markers = 8
    
    if len(boundaries) > max_markers:
        # Selecionar os limites mais importantes
        # Sempre incluir o primeiro e o último
        selected_boundaries = [boundaries[0]]
        
        # Calcular o intervalo ideal entre marcações
        ideal_gap = len(boundaries) / (max_markers - 2)
        
        # Selecionar marcações com base no gap ideal
        i = 0
        while i < len(boundaries) - 1:
            i += ideal_gap
            idx = round(i)
            if idx < len(boundaries) - 1:
                selected_boundaries.append(boundaries[idx])
        
        # Adicionar o último limite
        if boundaries[-1] not in selected_boundaries:
            selected_boundaries.append(boundaries[-1])
        
        boundaries = selected_boundaries
    
    # Adicionar a meta se não estiver próxima a nenhum limite existente
    if meta_value_percent is not None:
        add_meta = True
        for b in boundaries:
            if abs(meta_value_percent - b) < 0.1:
                add_meta = False
                break
        if add_meta:
            boundaries.append(meta_value_percent)
    
    # Remover o valor atual dos limites para não exibi-lo no eixo inferior
    boundaries = [b for b in boundaries if abs(b - current_value_percent) > 0.1]
    
    # Ordenar todos os limites
    boundaries.sort()

    # Linhas e rótulos dos limites
    limit_texts = []
    limit_lines = []
    for b in boundaries:
        r_b = ratio(b)
        px = bar_x + (r_b * bar_w)
        # Formata boundary conforme o tipo do KPI
        label_text = formatar_valor_interno(b, kpi_formato)
        limit_texts.append({"x": px, "text": label_text, "value": b})
        limit_lines.append(f"""
        <line x1="{px:.1f}" y1="{bar_y - 2}" x2="{px:.1f}" y2="{bar_y + bar_h + 2}" 
              stroke="#6B7280" stroke-width="1" stroke-dasharray="2,2" opacity="0.4" />
        """)

    # Verificar se a meta coincide com algum limite
    meta_duplicated = False
    for limit in limit_texts:
        if abs(mv - limit["value"]) < 0.1:
            meta_duplicated = True
            limit["is_meta"] = True
            break

    # Gerar HTML para rótulos dos limites
    limit_texts_svg = []
    for limit in limit_texts:
        if limit.get("is_meta", False):
            limit_texts_svg.append(f"""
            <text x="{limit['x']:.1f}" y="{bar_y + bar_h + 30}" text-anchor="middle" 
                  font-size="11" font-weight="600" fill="#111827">
              {limit['text']}
            </text>
            """)
        else:
            limit_texts_svg.append(f"""
            <text x="{limit['x']:.1f}" y="{bar_y + bar_h + 30}" text-anchor="middle" 
                  font-size="11" fill="#6B7280">
              {limit['text']}
            </text>
            """)

    # Texto da meta e do valor atual
    current_color, current_label = get_color_for_value(cv)
    meta_text_display = formatar_valor_interno(mv, kpi_formato)
    current_text_display = formatar_valor_interno(cv, kpi_formato)

    # Monta SVG
    svg_doc = f"""
<svg width="100%" height="100%"
     viewBox="0 0 {svg_w} {svg_h}"
     xmlns="http://www.w3.org/2000/svg"
     style="display:block; font-family: 'Inter', 'Segoe UI', sans-serif;">
  <defs>
    <linearGradient id="multiGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      {''.join(gradient_stops_html)}
    </linearGradient>
    <filter id="triShadow" x="-50%" y="-50%" width="200%" height="200%">
      <feDropShadow dx="1" dy="1" stdDeviation="1" flood-color="rgba(0,0,0,0.3)"/>
    </filter>
    <filter id="tooltipShadow">
      <feDropShadow dx="1" dy="1" stdDeviation="2" flood-color="rgba(0,0,0,0.15)"/>
    </filter>
  </defs>

  <!-- Título (nome do KPI) -->
  <text x="{bar_x}" y="30" font-size="16" font-weight="600" fill="#111827" text-anchor="start">
    {kpi_name}
  </text>

  <!-- Barra principal com degradê -->
  <rect
    x="{bar_x}" y="{bar_y}"
    width="{bar_w}" height="{bar_h}"
    rx="{corner_r}" ry="{corner_r}"
    fill="url(#multiGradient)"
  />

  <!-- Linhas verticais (limites das faixas) -->
  {''.join(limit_lines)}

  <!-- Rótulos dos limites -->
  {''.join(limit_texts_svg)}

  <!-- Linha Meta (pontilhada) -->
  <line x1="{mv_x}" y1="{line_top}"
        x2="{mv_x}" y2="{line_bottom}"
        stroke="#000" stroke-width="1.5"
        stroke-dasharray="3,3" opacity="0.7" />
  <text x="{mv_x}" y="{line_top - 4}"
        text-anchor="middle" font-size="11"
        fill="#111827" font-weight="500">
    Meta
  </text>
  {'' if meta_duplicated else f'''
  <text x="{mv_x}" y="{bar_y + bar_h + 30}"
        text-anchor="middle" font-size="11"
        font-weight="500" fill="#111827">
    {meta_text_display}
  </text>
  '''}

  <!-- Triângulo Real (ponteiro) -->
  <path d="{tri_path}" fill="#1F2937" filter="url(#triShadow)" />

  <!-- Tooltip do Real -->
  <rect x="{tip_left}" y="{bar_y - 26}" width="{tip_w}" height="24"
        rx="4" ry="4" fill="#1F2937" filter="url(#tooltipShadow)" />
  <text x="{tip_left + tip_w/2}" y="{bar_y - 26 + 16}"
        text-anchor="middle" font-size="12"
        font-weight="600" fill="white">
    {current_text_display}
  </text>



</svg>
"""

    full_html = f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
    }}
    svg {{
      width: 100%;
      height: 100%;
      display: block;
    }}
  </style>
</head>
<body>
  {svg_doc}
</body>
</html>
"""
    return full_html

# =============================================================================
# CÁLCULO ESPECÍFICO: PROGRESSO "MENOR" (manter se precisar)
# =============================================================================
def calcular_progresso(valor_atual, meta, tipo="maior"):
    if tipo == "maior":
        if meta <= 0:
            return 100.0 if valor_atual >= 0 else 0.0
        progress = (valor_atual / meta) * 100
        if progress < 0:
            progress = 0
        if progress > 100:
            progress = 100
        return progress
    else:
        # 'menor'
        if valor_atual <= meta:
            return 100.0
        else:
            if meta <= 0:
                return 0.0
            progress = 100 - ((valor_atual - meta) / meta) * 100
            if progress < 0:
                progress = 0
            if progress > 100:
                progress = 100
            return progress

alert_atualiza = html.Div()

def expandable_card(header_content, children_content, card_id):
    """
    Cria um card expansível com uma seta para expansão/retração,
    redesenhado com um visual mais premium e consistente.
    Restaura a cor areia original para os inner cards.
    
    Args:
        header_content: Conteúdo do cabeçalho do card
        children_content: Conteúdo que será mostrado quando o card for expandido
        card_id: ID único para o card
    
    Returns:
        componente Dash que representa o card expansível
    """
    from dash import html
    import dash_bootstrap_components as dbc
    
    # Cores originais do tema
    sand_color = "#F5EFE6"  # Cor areia restaurada
    
    arrow_id = {"type": "expand-arrow", "index": card_id}
    card_arrow_id = {"type": "card-arrow", "index": card_id}
    collapse_id = {"type": "collapse-card", "index": card_id}

    arrow_div = html.Div(
        html.I(
            className="fas fa-chevron-right",
            id=arrow_id,
            style={
                "color": "#64748B",
                "fontSize": "1.2rem",
                "transition": "transform 0.2s ease-in-out, color 0.2s ease",
                "marginRight": "1rem",
                "opacity": "0.85",
                "filter": "drop-shadow(0 1px 1px rgba(0,0,0,0.05))"
            }
        ),
        style={"paddingTop": "0.25rem"}
    )
    content_div = html.Div(header_content if isinstance(header_content, list) else [header_content], style={"flex": 1})
    header_with_arrow = html.Div([arrow_div, content_div], style={"display": "flex", "alignItems": "center"})

    main_card = html.Div(
        [
            html.Div(
                header_with_arrow, 
                className="inner-card", 
                style={
                    "padding": "1.5rem",
                    "borderRadius": "0.65rem",
                    "backgroundColor": sand_color,  # Restaurado para areia
                    "boxShadow": "inset 0 1px 2px rgba(0,0,0,0.02)"
                }
            )
        ],
        id=card_arrow_id,
        n_clicks=0,
        className="outer-card",
        style={
            "marginBottom": "2rem",
            "marginRight": "0.5rem",
            "padding": "1.2rem",  # Aumentado de 0.8rem para 1.2rem para ter faixa branca maior
            "borderRadius": "0.75rem",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)",
            "transition": "all 0.3s ease",
            "border": "1px solid rgba(229,231,235,0.8)",
            "backgroundColor": "#FFFFFF"  # Garantindo que o fundo externo seja branco
        }
    )
    return html.Div([
        main_card,
        dbc.Collapse(children_content, id=collapse_id, is_open=False)
    ])

def objective_card(title, progress_value, progress_color, financial_text, card_id, sub_objectives=None):
    """
    Versão corrigida do objective_card que preserva a formatação monetária,
    com cores mais premium alinhadas com os gráficos SVG.
    Adiciona um tom especial de verde para quando o progresso atinge 100%.
    Restaura a cor areia original para os inner cards.
    """
    import dash_bootstrap_components as dbc
    from dash import html

    sub_objectives = sub_objectives or []
    
    # Cores originais do tema
    sand_color = "#F5EFE6"  # Cor areia restaurada
    
    # Paleta de cores premium alinhada com as cores dos SVGs
    status_colors = {
        "success": {
            "bg": "#ECFDF5",  # Verde mint muito claro
            "text": "#047857", # Verde esmeralda profundo
            "progress": {
                "bg": "linear-gradient(90deg, #10B981 0%, #059669 100%)",
                "border": "#047857"
            }
        },
        "completed": {  # Novo estado para 100% completo
            "bg": "#DCFCE7",  # Verde mais vivo para destaque
            "text": "#166534",  # Verde escuro mais profundo
            "progress": {
                "bg": "linear-gradient(90deg, #22C55E 0%, #16A34A 100%)",
                "border": "#166534"
            }
        },
        "warning": {
            "bg": "#FFFBEB",  # Amarelo âmbar muito claro
            "text": "#B45309",  # Âmbar profundo
            "progress": {
                "bg": "linear-gradient(90deg, #F59E0B 0%, #D97706 100%)",
                "border": "#B45309"
            }
        },
        "danger": {
            "bg": "#FEF2F2",  # Vermelho muito claro
            "text": "#B91C1C",  # Vermelho premium escuro
            "progress": {
                "bg": "linear-gradient(90deg, #EF4444 0%, #DC2626 100%)",
                "border": "#B91C1C"
            }
        }
    }
    
    # Lógica para selecionar a cor correta
    if progress_value >= 100:
        c = status_colors.get("completed", status_colors["success"])
    else:
        c = status_colors.get(progress_color, status_colors["danger"])

    # Dividir o texto financeiro em valores atual e meta
    try:
        # Dividimos apenas com / mas mantemos a formatação original
        if '/' in financial_text:
            current_raw, target_raw = financial_text.split('/')
            current_val = current_raw.strip()
            target_val = target_raw.strip()
        else:
            # Caso não tenha divisão, usar o texto completo como valor atual
            current_val = financial_text
            target_val = ""
    except:
        current_val, target_val = "0", "0"

    header_content = html.Div([
        html.Div([
            html.H4(
                title,
                style={"fontSize": "1.1rem", "fontWeight": "600", "color": "#1F2937", "marginBottom": "0"}
            ),
            html.I(
                className=f"fas fa-trending-{'up' if progress_value >= 50 else 'down'}",
                style={"color": c["text"], "marginLeft": "0.4rem"}
            )
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "0.6rem"}),

        # Barra de progresso estilizada com gradiente
        html.Div(
            className="progress",
            style={
                "height": "1rem", 
                "marginBottom": "1rem",
                "borderRadius": "9999px",
                "boxShadow": "inset 0 1px 2px rgba(0,0,0,0.1)",
                "backgroundColor": "rgba(107,114,128,0.2)",
                "overflow": "hidden"
            },
            children=[
                html.Div(
                    className="progress-bar",
                    style={
                        "width": f"{progress_value}%",
                        "background": c["progress"]["bg"],
                        "borderRadius": "9999px",
                        "transition": "width 0.6s ease-in-out, background 0.3s ease",
                        "boxShadow": f"0 1px 2px rgba(0,0,0,0.15)"
                    }
                )
            ]
        ),

        # Linha com os valores financeiros formatados e o percentual de progresso
        html.Div([
            html.Div([
                html.Strong(f"{current_val}", style={"marginRight": "4px", "color": "#374151"}),
                html.Span(f"/ {target_val}", style={"color": "#6B7280"})
            ]),
            html.Span(
                f"{progress_value:.1f}%",
                style={
                    "backgroundColor": c["bg"],
                    "color": c["text"],
                    "padding": "0.25rem 0.7rem",
                    "borderRadius": "9999px",
                    "fontSize": "0.82rem",
                    "fontWeight": "600",
                    "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.06)",
                    "border": f"1px solid rgba({int(c['text'][1:3], 16)},{int(c['text'][3:5], 16)},{int(c['text'][5:7], 16)},0.1)",
                    "letterSpacing": "0.01em"
                }
            )
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"})
    ])

    # Caso tenha sub-objetivos, criamos um card expansível
    from dash import html
    from dash_bootstrap_components import Collapse

    if sub_objectives:
        children_content = html.Div(
            [sub_objective_card(**sub_obj) for sub_obj in sub_objectives],
            style={"marginTop": "0.6rem", "marginLeft": "3rem"}
        )
        outer = expandable_card(header_content, children_content, card_id)
    else:
        # Card simples com estilo premium
        outer = html.Div(
            html.Div(header_content, 
                   className="inner-card", 
                   style={
                       "padding": "1.5rem", 
                       "borderRadius": "0.65rem",
                       "backgroundColor": sand_color,  # Restaurado para areia
                       "boxShadow": "inset 0 1px 2px rgba(0,0,0,0.02)"
                   }),
            className="outer-card",
            style={
                "marginBottom": "2rem",
                "marginRight": "0.5rem",
                "padding": "1.2rem",  # Aumentado de 0.8rem para 1.2rem para ter faixa branca maior
                "borderRadius": "0.75rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)",
                "transition": "all 0.3s ease",
                "border": "1px solid rgba(229,231,235,0.8)",
                "backgroundColor": "#FFFFFF"  # Garantindo que o fundo externo seja branco
            }
        )

    return html.Div([outer], id=card_id)

def sub_objective_card(
    title,
    progress_value,
    progress_color,
    financial_text,
    child_sub_objectives=None,
    card_id=None,
    use_svg=False,
    target_value=100,
    target_type='maior',
    kpi_name=None,
    progress_percent=None
):
    """
    Versão otimizada do card de sub-objetivo com cores premium
    para melhor alinhamento visual com os gráficos SVG.
    Adiciona um tom especial de verde para quando o progresso atinge 100%.
    Restaura a cor areia original para os inner cards.
    """
    import uuid
    from dash import html
    import dash_bootstrap_components as dbc

    if card_id is None:
        card_id = str(uuid.uuid4())
        
    # Cores originais do tema
    sand_color = "#F5EFE6"  # Cor areia restaurada

    # Paleta de cores premium alinhada com as cores dos SVGs
    status_colors = {
        "success": {
            "bg": "#ECFDF5",  # Verde mint muito claro
            "text": "#047857", # Verde esmeralda profundo
            "progress": {
                "bg": "linear-gradient(90deg, #10B981 0%, #059669 100%)",
                "border": "#047857"
            }
        },
        "completed": {  # Novo estado para 100% completo
            "bg": "#DCFCE7",  # Verde mais vivo para destaque
            "text": "#166534",  # Verde escuro mais profundo
            "progress": {
                "bg": "linear-gradient(90deg, #22C55E 0%, #16A34A 100%)",
                "border": "#166534"
            }
        },
        "warning": {
            "bg": "#FFFBEB",  # Amarelo âmbar muito claro
            "text": "#B45309",  # Âmbar profundo
            "progress": {
                "bg": "linear-gradient(90deg, #F59E0B 0%, #D97706 100%)",
                "border": "#B45309"
            }
        },
        "danger": {
            "bg": "#FEF2F2",  # Vermelho muito claro
            "text": "#B91C1C",  # Vermelho premium escuro
            "progress": {
                "bg": "linear-gradient(90deg, #EF4444 0%, #DC2626 100%)",
                "border": "#B91C1C"
            }
        }
    }
    
    # Lógica para selecionar a cor correta
    if progress_value >= 100:
        c = status_colors.get("completed", status_colors["success"])
    else:
        c = status_colors.get(progress_color, status_colors["danger"])

    # Inicializar header_children aqui para evitar o erro
    header_children = []

    # Se for use_svg, usamos o create_status_svg otimizado
    if use_svg:
        # Manter a lógica original do código mas usando o layout otimizado
        try:
            cv_float = float(progress_value)
        except:
            cv_float = 0.0
        
        # Importante: usar a meta correta convertendo para float
        try:
            # Garantir que target_value seja um número
            if isinstance(target_value, str):
                # Remover possíveis símbolos e converter para float
                tv_float = float(target_value.replace('%', '').replace('R$', '').replace(',', '.').strip())
            else:
                tv_float = float(target_value)
        except:
            # Valor padrão seguro baseado no tipo de meta
            if target_type == 'menor':
                tv_float = 5.0 if "Churn" in kpi_name or "InadimplenciaReal" in kpi_name else 10.0
            else:
                tv_float = 100.0
        
        # Log para debug de metas
        kpi_display = kpi_name or "Indicador"
        print(f"[SVG Debug] {kpi_display}: valor atual = {cv_float}, meta = {tv_float}, tipo = {target_type}")

        # Cores para o indicador de progresso baseado no valor
        if progress_percent is not None:
            if progress_percent >= 100:
                progress_bg = status_colors["completed"]["bg"]
                progress_text = status_colors["completed"]["text"]
            elif progress_percent >= 70:
                progress_bg = status_colors["success"]["bg"]
                progress_text = status_colors["success"]["text"]
            elif progress_percent >= 40:
                progress_bg = status_colors["warning"]["bg"]
                progress_text = status_colors["warning"]["text"]
            else:
                progress_bg = status_colors["danger"]["bg"]
                progress_text = status_colors["danger"]["text"]
        else:
            progress_bg = c["bg"]
            progress_text = c["text"]

        # Título com o progresso percentual à direita (se fornecido)
        header_top = html.Div(
            [
                html.H6(
                    title,
                    style={
                        "fontSize": "0.95rem",
                        "fontWeight": "600",
                        "marginTop": "0.5rem",
                        "marginBottom": "0.8rem",
                        "marginLeft": "0.5rem",
                        "color": "#374151",
                        "flex": "1"
                    }
                ),
                # Indicador de progresso, se fornecido
                html.Span(
                    f"{progress_percent:.1f}%" if progress_percent is not None else "",
                    style={
                        "backgroundColor": progress_bg,
                        "color": progress_text,
                        "padding": "0.25rem 0.7rem",
                        "borderRadius": "9999px",
                        "fontSize": "0.82rem",
                        "fontWeight": "600",
                        "display": "inline-block" if progress_percent is not None else "none",
                        "marginRight": "0.5rem",
                        "marginTop": "0.5rem",
                        "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.06)",
                        "border": f"1px solid rgba({int(progress_text[1:3], 16)},{int(progress_text[3:5], 16)},{int(progress_text[5:7], 16)},0.1)",
                        "letterSpacing": "0.01em"
                    }
                )
            ],
            style={
                "display": "flex", 
                "justifyContent": "space-between", 
                "alignItems": "center"
            }
        )
        
        header_children = [header_top]
        
        # Usar o kpi_name para mostrar no gráfico, não o título
        kpi_display_name = kpi_name or "Net Revenue Retention"
        
        # Tentar importar zonas_de_controle
        try:
            # Tentar carregar de utils primeiro
            # Remover a linha abaixo
            # from .utils import carregar_kpi_descriptions 
            kpi_descriptions = carregar_kpi_descriptions()
        except:
            try:
                # Se não encontrar, tentar importar do módulo controles
                # Remover a linha abaixo
                # from .controles import zonas_de_controle
                kpi_descriptions = zonas_de_controle
            except:
                # Fallback para um dicionário vazio
                kpi_descriptions = {}
        
        # Criar SVG - Passando o force_negative_behavior baseado no target_type
        svg_doc = create_status_svg(
            current_value_percent=cv_float,
            meta_value_percent=tv_float,
            kpi_name=kpi_display_name,
            kpi_descriptions=kpi_descriptions,
            margin_lower=5.0,
            margin_upper=5.0,
            force_negative_behavior=(target_type == 'menor')
        )
        
        # Adicionar iframe com SVG
        header_children.append(
            html.Iframe(
                srcDoc=svg_doc,
                style={
                    "width": "100%",
                    "height": "120px",
                    "border": "none",
                    "overflow": "hidden",
                    "marginTop": "0",
                    "marginBottom": "0.5rem"
                }
            )
        )
        
        header_content = html.Div(header_children)
    else:
        # Para cards sem SVG, criamos um visual premium
        header_children = [
            html.H6(
                title,
                style={
                    "fontSize": "0.95rem",
                    "fontWeight": "600",
                    "marginTop": "0",
                    "marginBottom": "0.8rem",
                    "color": "#374151",
                    "letterSpacing": "0.01em"
                }
            )
        ]
        
        # Para cards sem SVG, manter o código original com cores aprimoradas
        try:
            if '/' in financial_text:
                current_raw, goal_raw = financial_text.split('/')
                current_val = current_raw.strip()  # Mantém R$ se presente
                meta_val = goal_raw.strip()  # Mantém R$ se presente
            else:
                current_val, meta_val = financial_text, ""
        except:
            current_val, meta_val = "0", "0"

        # Barra de progresso estilizada com gradiente
        header_children.append(
            html.Div(
                className="progress",
                style={
                    "height": "16px", 
                    "marginBottom": "0.8rem",
                    "borderRadius": "9999px",
                    "boxShadow": "inset 0 1px 2px rgba(0,0,0,0.1)",
                    "backgroundColor": "rgba(107,114,128,0.2)",
                    "overflow": "hidden"
                },
                children=[
                    html.Div(
                        className="progress-bar",
                        style={
                            "width": f"{progress_value}%",
                            "background": c["progress"]["bg"],
                            "borderRadius": "9999px",
                            "transition": "width 0.6s ease-in-out, background 0.3s ease",
                            "boxShadow": f"0 1px 2px rgba(0,0,0,0.15)"
                        }
                    )
                ]
            )
        )

        header_children.append(
            html.Div(
                [
                    html.Div([
                        html.Strong(f"{current_val}", style={"marginRight": "6px", "color": "#374151"}),
                        html.Span(f"/ {meta_val}", style={"color": "#6B7280"})
                    ]),
                    html.Span(
                        f"{progress_value:.1f}%",
                        style={
                            "backgroundColor": c["bg"],
                            "color": c["text"],
                            "padding": "0.25rem 0.7rem",
                            "borderRadius": "9999px",
                            "fontSize": "0.82rem",
                            "fontWeight": "600",
                            "boxShadow": "0 1px 2px rgba(0, 0, 0, 0.06)",
                            "border": f"1px solid rgba({int(c['text'][1:3], 16)},{int(c['text'][3:5], 16)},{int(c['text'][5:7], 16)},0.1)",
                            "letterSpacing": "0.01em"
                        }
                    )
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}
            )
        )

        header_content = html.Div(header_children)

    # Manter a lógica original para cards com sub-sub-objetivos
    if child_sub_objectives:
        from dash_bootstrap_components import Collapse
        children_content = html.Div(
            [sub_objective_card(**child) for child in child_sub_objectives],
            style={"marginLeft": "2rem", "marginTop": "0.5rem"}
        )
        from dash import html
        return html.Div(
            expandable_card(header_content, children_content, card_id),
            className="sub-objective-connector"
        )
    else:
        # Card simples com visual premium
        from dash import html
        inner_padding = "1rem" if use_svg else "1rem"
        inner = html.Div(
            header_content, 
            className="inner-card", 
            style={
                "padding": inner_padding, 
                "margin": "8px",
                "borderRadius": "0.65rem",
                "backgroundColor": sand_color,  # Restaurado para areia
                "boxShadow": "inset 0 1px 2px rgba(0,0,0,0.02)"
            }
        )
        outer = html.Div(
            inner,
            className="outer-card",
            style={
                "marginBottom": "2rem",
                "marginRight": "0.5rem",
                "padding": "1.2rem",  # Aumentado de 0.8rem para 1.2rem para ter faixa branca maior
                "borderRadius": "0.75rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)",
                "transition": "all 0.3s ease",
                "border": "1px solid rgba(229,231,235,0.8)",
                "backgroundColor": "#FFFFFF"  # Garantindo que o fundo externo seja branco
            }
        )
        return html.Div(outer, className="sub-objective-connector")

# =============================================================================
# Layout principal
# =============================================================================

objective_1_placeholder = dbc.Row(
    dbc.Col(html.Div(id="retomar-crescimento-card"), width=12),
    className="g-2"
)

objective_2 = dbc.Row(
    dbc.Col(
        objective_card(
            title="Expandir e Melhorar nossos Produtos",
            progress_value=30,
            progress_color="warning",
            financial_text="R$ 3M / R$ 10M",
            card_id="obj-2",
            sub_objectives=[
                {
                    "title": "Lançar nova plataforma",
                    "progress_value": 40,
                    "progress_color": "warning",
                    "financial_text": "R$ 1.2M / R$ 3M"
                },
                {
                    "title": "Implementar novas funcionalidades",
                    "progress_value": 20,
                    "progress_color": "danger",
                    "financial_text": "R$ 1.8M / R$ 7M"
                }
            ]
        ),
        width=12
    ),
    className="g-2"
)

objective_3 = dbc.Row(
    dbc.Col(
        # Será preenchido pelo callback update_obj3
        objective_card(
            title="Ser uma empresa enxuta e eficiente",
            progress_value=50,
            progress_color="danger",
            financial_text="R$ 2M / R$ 4M",
            card_id="obj-3"
        ),
        width=12
    ),
    className="g-2"
)

objective_4 = dbc.Row(
    dbc.Col(
        # Será preenchido pelo callback update_obj4 (logo abaixo).
        objective_card(
            title="Melhorar a reputação da eshows",
            progress_value=0,
            progress_color="danger",
            financial_text="0% / 100%",
            card_id="obj-4"
        ),
        width=12
    ),
    className="g-2"
)

objectives_section = html.Div([
    objective_1_placeholder,
    objective_2,
    objective_3,
    objective_4
])

periodo_mes_row = dbc.Row([
    dbc.Col(
        [
            html.Div("Período:", style={"marginBottom": "4px"}),
            dcc.Dropdown(
                id="okrs-periodo-dropdown",
                options=[
                    {"label": "1° Trimestre", "value": "1° Trimestre"},
                    {"label": "2° Trimestre", "value": "2° Trimestre"},
                    {"label": "3° Trimestre", "value": "3° Trimestre"},
                    {"label": "4° Trimestre", "value": "4° Trimestre"},
                    {"label": "Mês Aberto",   "value": "Mês Aberto"},
                    {"label": "Ano Completo", "value": "Ano Completo"},
                    {"label": "Período Personalizado", "value": "custom-range"}  # Usamos "custom-range" para compatibilidade
                ],
                value="1° Trimestre",
                clearable=False,
                style={"borderRadius": "4px", "width": "180px"}
            )
        ],
        width="auto"
    ),
    dbc.Col(
        [
            html.Div("Mês:", style={"marginBottom": "4px"}),
            dcc.Dropdown(
                id="okrs-mes-dropdown",
                options=[
                    {"label": "Janeiro",   "value": 1},
                    {"label": "Fevereiro", "value": 2},
                    {"label": "Março",     "value": 3},
                    {"label": "Abril",     "value": 4},
                    {"label": "Maio",      "value": 5},
                    {"label": "Junho",     "value": 6},
                    {"label": "Julho",     "value": 7},
                    {"label": "Agosto",    "value": 8},
                    {"label": "Setembro",  "value": 9},
                    {"label": "Outubro",   "value": 10},
                    {"label": "Novembro",  "value": 11},
                    {"label": "Dezembro",  "value": 12},
                ],
                value=datetime.now().month,
                clearable=False,
                style={"borderRadius": "4px", "width": "150px"}
            )
        ],
        id="okrs-mes-dropdown-container",
        width="auto",
        style={"display": "none"}
    ),
    # Dropdowns para período personalizado
    dbc.Col(
        [
            html.Div("De:", style={"marginBottom": "4px"}),
            dcc.Dropdown(
                id="okrs-mes-inicial-dropdown",
                options=[
                    {"label": mes_nome(1),  "value": 1},
                    {"label": mes_nome(2),  "value": 2},
                    {"label": mes_nome(3),  "value": 3},
                    {"label": mes_nome(4),  "value": 4},
                    {"label": mes_nome(5),  "value": 5},
                    {"label": mes_nome(6),  "value": 6},
                    {"label": mes_nome(7),  "value": 7},
                    {"label": mes_nome(8),  "value": 8},
                    {"label": mes_nome(9),  "value": 9},
                    {"label": mes_nome(10), "value": 10},
                    {"label": mes_nome(11), "value": 11},
                    {"label": mes_nome(12), "value": 12},
                ],
                value=1,
                clearable=False,
                style={"borderRadius": "4px", "width": "150px"}
            )
        ],
        id="okrs-mes-inicial-container",
        width="auto",
        style={"display": "none"}
    ),
    dbc.Col(
        [
            html.Div("Até:", style={"marginBottom": "4px"}),
            dcc.Dropdown(
                id="okrs-mes-final-dropdown",
                options=[
                    {"label": mes_nome(1),  "value": 1},
                    {"label": mes_nome(2),  "value": 2},
                    {"label": mes_nome(3),  "value": 3},
                    {"label": mes_nome(4),  "value": 4},
                    {"label": mes_nome(5),  "value": 5},
                    {"label": mes_nome(6),  "value": 6},
                    {"label": mes_nome(7),  "value": 7},
                    {"label": mes_nome(8),  "value": 8},
                    {"label": mes_nome(9),  "value": 9},
                    {"label": mes_nome(10), "value": 10},
                    {"label": mes_nome(11), "value": 11},
                    {"label": mes_nome(12), "value": 12},
                ],
                value=datetime.now().month,
                clearable=False,
                style={"borderRadius": "4px", "width": "150px"}
            )
        ],
        id="okrs-mes-final-container",
        width="auto",
        style={"display": "none"}
    ),
],
justify="start",
align="end",
className="g-3",
style={"marginTop": "40px", "marginBottom": "20px"}
)

okrs_layout = dbc.Container(
    [
        # dcc.Download(id="download-excluidos"),
        dbc.Row([
            dbc.Col([
                html.H1(
                    "OKRs eshows",
                    style={
                        "fontFamily": "Inter",
                        "fontWeight": "700",
                        "fontSize": "46px",
                        "color": "#4A4A4A",
                        "marginBottom": "0",
                        "marginTop": "0"
                    }
                ),
                html.H2(
                    "Objetivos e Resultados Chave",
                    style={
                        "fontFamily": "Inter",
                        "fontWeight": "500",
                        "fontSize": "28px",
                        "color": "#4A4A4A",
                        "marginBottom": "5px",
                        "marginTop": "0"
                    }
                ),
                periodo_mes_row
            ], md=8),
            dbc.Col(
                html.Div(
                    html.Iframe(
                        id="meta-gauge-wrapper",
                        style={"width": "400px", "height": "300px", "border": "none", "overflow": "hidden", "background": "transparent"}
                    ),
                    style={"textAlign": "right","position": "relative", "top": "25px"}
                ),
                md=4,
                style={"marginBottom": "-90px"}
            )
        ], style={"marginBottom": "0"}),

        html.Div([
            html.H3(
                "Objetivos Principais",
                style={"marginTop": "0", "marginBottom": "5px", "fontSize": "1.25rem", "fontWeight": "600"}
            ),
            html.Div(objectives_section, style={"marginTop": "1.5rem"})
        ])
    ],
    fluid=True,
    style={"padding": "15px"}
)

# -----------------------------------------------------------------------------
# 1)  FUNÇÃO AUXILIAR  – parse seguro de números (usa pandas)
# -----------------------------------------------------------------------------
def _parse_to_float(col):
    """
    Converte uma Series para float de forma resiliente:
    • troca vírgula -> ponto
    • remove % e espaços
    • usa pd.to_numeric(errors='coerce') para pegar NaN em strings como 'Ano'
    """
    return (
        col.astype(str)
           .str.replace(",", ".", regex=False)
           .str.replace("%", "", regex=False)
           .str.strip()
           .pipe(pd.to_numeric, errors="coerce")
    )

# ----------------------------------------------------------------------------- 
# FUNÇÃO PRINCIPAL – ler_todas_as_metas (versão robusta) 
# ----------------------------------------------------------------------------- 
def ler_todas_as_metas(ano: int,
                       periodo: str,
                       mes: int | None = None,
                       custom_range: tuple | None = None) -> dict:
    """
    Lê Metas.xlsx, filtra o período e devolve {Meta: valor}.
    – Metas percentuais são convertidas p/ fração (ex.: 10 % → 0.10)  
    – Metas de volume ("NovosClientes" etc.) são SOMA; demais recebem MÉDIA.  
    – Sempre devolve todas as chaves esperadas → evita KeyError em outros módulos.
    """
    df_metas = carregar_metas()
    if df_metas is None or df_metas.empty:
        df_periodo = pd.DataFrame()            # força fallback
    else:
        df_periodo = filtrar_periodo_principal(df_metas, ano,
                                               periodo, mes, custom_range)

    # ---------- Coluna do Excel → chave interna ----------
    col_map: dict[str, str] = {
        "Novos Clientes": "NovosClientes",
        "Key Account": "KeyAccount",
        "Outros Clientes": "OutrosClientes",
        "Plataforma": "Plataforma",
        "Fintech": "Fintech",
        "NRR": "NRR",
        "Churn": "Churn",
        "TurnOver": "TurnOver",
        "Lucratividade": "Lucratividade",
        "Crescimento Sustentável": "CrescimentoSustentavel",
        "Palcos Vazios": "PalcosVazios",
        "InadimplenciaReal": "InadimplenciaReal",
        "Estabilidade": "Estabilidade",
        "Ef. Atendimento": "EficienciaAtendimento",
        "AutonomiaUsuario": "AutonomiaUsuario",
        "Perdas Operacionais": "PerdasOperacionais",
        "ReceitaPorColaborador": "ReceitaPorColaborador",
        "LTV/CAC": "LtvCac",
        "NPS Artistas": "NPSArtistas",
        "NPS Equipe": "NPSEquipe",
    }

    # metas que são SOMA (o resto recebe média)
    keys_to_sum = {
        "NovosClientes", "KeyAccount", "OutrosClientes",
        "Plataforma", "Fintech", "PalcosVazios"
    }

    # metas percentuais → converter para fração
    percent_keys = {
        "NRR", "Churn", "TurnOver", "Lucratividade",
        "CrescimentoSustentavel", "InadimplenciaReal",
        "Estabilidade", "EficienciaAtendimento", "AutonomiaUsuario"
    }

    # ---------- dicionário-base (todos os campos) ----------
    metas_default = {
        "NovosClientes": 0.0, "KeyAccount": 0.0, "OutrosClientes": 0.0,
        "Plataforma": 0.0, "Fintech": 0.0,
        # valores default percentuais já em FRAÇÃO
        "NRR": 0.10, "Churn": 0.08, "TurnOver": 0.10, "Lucratividade": 0.10,
        "CrescimentoSustentavel": 0.05, "PalcosVazios": 0.0,
        "InadimplenciaReal": 0.05, "Estabilidade": 0.90,
        "EficienciaAtendimento": 0.80, "AutonomiaUsuario": 0.30,
        "PerdasOperacionais": 0.15, "ReceitaPorColaborador": 12_500.0,
        "LtvCac": 2.0, "NPSArtistas": 30.0, "NPSEquipe": 70.0
    }

    # ---------- se não há linhas no período, retorna defaults ----------
    if df_periodo.empty:
        return metas_default.copy()

    # ---------- loop de cálculo ----------
    metas_calc = metas_default.copy()

    for col_excel, key_meta in col_map.items():
        if col_excel not in df_periodo.columns:
            continue

        serie = _parse_to_float(df_periodo[col_excel]).dropna()
        if serie.empty:
            continue

        val = serie.sum() if key_meta in keys_to_sum else serie.mean()
        if key_meta in percent_keys:
            val = val / 100.0  # converte para fração

        # Correções específicas de março / 1º T
        if (mes == 3 or periodo == "1° Trimestre" or
            (periodo == "custom-range" and custom_range and
             custom_range[0].month == 1 and custom_range[1].month == 3)):
            if key_meta == "Lucratividade" and abs(val - 0.10) < 1e-3:
                val = 0.15
            if key_meta == "InadimplenciaReal" and abs(val - 0.03) < 1e-3:
                val = 0.08

        metas_calc[key_meta] = val

    return metas_calc

# =============================================================================
# Callbacks
# =============================================================================

def register_okrs_callbacks(app):
    """
    Registra todos os callbacks relacionados à página de OKRs no app principal.
    """

    @app.callback(
        [Output("okrs-mes-dropdown-container", "style"),
         Output("okrs-mes-inicial-container", "style"),
         Output("okrs-mes-final-container", "style")],
        Input("okrs-periodo-dropdown", "value")
    )
    def exibir_mes_dropdown(periodo_value):
        mes_aberto_style = {"display": "block"} if periodo_value == "Mês Aberto" else {"display": "none"}
        periodo_personalizado_style = {"display": "block"} if periodo_value == "custom-range" else {"display": "none"}
        
        return mes_aberto_style, periodo_personalizado_style, periodo_personalizado_style

    @app.callback(
        Output("meta-gauge-wrapper", "srcDoc"),
        [Input("okrs-periodo-dropdown", "value"),
         Input("okrs-mes-dropdown", "value"),
         Input("okrs-mes-inicial-dropdown", "value"),
         Input("okrs-mes-final-dropdown", "value")]
    )
    def update_gauge(periodo, mes_selecionado, mes_inicial, mes_final):
        import math
        # Criar custom_range se necessário
        custom_range = None
        ano = 2025  # Ou outro ano relevante para sua aplicação
        if periodo == "custom-range" and mes_inicial and mes_final:
            custom_range = criar_custom_range(ano, mes_inicial, mes_final)

        # 1) Calcula [0..100]
        gauge_value = calcular_progresso_geral(periodo, mes_selecionado, custom_range)
        gv = max(0, min(100, gauge_value))

        # 2) Cores para o degradê
        red = "#E53935"          # Vermelho (0-20%)
        orange = "#FF7043"       # Laranja (20-40%) 
        yellow = "#FFD54F"       # Amarelo (40-60%)
        light_green = "#7CB342"  # Verde claro (60-80%)
        dark_green = "#2E7D32"   # Verde escuro (80-100%)

        # Cor do badge baseada no valor atual - Paleta mais sofisticada
        if gv <= 20:
            value_color = red
            badge_gradient_start = "#FF5252"
            badge_gradient_end = "#D32F2F"
            badge_accent = "#FFCDD2"  # Tom mais claro para acento
            text_color = "rgba(255,255,255,0.95)"
        elif gv <= 40:
            value_color = orange
            badge_gradient_start = "#FFAB91"
            badge_gradient_end = "#E64A19"
            badge_accent = "#FFCCBC"  # Tom mais claro para acento
            text_color = "rgba(255,255,255,0.95)"
        elif gv <= 60:
            value_color = yellow
            badge_gradient_start = "#FFF9C4"
            badge_gradient_end = "#FFC107"
            badge_accent = "#FFFDE7"  # Tom mais claro para acento
            text_color = "rgba(51,51,51,0.9)"
        elif gv <= 80:
            value_color = light_green
            badge_gradient_start = "#C5E1A5"
            badge_gradient_end = "#558B2F"
            badge_accent = "#F1F8E9"  # Tom mais claro para acento
            text_color = "rgba(51,51,51,0.9)"
        else:
            value_color = dark_green
            badge_gradient_start = "#81C784"
            badge_gradient_end = "#1B5E20"
            badge_accent = "#E8F5E9"  # Tom mais claro para acento
            text_color = "rgba(255,255,255,0.95)"

        # 3) Dimensões
        svg_w = 400
        svg_h = 300
        center_x = svg_w / 2
        center_y = 210  # Ajustado para centralizar melhor
        radius = 160
        stroke_width = 30

        # 4) Convertemos gv em [0..180], onde 0 = esquerda e 180 = direita.
        angle_deg = gv * 180.0 / 100.0

        # 5) Calculamos as coordenadas para o "ponto atual" do arco
        angle_rad = math.radians(180 - angle_deg)
        pointer_x = center_x + radius * math.cos(angle_rad)
        pointer_y = center_y - radius * math.sin(angle_rad)

        # 6) Posição do badge (rótulo)
        label_radius = radius - 10  # Posicionado sobre o arco colorido
        label_x = center_x + label_radius * math.cos(angle_rad)
        label_y = center_y - label_radius * math.sin(angle_rad)

        # 7) Arco de FUNDO, de 0° (esquerda) até 180° (direita)
        start_x = center_x - radius
        start_y = center_y
        end_x = center_x + radius
        end_y = center_y

        arc_fundo = f"M{start_x},{start_y} A{radius},{radius} 0 0,1 {end_x},{end_y}"

        # 8) Arco colorido de 0° até angle_deg
        arc_color = f"M{start_x},{start_y} A{radius},{radius} 0 0,1 {pointer_x},{pointer_y}"

        # 9) Agora definimos o gradiente baseado no valor atual
        gradient_stops = []
        
        # Sempre começa com vermelho
        gradient_stops.append(f'<stop offset="0%" stop-color="{red}"/>')
        
        # Adiciona cores intermediárias baseadas no progresso atual
        if gv > 20:
            pos_orange = min(20/gv * 100, 50)
            gradient_stops.append(f'<stop offset="{pos_orange}%" stop-color="{orange}"/>')
            
        if gv > 40:
            pos_yellow = min(40/gv * 100, 75)
            gradient_stops.append(f'<stop offset="{pos_yellow}%" stop-color="{yellow}"/>')
            
        if gv > 60:
            pos_light_green = min(60/gv * 100, 90)
            gradient_stops.append(f'<stop offset="{pos_light_green}%" stop-color="{light_green}"/>')
            
        if gv > 80:
            gradient_stops.append(f'<stop offset="100%" stop-color="{dark_green}"/>')
        else:
            gradient_stops.append(f'<stop offset="100%" stop-color="{value_color}"/>')

        gradient_stops_html = "".join(gradient_stops)

        # 10) HTML final com melhorias visuais premium
        gauge_script = f"""
    <html>
    <head><style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&family=Inter:wght@300;400;500&display=swap');
    html, body {{
    margin:0; padding:0;
    overflow:hidden;
    width:100%; height:100%;
    background:transparent;
    font-family: 'Roboto', 'Inter', sans-serif;
    }}
    </style></head>
    <body>
    <div style="position:relative;width:100%;height:100%;">
    <svg width="100%" height="100%" viewBox="0 0 {svg_w} {svg_h}">
    <defs>
        <!-- Gradiente dinâmico baseado no progresso atual -->
        <linearGradient id="gauge-gradient" x1="0%" y1="0%" x2="100%" y1="0%">
        {gradient_stops_html}
        </linearGradient>
        
        <!-- Gradiente para o ponteiro -->
        <linearGradient id="pointer-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="rgba(0,0,0,0.2)"/>
        </linearGradient>
        
        <!-- Gradiente para a base do ponteiro -->
        <radialGradient id="pointer-base-gradient" cx="50%" cy="50%" r="50%" fx="30%" fy="30%">
        <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.6"/>
        <stop offset="100%" stop-color="rgba(0,0,0,0.2)"/>
        </radialGradient>
        
        <!-- Gradiente linear mais leve para o badge -->
        <linearGradient id="badge-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="{badge_gradient_start}" stop-opacity="0.85"/>
        <stop offset="100%" stop-color="{badge_gradient_end}" stop-opacity="0.9"/>
        </linearGradient>
        
        <!-- Gradiente circular para o contorno do badge -->
        <radialGradient id="badge-border-gradient" cx="50%" cy="50%" r="50%" fx="30%" fy="30%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.9)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0.3)"/>
        </radialGradient>
        
        <!-- Gradiente de reflexo para o badge - mais delicado e radial -->
        <radialGradient id="badge-shine" cx="50%" cy="40%" r="60%" fx="50%" fy="0%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.45)"/>
        <stop offset="70%" stop-color="rgba(255,255,255,0)"/>
        </radialGradient>
        
        <!-- Gradiente para o efeito de vidro -->
        <radialGradient id="glass-effect" cx="50%" cy="30%" r="70%" fx="50%" fy="10%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.35)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0.05)"/>
        </radialGradient>
        
        <!-- Gradiente para o anel decorativo -->
        <linearGradient id="ring-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="{badge_accent}"/>
        <stop offset="100%" stop-color="{badge_gradient_end}"/>
        </linearGradient>
        
        <!-- Sombra para o arco -->
        <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
        <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="rgba(0,0,0,0.3)" flood-opacity="0.6"/>
        </filter>
        
        <!-- Sombra aprimorada para o ponteiro -->
        <filter id="pointer-shadow" x="-50%" y="-50%" width="200%" height="200%">
        <feDropShadow dx="0" dy="3" stdDeviation="2.5" flood-color="rgba(0,0,0,0.35)" flood-opacity="0.7"/>
        <feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="rgba(0,0,0,0.2)" flood-opacity="0.4"/>
        </filter>
        
        <!-- Efeito de brilho para o ponteiro -->
        <filter id="pointer-glow">
        <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur"/>
        <feComposite in="SourceGraphic" in2="blur" operator="over"/>
        </filter>
        
        <!-- Filtro para efeito de vidro translúcido -->
        <filter id="glass" x="-10%" y="-10%" width="120%" height="120%">
        <feGaussianBlur in="SourceGraphic" stdDeviation="1" result="blur"/>
        <feComposite in="SourceGraphic" in2="blur" operator="over"/>
        </filter>
        
        <!-- Sombra de texto para melhor legibilidade -->
        <filter id="text-shadow" x="-10%" y="-10%" width="120%" height="120%">
        <feDropShadow dx="0" dy="1" stdDeviation="0.3" flood-color="rgba(0,0,0,0.2)" flood-opacity="0.5"/>
        </filter>
    </defs>

    <!-- Arco de fundo (0°..180°) -->
    <path d="{arc_fundo}" fill="none" stroke="#F0F0F0"
            stroke-width="{stroke_width}" stroke-linecap="round"/>

    <!-- Arco colorido (0°..angle_deg) -->
    <path d="{arc_color}" fill="none"
            stroke="url(#gauge-gradient)"
            stroke-width="{stroke_width}"
            stroke-linecap="round"
            filter="url(#shadow)"/>
            
    <!-- Linha branca decorativa no meio do arco -->
    <path d="{arc_fundo}" fill="none" 
            stroke="rgba(255,255,255,0.5)" 
            stroke-width="2" 
            stroke-linecap="round"/>

    <!-- Ponteiro redesenhado e aprimorado -->
    <g transform="translate({center_x},{center_y}) rotate({angle_deg - 90})">
        <!-- Camada de sombra do ponteiro -->
        <path d="M-7,-2 L0,{-(radius*0.68)} L7,-2 C9,0 9,3 0,3 C-9,3 -9,0 -7,-2 Z"
            fill="rgba(0,0,0,0.2)" transform="translate(2,2)" opacity="0.6"/>
        
        <!-- Ponteiro principal com forma mais aerodinâmica -->
        <path d="M-7,-2 L0,{-(radius*0.68)} L7,-2 C9,0 9,3 0,3 C-9,3 -9,0 -7,-2 Z"
            fill="{value_color}"
            stroke="#ffffff"
            stroke-width="0.8"
            filter="url(#pointer-shadow)"/>
        
        <!-- Camada de brilho para o ponteiro -->
        <path d="M-6,-1 L0,{-(radius*0.65)} L6,-1 C7,0 7,2 0,2 C-7,2 -7,0 -6,-1 Z"
            fill="url(#pointer-gradient)"
            opacity="0.85"
            filter="url(#pointer-glow)"/>
        
        <!-- Base do ponteiro aprimorada -->
        <circle cx="0" cy="0" r="14" fill="{value_color}" stroke="#ffffff" stroke-width="1"/>
        <circle cx="0" cy="0" r="12" fill="url(#pointer-base-gradient)" opacity="0.9"/>
        <circle cx="0" cy="0" r="6" fill="#ffffff" stroke="rgba(0,0,0,0.1)" stroke-width="0.5"/>
        
        <!-- Reflexo na base para dar efeito 3D -->
        <ellipse cx="-2" cy="-2" rx="4" ry="3" fill="rgba(255,255,255,0.7)" opacity="0.7"/>
    </g>
    
    <!-- Badge circular do valor - visual ultra premium com glass effect -->
    <g transform="translate({label_x},{label_y})">
        <!-- Anel decorativo externo sutil -->
        <circle cx="0" cy="0" r="34" 
                fill="none" 
                stroke="url(#ring-gradient)" 
                stroke-width="0.8" 
                opacity="0.6"
                filter="url(#glass)"/>
                
        <!-- Anel decorativo secundário com padrão pontilhado -->
        <circle cx="0" cy="0" r="29" 
                fill="none" 
                stroke="rgba(255,255,255,0.2)" 
                stroke-width="0.5"
                stroke-dasharray="1,2"
                opacity="0.8"/>
                
        <!-- Fundo principal do badge circular com degradê mais leve -->
        <circle cx="0" cy="0" r="25"
                fill="url(#badge-gradient)" 
                stroke="rgba(255,255,255,0.5)" 
                stroke-width="0.5"/>
        
        <!-- Camada de efeito de vidro (glass effect) mantida -->
        <circle cx="0" cy="0" r="23"
                fill="url(#glass-effect)" 
                opacity="0.45"
                filter="url(#glass)"/>
        
        <!-- Valor com fonte Roboto Light -->
        <text x="0" y="6" text-anchor="middle"
            font-family="'Roboto', sans-serif" font-size="19"
            font-weight="300" letter-spacing="0.5"
            filter="url(#text-shadow)"
            fill="{text_color}">
        {gv:.0f}%
        </text>
    </g>
    </svg>
    </div>
    </body></html>
    """
        return gauge_script

    @callback(
        Output({'type': 'collapse-card', 'index': MATCH}, 'is_open'),
        Output({'type': 'expand-arrow', 'index': MATCH}, 'style'),
        Input({'type': 'card-arrow', 'index': MATCH}, 'n_clicks'),
        State({'type': 'collapse-card', 'index': MATCH}, 'is_open'),
        prevent_initial_call=True
    )
    def toggle_collapse(n_clicks, is_open):
        new_is_open = not is_open
        
        # Estilo atualizado da seta com cores mais premium
        arrow_style = {
            "color": "#4B5563" if new_is_open else "#64748B",  # Mais escuro quando expandido
            "fontSize": "1.2rem",
            "marginRight": "0.8rem",
            "transition": "transform 0.3s ease-in-out, color 0.3s ease",
            "transform": "rotate(90deg)" if new_is_open else "rotate(0deg)",
            "filter": "drop-shadow(0 1px 1px rgba(0,0,0,0.05))",
            "opacity": "1" if new_is_open else "0.85"
        }
        
        return new_is_open, arrow_style

    # =============================================================================
    # OBJETIVO 1
    # =============================================================================
    @app.callback(
    Output("retomar-crescimento-card", "children"),
    [Input("okrs-periodo-dropdown", "value"),
     Input("okrs-mes-dropdown", "value"),
     Input("okrs-mes-inicial-dropdown", "value"),
     Input("okrs-mes-final-dropdown", "value")]
    )
    def update_obj1(periodo, mes_selecionado, mes_inicial, mes_final):
        """
        Lógica "Retomar o Crescimento" adaptada para usar a função ler_todas_as_metas
        Suporta período personalizado.
        """
        # Criar custom_range se necessário
        custom_range = None
        ano = 2025
        if periodo == "custom-range" and mes_inicial and mes_final:
            custom_range = criar_custom_range(ano, mes_inicial, mes_final)
            print(f"Período personalizado: De {mes_nome(mes_inicial)} até {mes_nome(mes_final)} de {ano}")
            if custom_range:
                print(f"custom_range: {custom_range[0]} até {custom_range[1]}")

        df_eshows_completo = df_eshows
        
        # Utilizando a função ler_todas_as_metas para obter as metas
        mes = None
        if periodo == "Mês Aberto":
            mes = mes_selecionado
            
        # Obtém todas as metas em um dicionário, passando custom_range
        metas = ler_todas_as_metas(ano, periodo, mes, custom_range)
        
        # Extrai as metas específicas do objetivo 1
        meta_novos = metas["NovosClientes"]
        meta_key = metas["KeyAccount"]
        meta_outros = metas["OutrosClientes"]
        meta_plat = metas["Plataforma"]
        meta_fint = metas["Fintech"]

        meta_curadoria = meta_novos + meta_key + meta_outros
        meta_obj_principal = meta_curadoria + meta_plat + meta_fint

        ano_real = 2025
        mes_real = None
        if periodo == "Mês Aberto":
            mes_real = mes_selecionado

        # Usar custom_range na chamada para filtrar_periodo_principal
        df_periodo_eshows = filtrar_periodo_principal(df_eshows_completo, ano_real, periodo, mes_real, custom_range)

        if df_periodo_eshows.empty:
            real_novos = real_key = real_outros = real_plat = real_fint = 0.0
        else:
            COLUNAS_CURADORIA = ["Comissão B2B", "SaaS Percentual", "SaaS Mensalidade", "Notas Fiscais"]
            FINTECH_COLUNA    = "Antecipação de Cachês"

            for c in COLUNAS_CURADORIA:
                if c in df_periodo_eshows.columns:
                    df_periodo_eshows[c] = pd.to_numeric(df_periodo_eshows[c], errors='coerce').fillna(0)
            if FINTECH_COLUNA in df_periodo_eshows.columns:
                df_periodo_eshows[FINTECH_COLUNA] = pd.to_numeric(df_periodo_eshows[FINTECH_COLUNA], errors='coerce').fillna(0)

            # Ajuste da lógica para período personalizado
            if periodo == "custom-range" and custom_range:
                start_date = custom_range[0]
                df_min = df_eshows_completo.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")
                df_min["EarliestShow"] = pd.to_datetime(df_min["EarliestShow"], errors='coerce')
                novos_ids = set(df_min.loc[df_min["EarliestShow"] >= start_date, "Id da Casa"])
            elif periodo == "Mês Aberto":
                janeiro_1 = datetime(ano_real, 1, 1)
                df_min = df_eshows_completo.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow")
                df_min["EarliestShow"] = pd.to_datetime(df_min["EarliestShow"], errors='coerce')
                novos_ids = set(df_min.loc[df_min["EarliestShow"] >= janeiro_1, "Id da Casa"])
            else:
                # Passar custom_range também para filtrar_novos_palcos
                novos_ids = filtrar_novos_palcos(df_eshows_completo, ano_real, periodo, mes_real, custom_range)

            # Passar custom_range para filtrar_key_accounts se necessário
            kas_ids = filtrar_key_accounts(df_eshows_completo, ano_real)
            real_fint = df_periodo_eshows[FINTECH_COLUNA].sum() if FINTECH_COLUNA in df_periodo_eshows.columns else 0.0
            real_plat = 0.0

            df_novos = df_periodo_eshows[df_periodo_eshows["Id da Casa"].isin(novos_ids)]
            real_novos = df_novos[COLUNAS_CURADORIA].sum().sum() if not df_novos.empty else 0.0

            df_kas = df_periodo_eshows[df_periodo_eshows["Id da Casa"].isin(kas_ids)]
            df_kas = df_kas[~df_kas["Id da Casa"].isin(novos_ids)]
            real_key = df_kas[COLUNAS_CURADORIA].sum().sum() if not df_kas.empty else 0.0

            df_demais = df_periodo_eshows[
                ~df_periodo_eshows["Id da Casa"].isin(novos_ids)
                & ~df_periodo_eshows["Id da Casa"].isin(kas_ids)
            ]
            real_outros = df_demais[COLUNAS_CURADORIA].sum().sum() if not df_demais.empty else 0.0

        real_curadoria = real_novos + real_key + real_outros
        real_obj_principal = real_curadoria + real_plat + real_fint

        def perc(r, m):
            return (r / m) * 100 if m else 0

        perc_obj  = perc(real_obj_principal, meta_obj_principal)
        perc_cura = perc(real_curadoria, meta_curadoria)
        perc_nov  = perc(real_novos, meta_novos)
        perc_key  = perc(real_key, meta_key)
        perc_out  = perc(real_outros, meta_outros)
        perc_plat = perc(real_plat, meta_plat)
        perc_fint = perc(real_fint, meta_fint)

        color_obj  = define_progress_color(perc_obj)
        color_cura = define_progress_color(perc_cura)
        color_nov  = define_progress_color(perc_nov)
        color_key  = define_progress_color(perc_key)
        color_out  = define_progress_color(perc_out)
        color_plat = define_progress_color(perc_plat)
        color_fint = define_progress_color(perc_fint)

        # Garantimos que os valores já contêm o prefixo R$
        def format_monetario(valor):
            resultado = formatar_valor_utils(valor, tipo="monetario")
            # Certifique-se de que começa com R$
            if not resultado.startswith("R$"):
                resultado = f"R${resultado}"
            return resultado

        # Usando a função auxiliar para criar o texto financeiro
        def montar_fintext(r, m):
            rr = format_monetario(r)
            mm = format_monetario(m)
            return f"{rr} / {mm}"

        # Formatação aplicada a todos os valores
        fin_obj  = montar_fintext(real_obj_principal, meta_obj_principal)
        fin_cura = montar_fintext(real_curadoria, meta_curadoria)
        fin_nov  = montar_fintext(real_novos, meta_novos)
        fin_key  = montar_fintext(real_key, meta_key)
        fin_out  = montar_fintext(real_outros, meta_outros)
        fin_plat = montar_fintext(real_plat, meta_plat)
        fin_fint = montar_fintext(real_fint, meta_fint)

        # Log para verificar os valores formatados
        print(f"Obj: {fin_obj}, Curadoria: {fin_cura}, Novos: {fin_nov}, Key: {fin_key}, Outros: {fin_out}")

        # Retorna o card "Retomar o Crescimento"
        return objective_card(
            title="Retomar o Crescimento da Eshows",
            progress_value=perc_obj,
            progress_color=color_obj,
            financial_text=fin_obj,
            card_id="obj-1",
            sub_objectives=[
                {
                    "title": "Curadoria",
                    "progress_value": perc_cura,
                    "progress_color": color_cura,
                    "financial_text": fin_cura,
                    "child_sub_objectives": [
                        {
                            "title": "Novos Clientes",
                            "progress_value": perc_nov,
                            "progress_color": color_nov,
                            "financial_text": fin_nov
                        },
                        {
                            "title": "Key Accounts",
                            "progress_value": perc_key,
                            "progress_color": color_key,
                            "financial_text": fin_key
                        },
                        {
                            "title": "Demais Clientes",
                            "progress_value": perc_out,
                            "progress_color": color_out,
                            "financial_text": fin_out
                        }
                    ]
                },
                {
                    "title": "Plataforma",
                    "progress_value": perc_plat,
                    "progress_color": color_plat,
                    "financial_text": fin_plat
                },
                {
                    "title": "Fintech",
                    "progress_value": perc_fint,
                    "progress_color": color_fint,
                    "financial_text": fin_fint
                }
            ]
        )

    # =============================================================================
    # Objetivo Principal 3
    # =============================================================================
    @app.callback(
        Output("obj-3", "children"),
        [Input("okrs-periodo-dropdown", "value"),
        Input("okrs-mes-dropdown", "value"),
        Input("okrs-mes-inicial-dropdown", "value"),
        Input("okrs-mes-final-dropdown", "value")]
    )
    def update_obj3(periodo, mes_selecionado, mes_inicial, mes_final):
        """
        Callback para atualizar o Objetivo 3: 'Ser uma empresa enxuta e eficiente'
        Processa diversos KPIs relacionados à eficiência operacional da empresa.
        Utiliza a função ler_todas_as_metas para obter os valores das metas.
        """
        print("=== update_obj3 callback ===")
        print(f"Recebi periodo = {periodo} | mes_selecionado = {mes_selecionado}")
        
        # Criar custom_range se for período personalizado
        custom_range = None
        ano = 2025
        if periodo == "custom-range" and mes_inicial and mes_final:
            custom_range = criar_custom_range(ano, mes_inicial, mes_final)
            print(f"Período personalizado: De {mes_nome(mes_inicial)} até {mes_nome(mes_final)} de {ano}")
            if custom_range:
                print(f"custom_range: {custom_range[0]} até {custom_range[1]}")
        
        # Carregamento das bases de dados necessárias (exceto metas que serão via ler_todas_as_metas)
        df_pessoas = carregar_pessoas()
        df_base2_global = df_base2  # Já carregado globalmente
        df_ocorrencias_global = df_ocorrencias  # Já carregado globalmente
        df_eshows_global = df_eshows  # Já carregado globalmente
        df_inad_casas, df_inad_artistas = carregar_base_inad()
        
        # Calcular df_casas_earliest e df_casas_latest para LTV/CAC
        df_casas_earliest = df_eshows_global.groupby("Id da Casa")["Data do Show"].min().reset_index(name="EarliestShow") if df_eshows_global is not None and not df_eshows_global.empty else None
        df_casas_latest = df_eshows_global.groupby("Id da Casa")["Data do Show"].max().reset_index(name="LastShow") if df_eshows_global is not None and not df_eshows_global.empty else None
        
        # Obtenção de todas as metas utilizando a função ler_todas_as_metas
        mes = None
        if periodo == "Mês Aberto":
            mes = mes_selecionado
            
        # Obter o dicionário de metas
        metas = ler_todas_as_metas(ano, periodo, mes, custom_range)
        
        print(f"Dicionário de metas obtido: {metas}")
        
        # Extrair as metas específicas do dicionário
        meta_nrr = metas["NRR"]
        meta_churn = metas["Churn"]
        meta_turnover = metas["TurnOver"]
        meta_lucratividade = metas["Lucratividade"]
        meta_crescimento_sustentavel = metas["CrescimentoSustentavel"]
        meta_palcos_vazios = metas["PalcosVazios"]
        meta_inadimplencia_real = metas["InadimplenciaReal"]
        meta_estabilidade = metas["Estabilidade"]
        meta_eficiencia = metas["EficienciaAtendimento"]
        meta_autonomia = metas["AutonomiaUsuario"]
        meta_perdas = metas["PerdasOperacionais"]
        meta_rpc = metas["ReceitaPorColaborador"]
        meta_ltv_cac = metas["LtvCac"]  # Nova meta para LTV/CAC
        
        # Log das metas obtidas
        print("=== VALORES DAS METAS OBTIDAS ===")
        print(f"NRR: {meta_nrr:.1f}%")
        print(f"Churn: {meta_churn:.1f}%")
        print(f"TurnOver: {meta_turnover:.1f}%")
        print(f"Lucratividade: {meta_lucratividade:.1f}%")
        print(f"CrescimentoSustentavel: {meta_crescimento_sustentavel:.1f}%")
        print(f"PalcosVazios: {meta_palcos_vazios:.1f} (valor absoluto)")
        print(f"InadimplenciaReal: {meta_inadimplencia_real:.1f}%")
        print(f"Estabilidade: {meta_estabilidade:.1f}%")
        print(f"EficienciaAtendimento: {meta_eficiencia:.1f}%")
        print(f"AutonomiaUsuario: {meta_autonomia:.1f}%")
        print(f"PerdasOperacionais: {meta_perdas:.3f}")
        print(f"ReceitaPorColaborador: {meta_rpc:.2f}")
        print(f"LTV/CAC: {meta_ltv_cac:.2f}")
        
        # Mapeamento de status para cores (usado em todo o callback)
        status_color_map = {
            "critico": "danger",
            "ruim": "danger",
            "controle": "warning",
            "bom": "success",
            "excelente": "success"
        }
        
        # Função auxiliar para processar resultados dos KPIs
        def processar_resultado_kpi(kpi_data, nome_kpi, meta_valor, tipo_formatacao="percentual"):
            """
            Processa o resultado de um KPI e retorna valores padronizados.
            """
            # Se o KPI é "Receita por Colaborador", forçamos a formatação monetária.
            if nome_kpi == "Receita por Colaborador":
                tipo_formatacao = "monetario"
            # Se o KPI é "LTV/CAC", forçamos a formatação numérica com 2 casas decimais.
            elif nome_kpi == "LTV/CAC":
                tipo_formatacao = "numero_2f"
            # Se o KPI é "Palcos Vazios", forçamos a formatação numérica.
            elif nome_kpi == "Palcos Vazios":
                tipo_formatacao = "numero"

            # Obtém o valor bruto (string) do dicionário kpi_data
            resultado_str = kpi_data.get("resultado", "0.00")

            # Converte a string formatada em float
            resultado_valor = parse_valor_formatado(resultado_str)

            # Status e cor (usando o mapeamento definido no callback)
            status = kpi_data.get("status", "controle")
            cor = status_color_map.get(status, "danger")

            # Formatação para exibição
            valor_fmt = formatar_valor_utils(resultado_valor, tipo_formatacao)
            meta_fmt = formatar_valor_utils(meta_valor, tipo_formatacao)
            texto_financeiro = f"{valor_fmt} / {meta_fmt}"

            # Define se a meta é "menor é melhor" ou "maior é melhor"
            tipo_meta = "menor" if nome_kpi in [
                "Churn %", "Turn Over", "Palcos Vazios",
                "Inadimplência Real", "Perdas Operacionais"
            ] else "maior"

            # Escolhe o DF global adequado de acordo com o KPI
            if nome_kpi in ["Turn Over", "Receita por Colaborador"]:
                df_global = df_pessoas
            elif nome_kpi == "Palcos Vazios":
                df_global = df_ocorrencias_global
            elif nome_kpi in [
                "Estabilidade",
                "Eficiência de Atendimento",
                "Autonomia do Usuário",
                "Perdas Operacionais"
            ]:
                df_global = df_base2_global
            else:
                df_global = df_eshows_global

            # Mapeia o nome do KPI para sua função de cálculo
            # Remover o bloco de importação abaixo
            '''
            from .variacoes import (
                get_nrr_variables,
                get_churn_variables,
                get_turnover_variables,
                get_lucratividade_variables,
                get_crescimento_sustentavel_variables,
                get_palcos_vazios_variables,
                get_inadimplencia_real_variables,
                get_estabilidade_variables,
                get_eficiencia_atendimento_variables,
                get_autonomia_usuario_variables,
                get_perdas_operacionais_variables,
                get_rpc_variables,
                get_ltv_cac_variables
            )
            '''
            funcao_map = {
                "Net Revenue Retention": get_nrr_variables,
                "Churn %": get_churn_variables,
                "Turn Over": get_turnover_variables,
                "Lucratividade": get_lucratividade_variables,
                "Crescimento Sustentável": get_crescimento_sustentavel_variables,
                "Palcos Vazios": get_palcos_vazios_variables,
                "Inadimplência Real": get_inadimplencia_real_variables,
                "Estabilidade": get_estabilidade_variables,
                "Eficiência de Atendimento": get_eficiencia_atendimento_variables,
                "Autonomia do Usuário": get_autonomia_usuario_variables,
                "Perdas Operacionais": get_perdas_operacionais_variables,
                "Receita por Colaborador": get_rpc_variables,
                "LTV/CAC": get_ltv_cac_variables  # Adicionado função para LTV/CAC
            }

            # Calcula progresso histórico do KPI - usando metas do dicionário
            progresso = calcular_progresso_kpi_com_historico(
                valor_atual=resultado_valor,
                meta=meta_valor,
                tipo_meta=tipo_meta,
                kpi_name=nome_kpi,
                ano=ano,
                periodo=periodo,
                mes=mes_selecionado if periodo == "Mês Aberto" else None,
                custom_range=custom_range if periodo == "custom-range" else None,
                df_global=df_global,
                funcao_kpi=funcao_map.get(nome_kpi),
                dicionario_metas=metas,
                debug=False
            )

            return {
                "valor": resultado_valor,
                "status": status,
                "cor": cor,
                "texto_financeiro": texto_financeiro,
                "progresso": progresso
            }
        
        # ===== Cálculo dos KPIs tradicionais =====
        
        # 1. NRR (Net Revenue Retention)
        nrr_data = get_nrr_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global
        )
        print("\n=== DETALHES DO KPI: NRR ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in nrr_data:
            for nome_var, valor_var in nrr_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_nrr_variables:")
        print(nrr_data)
        
        nrr_processado = processar_resultado_kpi(nrr_data, "Net Revenue Retention", meta_nrr)
        print(f"💰 Valor final de NRR (string): {nrr_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de NRR (float): {nrr_processado['valor']}\n")
        
        # 2. Churn
        churn_data = get_churn_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global
        )
        print("\n=== DETALHES DO KPI: CHURN ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in churn_data:
            for nome_var, valor_var in churn_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_churn_variables:")
        print(churn_data)
        
        churn_processado = processar_resultado_kpi(churn_data, "Churn %", meta_churn)
        print(f"💰 Valor final de Churn (string): {churn_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Churn (float): {churn_processado['valor']}\n")
        
        # 3. Turn Over
        turnover_data = get_turnover_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_pessoas_global=df_pessoas
        )
        print("\n=== DETALHES DO KPI: TURN OVER ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in turnover_data:
            for nome_var, valor_var in turnover_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_turnover_variables:")
        print(turnover_data)
        
        turnover_processado = processar_resultado_kpi(turnover_data, "Turn Over", meta_turnover)
        print(f"💰 Valor final de Turn Over (string): {turnover_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Turn Over (float): {turnover_processado['valor']}\n")
        
        # 4. Lucratividade
        lucratividade_data = get_lucratividade_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global,
            df_base2_global=df_base2_global
        )
        print("\n=== DETALHES DO KPI: LUCRATIVIDADE ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in lucratividade_data:
            for nome_var, valor_var in lucratividade_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_lucratividade_variables:")
        print(lucratividade_data)
        
        lucratividade_processado = processar_resultado_kpi(lucratividade_data, "Lucratividade", meta_lucratividade)
        print(f"💰 Valor final de Lucratividade (string): {lucratividade_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Lucratividade (float): {lucratividade_processado['valor']}\n")
        
        # 5. Crescimento Sustentável
        crescimento_sustentavel_data = get_crescimento_sustentavel_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global,
            df_base2_global=df_base2_global
        )
        print("\n=== DETALHES DO KPI: CRESCIMENTO SUSTENTÁVEL ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in crescimento_sustentavel_data:
            for nome_var, valor_var in crescimento_sustentavel_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_crescimento_sustentavel_variables:")
        print(crescimento_sustentavel_data)
        
        crescimento_sustentavel_processado = processar_resultado_kpi(
            crescimento_sustentavel_data, "Crescimento Sustentável", meta_crescimento_sustentavel
        )
        print(f"💰 Valor final de Crescimento Sustentável (string): {crescimento_sustentavel_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Crescimento Sustentável (float): {crescimento_sustentavel_processado['valor']}\n")
        
        # 6. Palcos Vazios
        print("Calculando Palcos Vazios...")
        palcos_vazios_data = get_palcos_vazios_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_ocorrencias_global=df_ocorrencias_global
        )
        print("\n=== DETALHES DO KPI: PALCOS VAZIOS ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in palcos_vazios_data:
            for nome_var, valor_var in palcos_vazios_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_palcos_vazios_variables:")
        print(palcos_vazios_data)
        
        palcos_vazios_processado = processar_resultado_kpi(
            palcos_vazios_data, "Palcos Vazios", meta_palcos_vazios, "numero"
        )
        print(f"💰 Valor final de Palcos Vazios (string): {palcos_vazios_data.get('resultado','0')}")
        print(f"💰 Valor final de Palcos Vazios (float): {palcos_vazios_processado['valor']}\n")
        
        # 7. Inadimplência Real
        print("Calculando Inadimplência Real...")
        inadimplencia_real_data = get_inadimplencia_real_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global,
            df_inad_casas=df_inad_casas,
            df_inad_artistas=df_inad_artistas
        )
        print("\n=== DETALHES DO KPI: INADIMPLÊNCIA REAL ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in inadimplencia_real_data:
            for nome_var, valor_var in inadimplencia_real_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_inadimplencia_real_variables:")
        print(inadimplencia_real_data)
        
        inadimplencia_real_processado = processar_resultado_kpi(
            inadimplencia_real_data, "Inadimplência Real", meta_inadimplencia_real
        )
        print(f"💰 Valor final de Inadimplência Real (string): {inadimplencia_real_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Inadimplência Real (float): {inadimplencia_real_processado['valor']}\n")
        
        # ===== Cálculo dos NOVOS KPIs =====
        
        # 8. Estabilidade
        estabilidade_data = get_estabilidade_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_base2_global=df_base2_global
        )
        print("\n=== DETALHES DO KPI: ESTABILIDADE ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in estabilidade_data:
            for nome_var, valor_var in estabilidade_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_estabilidade_variables:")
        print(estabilidade_data)
        
        estabilidade_processado = processar_resultado_kpi(
            estabilidade_data, "Estabilidade", meta_estabilidade
        )
        print(f"💰 Valor final de Estabilidade (string): {estabilidade_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Estabilidade (float): {estabilidade_processado['valor']}\n")
        
        # 9. Eficiência de Atendimento
        eficiencia_data = get_eficiencia_atendimento_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_base2_global=df_base2_global
        )
        print("\n=== DETALHES DO KPI: EFICIÊNCIA DE ATENDIMENTO ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in eficiencia_data:
            for nome_var, valor_var in eficiencia_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_eficiencia_atendimento_variables:")
        print(eficiencia_data)
        
        eficiencia_processado = processar_resultado_kpi(
            eficiencia_data, "Eficiência de Atendimento", meta_eficiencia
        )
        print(f"💰 Valor final de Eficiência de Atendimento (string): {eficiencia_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Eficiência de Atendimento (float): {eficiencia_processado['valor']}\n")
        
        # 10. Autonomia do Usuário
        autonomia_data = get_autonomia_usuario_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_base2_global=df_base2_global
        )
        print("\n=== DETALHES DO KPI: AUTONOMIA DO USUÁRIO ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in autonomia_data:
            for nome_var, valor_var in autonomia_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_autonomia_usuario_variables:")
        print(autonomia_data)
        
        autonomia_processado = processar_resultado_kpi(
            autonomia_data, "Autonomia do Usuário", meta_autonomia
        )
        print(f"💰 Valor final de Autonomia do Usuário (string): {autonomia_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Autonomia do Usuário (float): {autonomia_processado['valor']}\n")
        
        # 11. Perdas Operacionais
        perdas_data = get_perdas_operacionais_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global,
            df_base2_global=df_base2_global
        )
        print("\n=== DETALHES DO KPI: PERDAS OPERACIONAIS ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in perdas_data:
            for nome_var, valor_var in perdas_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_perdas_operacionais_variables:")
        print(perdas_data)
        
        perdas_processado = processar_resultado_kpi(
            perdas_data, "Perdas Operacionais", meta_perdas
        )
        print(f"💰 Valor final de Perdas Operacionais (string): {perdas_data.get('resultado','0.00%')}")
        print(f"💰 Valor final de Perdas Operacionais (float): {perdas_processado['valor']}\n")
        
        # 12. Receita por Colaborador
        rpc_data = get_rpc_variables(
            ano=ano, 
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global,
            df_pessoas_global=df_pessoas
        )
        print("\n=== DETALHES DO KPI: RECEITA POR COLABORADOR ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in rpc_data:
            for nome_var, valor_var in rpc_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_rpc_variables:")
        print(rpc_data)
        
        rpc_processado = processar_resultado_kpi(
            rpc_data, "Receita por Colaborador", meta_rpc, "monetario"
        )
        print(f"💰 Valor final de Receita por Colaborador (string): {rpc_data.get('resultado','R$ 0,00')}")
        print(f"💰 Valor final de Receita por Colaborador (float): {rpc_processado['valor']}\n")
        
        # 13. NOVO KPI: LTV/CAC
        print("Calculando LTV/CAC...")
        ltv_cac_data = get_ltv_cac_variables(
            ano=ano,
            periodo=periodo,
            mes=mes_selecionado if periodo=="Mês Aberto" else None,
            custom_range=custom_range if periodo=="custom-range" else None,
            df_eshows_global=df_eshows_global,
            df_base2_global=df_base2_global,
            df_casas_earliest_global=df_casas_earliest,
            df_casas_latest_global=df_casas_latest
        )
        print("\n=== DETALHES DO KPI: LTV/CAC ===")
        print("🔎 Passo a passo do cálculo:")
        if "variables_values" in ltv_cac_data:
            for nome_var, valor_var in ltv_cac_data["variables_values"].items():
                print(f"   • {nome_var}: {valor_var}")
        else:
            print("   • Não há 'variables_values' detalhadas no resultado.")
        print("📄 Dicionário retornado por get_ltv_cac_variables:")
        print(ltv_cac_data)
        
        ltv_cac_processado = processar_resultado_kpi(
            ltv_cac_data, "LTV/CAC", meta_ltv_cac, "numero_2f"
        )
        print(f"💰 Valor final de LTV/CAC (string): {ltv_cac_data.get('resultado','0.00')}")
        print(f"💰 Valor final de LTV/CAC (float): {ltv_cac_processado['valor']}\n")
        
        # Log dos valores finais calculados
        print("=== VALORES FINAIS CALCULADOS ===")
        print(f"NRR: meta={meta_nrr}, realizado={nrr_processado['valor']}, cor={nrr_processado['cor']}")
        print(f"Churn: meta={meta_churn}, realizado={churn_processado['valor']}, cor={churn_processado['cor']}")
        print(f"Turn Over: meta={meta_turnover}, realizado={turnover_processado['valor']}, cor={turnover_processado['cor']}")
        print(f"Lucratividade: meta={meta_lucratividade}, realizado={lucratividade_processado['valor']}, cor={lucratividade_processado['cor']}")
        print(f"Crescimento Sustentável: meta={meta_crescimento_sustentavel}, realizado={crescimento_sustentavel_processado['valor']}, cor={crescimento_sustentavel_processado['cor']}")
        print(f"Palcos Vazios: meta={meta_palcos_vazios}, realizado={palcos_vazios_processado['valor']}, cor={palcos_vazios_processado['cor']}")
        print(f"Inadimplência Real: meta={meta_inadimplencia_real}, realizado={inadimplencia_real_processado['valor']}, cor={inadimplencia_real_processado['cor']}")
        print(f"LTV/CAC: meta={meta_ltv_cac}, realizado={ltv_cac_processado['valor']}, cor={ltv_cac_processado['cor']}")

        # Criação dos subobjetivos usando um formato padronizado
        def criar_subobjetivo(titulo, kpi_processado, valor_meta, nome_kpi):
            """Cria um subobjetivo padronizado a partir dos dados processados"""
            return {
                "title": titulo,
                "progress_value": kpi_processado["valor"],
                "progress_color": kpi_processado["cor"],
                "financial_text": kpi_processado["texto_financeiro"],
                "use_svg": True,
                "target_value": valor_meta,
                "target_type": "menor" if nome_kpi in ["Churn %", "Turn Over", "Palcos Vazios", "Inadimplência Real", "Perdas Operacionais"] else "maior",
                "kpi_name": nome_kpi,
                "progress_percent": kpi_processado["progresso"]
            }
        
        # Lista de subobjetivos
        subobjetivos = [
            # KPIs tradicionais
            criar_subobjetivo("Melhorar o desempenho nos Key Accounts", 
                            nrr_processado, meta_nrr, "Net Revenue Retention"),
            
            criar_subobjetivo("Aumentar a Retenção da Base de Clientes", 
                            churn_processado, meta_churn, "Churn %"),
            
            criar_subobjetivo("Consolidar uma Equipe Engajada e Estável", 
                            turnover_processado, meta_turnover, "Turn Over"),
            
            criar_subobjetivo("Garantir uma Operação Lucrativa e Saudável", 
                            lucratividade_processado, meta_lucratividade, "Lucratividade"),
            
            criar_subobjetivo("Melhorar a Eficiência na Gestão e Alocação de Custos", 
                            crescimento_sustentavel_processado, meta_crescimento_sustentavel, 
                            "Crescimento Sustentável"),
            
            criar_subobjetivo("Assegurar uma Operação Sólida na entrega dos shows", 
                            palcos_vazios_processado, meta_palcos_vazios, "Palcos Vazios"),
            
            criar_subobjetivo("Estabilizar o caixa melhorando a disciplina financeira dos clientes", 
                            inadimplencia_real_processado, meta_inadimplencia_real, "Inadimplência Real"),
            
            # Novos KPIs
            criar_subobjetivo("Prevenir sobrecargas operacionais com produto estável", 
                            estabilidade_processado, meta_estabilidade, "Estabilidade"),
            
            criar_subobjetivo("Garantir atendimento rápido e assertivo", 
                            eficiencia_processado, meta_eficiencia, "Eficiência de Atendimento"),
            
            criar_subobjetivo("Reduzir o esforço operacional ao incentivar o cliente a utilizar as plataformas", 
                            autonomia_processado, meta_autonomia, "Autonomia do Usuário"),
            
            criar_subobjetivo("Evitar perdas financeiras através de maior organização operacional", 
                            perdas_processado, meta_perdas, "Perdas Operacionais"),
            
            criar_subobjetivo("Elevar produtividade da equipe", 
                            rpc_processado, meta_rpc, "Receita por Colaborador"),
            
            # Novo subobjetivo para LTV/CAC
            criar_subobjetivo("Buscar novos clientes rentáveis", 
                            ltv_cac_processado, meta_ltv_cac, "LTV/CAC")
        ]
        
        # Cálculo do progresso global do objetivo
        progressos = [s.get("progress_percent", 0) for s in subobjetivos]
        progresso_objetivo = sum(progressos) / len(progressos) if progressos else 0
        
        # Determinação da cor do objetivo global
        cor_objetivo = define_progress_color(progresso_objetivo)
        
        # Cálculo dos KPIs concluídos
        kpis_concluidos = sum(1 for p in progressos if p >= 100)
        total_kpis = len(progressos)
        financial_text_objetivo = f"{kpis_concluidos} KPIs / {total_kpis} KPIs"
        
        # Retorna o card final do Objetivo 3
        return objective_card(
            title="Ser uma empresa enxuta e eficiente",
            progress_value=progresso_objetivo,
            progress_color=cor_objetivo,
            financial_text=financial_text_objetivo,
            card_id="obj-3",
            sub_objectives=subobjetivos
        )

    # =============================================================================
    # CALLBACK PARA OBJETIVO 4 COM OS 2 NOVOS KPIs (AJUSTADO PARA USAR ler_todas_as_metas)
    # =============================================================================
    @app.callback(
        Output("obj-4", "children"),
        [Input("okrs-periodo-dropdown", "value"),
        Input("okrs-mes-dropdown", "value"),
        Input("okrs-mes-inicial-dropdown", "value"),
        Input("okrs-mes-final-dropdown", "value")]
    )
    def update_obj4(periodo, mes_selecionado, mes_inicial, mes_final):
        """
        Objetivo 4: "Melhorar a reputação da eshows"
        Utiliza a função ler_todas_as_metas para obter as metas dos KPIs:
        - NPS Artistas
        - NPS Equipe
        Suporta período personalizado.
        """
        ano = 2025
        df_base2_global = df_base2
        
        # Criar custom_range se for período personalizado
        custom_range = None
        if periodo == "custom-range" and mes_inicial and mes_final:
            custom_range = criar_custom_range(ano, mes_inicial, mes_final)
            print(f"Período personalizado: De {mes_nome(mes_inicial)} até {mes_nome(mes_final)} de {ano}")
            if custom_range:
                print(f"custom_range: {custom_range[0]} até {custom_range[1]}")
        
        # Obtenção das metas utilizando a função ler_todas_as_metas
        mes = None
        if periodo == "Mês Aberto":
            mes = mes_selecionado
                
        # Obter o dicionário de metas, passando custom_range
        metas = ler_todas_as_metas(ano, periodo, mes, custom_range)
        
        # Extrair as metas específicas para os KPIs do objetivo 4
        meta_nps_artistas = metas["NPSArtistas"]
        meta_nps_equipe = metas["NPSEquipe"]
        
        print(f"Meta NPS Artistas: {meta_nps_artistas}")
        print(f"Meta NPS Equipe: {meta_nps_equipe}")

        # 1) Calcula NPS Artistas
        nps_art_data = get_nps_artistas_variables(
            ano=ano,
            periodo=periodo,
            mes=mes_selecionado if periodo == "Mês Aberto" else None,
            custom_range=custom_range if periodo == "custom-range" else None,
            df_nps_global=df_base2_global
        )
        try:
            val_art = float(nps_art_data["resultado"].replace("%", ""))
        except:
            val_art = 0.0
                
        # Usando a função calcular_progresso_kpi_com_historico para consistência com outros objetivos
        prog_art = calcular_progresso_kpi_com_historico(
            valor_atual=val_art,
            tipo_meta="maior",
            kpi_name="NPS Artistas",
            ano=ano,
            periodo=periodo,
            mes=mes_selecionado if periodo == "Mês Aberto" else None,
            custom_range=custom_range if periodo == "custom-range" else None,
            df_global=df_base2_global,
            funcao_kpi=get_nps_artistas_variables,
            dicionario_metas=metas,
            debug=False
        )
        cor_art = define_progress_color(prog_art)
        fin_text_art = f"{nps_art_data['resultado']} / {formatar_valor_utils(meta_nps_artistas, 'numero')}"

        # 2) Calcula NPS Equipe
        nps_eq_data = get_nps_equipe_variables(
            ano=ano,
            periodo=periodo,
            mes=mes_selecionado if periodo == "Mês Aberto" else None,
            custom_range=custom_range if periodo == "custom-range" else None,
            df_nps_global=df_base2_global
        )
        try:
            val_eq = float(nps_eq_data["resultado"].replace("%", ""))
        except:
            val_eq = 0.0
                
        # Usando a função calcular_progresso_kpi_com_historico para consistência
        prog_eq = calcular_progresso_kpi_com_historico(
            valor_atual=val_eq,
            tipo_meta="maior",
            kpi_name="NPS Equipe",
            ano=ano,
            periodo=periodo,
            mes=mes_selecionado if periodo == "Mês Aberto" else None,
            custom_range=custom_range if periodo == "custom-range" else None,
            df_global=df_base2_global,
            funcao_kpi=get_nps_equipe_variables,
            dicionario_metas=metas,
            debug=False
        )
        cor_eq = define_progress_color(prog_eq)
        fin_text_eq = f"{nps_eq_data['resultado']} / {formatar_valor_utils(meta_nps_equipe, 'numero')}"

        # Progresso final do Obj4 = média
        progresso_obj4 = (prog_art + prog_eq) / 2.0
        cor_obj4 = define_progress_color(progresso_obj4)
        
        # MODIFICADO: Contador de KPIs concluídos para padronizar com Obj3
        kpis_concluidos = sum(1 for p in [prog_art, prog_eq] if p >= 100)
        total_kpis = 2  # Total de KPIs no Objetivo 4
        fin_text_obj4 = f"{kpis_concluidos} KPIs / {total_kpis} KPIs"

        return objective_card(
            title="Melhorar a reputação da eshows",
            progress_value=progresso_obj4,
            progress_color=cor_obj4,
            financial_text=fin_text_obj4,  # Formatação padronizada
            card_id="obj-4",
            sub_objectives=[
                {
                    "title": "NPS Artistas",
                    "progress_value": val_art,
                    "progress_color": cor_art,
                    "financial_text": fin_text_art,
                    "use_svg": True,
                    "target_value": meta_nps_artistas,
                    "target_type": "maior",
                    "kpi_name": "NPS Artistas",
                    "progress_percent": prog_art
                },
                {
                    "title": "NPS Equipe",
                    "progress_value": val_eq,
                    "progress_color": cor_eq,
                    "financial_text": fin_text_eq,
                    "use_svg": True,
                    "target_value": meta_nps_equipe,
                    "target_type": "maior",
                    "kpi_name": "NPS Equipe",
                    "progress_percent": prog_eq
                }
            ]
        )

# if __name__ == "__main__":
#     app.run_server(debug=True, port=8051)


