# app/config_data.py
from app.utils.hist import (
    historical_rpc, historical_cmgr, historical_lucratividade, historical_ebitda,
    historical_gmv, historical_ticket, historical_nps_artistas, historical_nps_equipe,
    historical_roll6m, historical_estabilidade, historical_nrr, historical_perdas_operacionais,
    historical_churn, historical_inadimplencia, historical_turnover, historical_perfis_completos,
    historical_autonomia_usuario, historical_sucesso_implantacao, historical_conformidade_juridica,
    historical_eficiencia_atendimento, historical_nivel_servico, historical_take_rate,
    historical_crescimento_sustentavel, historical_inadimplencia_real, historical_palcos_vazios,
    historical_palcos_ativos, historical_ocorrencias, historical_erros_operacionais,
    historical_cidades, historical_novos_palcos, historical_lifetime_novos_palcos,
    historical_fat_novos_palcos, historical_churn_novos_palcos, historical_fat_ka,
    historical_novos_palcos_ka, historical_take_rate_ka, historical_churn_ka,
    historical_num_shows, historical_custos_totais, historical_lucro_liquido,
    historical_faturamento_eshows, historical_num_colaboradores, historical_tempo_medio_casa,
    historical_receita_por_colaborador, historical_custo_medio_colaborador,
    historical_artistas_ativos
)
import gc
import pandas as pd # Adicionado para pd.Timestamp em alguns históricos
import logging

logger = logging.getLogger(__name__)

logger.debug("[config_data.py] Calculando todos os históricos para HIST_KPI_MAP...")

rpc_historico = historical_rpc(months=12)
cmgr_historico = historical_cmgr(months=12)
lucratividade_historico = historical_lucratividade(months=12)
ebitda_historico = historical_ebitda(months=12)
gmv_historico = historical_gmv(months=12)
ticket_historico = historical_ticket(months=12)
nps_artistas_historico = historical_nps_artistas(months=12)
nps_equipe_historico = historical_nps_equipe(months=12)
roll6m_historico = historical_roll6m(months=12)
estabilidade_historico = historical_estabilidade(months=12)
nrr_historico = historical_nrr(months=12)
perdas_historico = historical_perdas_operacionais(months=12)
churn_historico = historical_churn(months=12, dias_sem_show=45)
inadimplencia_historico = historical_inadimplencia(months=12)
turnover_historico = historical_turnover(months=12)
perfis_completos_historico = historical_perfis_completos(months=12)
autonomia_usuario_historico = historical_autonomia_usuario(months=12)
sucesso_implantacao_historico = historical_sucesso_implantacao(months=12)
conformidade_juridica_historico = historical_conformidade_juridica(months=12)
eficiencia_atendimento_historico = historical_eficiencia_atendimento(months=12)
nivel_servico_historico = historical_nivel_servico(months=12)
resultado_take_rate = historical_take_rate(months=12)
resultado_crescimento = historical_crescimento_sustentavel(months=12)
resultado_inadimplencia_real = historical_inadimplencia_real(months=12)
resultado_palcos_vazios = historical_palcos_vazios(months=12)
palcos_ativos_historico = historical_palcos_ativos(months=12)
ocorrencias_historico = historical_ocorrencias(months=12)
erros_operacionais_historico = historical_erros_operacionais(months=12)
cidades_historico = historical_cidades(months=12)
novos_palcos_historico = historical_novos_palcos(months=12)
lifetime_novos_historico = historical_lifetime_novos_palcos(months=12)
fat_novos_historico = historical_fat_novos_palcos(months=12)
churn_novos_historico = historical_churn_novos_palcos(months=12, dias_sem_show=45)
fat_ka_historico = historical_fat_ka(months=12)
novos_palcos_ka_historico = historical_novos_palcos_ka(months=12)
take_rate_ka_historico = historical_take_rate_ka(months=12)
churn_ka_historico = historical_churn_ka(months=12)
num_shows_hist = historical_num_shows(months=12)
custos_totais_hist = historical_custos_totais(months=12)
lucro_liquido_hist = historical_lucro_liquido(months=12)
faturamento_eshows_hist = historical_faturamento_eshows(months=12)
num_colab_historico = historical_num_colaboradores(months=12)
tempo_medio_casa_historico = historical_tempo_medio_casa(months=12)
rpc_historico_pessoas = historical_receita_por_colaborador(months=12)
custo_medio_colab_historico = historical_custo_medio_colaborador(months=12)
artistas_ativos_historico = historical_artistas_ativos(months=12)

gc.collect()
logger.debug("[config_data.py] Coleta de lixo executada após cálculos históricos.")

HIST_KPI_MAP = {
    "GMV": gmv_historico,
    "Número de Shows": num_shows_hist,
    "Ticket Médio": ticket_historico,
    "Número de Cidades": cidades_historico,
    "Faturamento Eshows": faturamento_eshows_hist,
    "Take Rate GMV": resultado_take_rate,
    "Custos Totais": custos_totais_hist,
    "Lucro Líquido": lucro_liquido_hist,
    "Novos Palcos": novos_palcos_historico,
    "Fat. Novos Palcos": fat_novos_historico,
    "Life Time Médio": lifetime_novos_historico,
    "Churn de Novos Palcos": churn_novos_historico,
    "Faturamento KA": fat_ka_historico,
    "Novos Palcos KA": novos_palcos_ka_historico,
    "Take Rate KA": take_rate_ka_historico,
    "Churn KA": churn_ka_historico,
    "Palcos Ativos": palcos_ativos_historico,
    "Ocorrências": ocorrencias_historico,
    "Palcos Vazios": resultado_palcos_vazios,
    "Erros Operacionais": erros_operacionais_historico,
    "Artistas Ativos": artistas_ativos_historico,
    "Nº de Colaboradores": num_colab_historico,
    "Tempo Médio de Casa": tempo_medio_casa_historico,
    "Receita por Colaborador": rpc_historico_pessoas,
    "Custo Médio do Colaborador": custo_medio_colab_historico,
    "CMGR": cmgr_historico,
    "Lucratividade": lucratividade_historico,
    "EBITDA": ebitda_historico,
    "Roll 6M Growth": roll6m_historico,
    "Estabilidade": estabilidade_historico,
    "Net Revenue Retention": nrr_historico,
    "Perdas Operacionais": perdas_historico,
    "Churn %": churn_historico,
    "Inadimplência": inadimplencia_historico,
    "Turn Over": turnover_historico,
    "Perfis Completos": perfis_completos_historico,
    "Autonomia do Usuário": autonomia_usuario_historico,
    "Sucesso da Implantação": sucesso_implantacao_historico,
    "Conformidade Jurídica": conformidade_juridica_historico,
    "Eficiência de Atendimento": eficiencia_atendimento_historico,
    "Nível de Serviço": nivel_servico_historico,
    "Inadimplência Real": resultado_inadimplencia_real,
    "Crescimento Sustentável": resultado_crescimento,
    "NPS Artistas": nps_artistas_historico,
    "NPS Equipe": nps_equipe_historico
}
logger.debug("[config_data.py] HIST_KPI_MAP definido.")

# Adicionar uma função para obter o mapa, para garantir que ele seja acessado após a definição
def get_hist_kpi_map():
    return HIST_KPI_MAP 