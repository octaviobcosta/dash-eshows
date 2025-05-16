# controles.py
import re
import math

# Dicionário com as zonas de controle para cada KPI
zonas_de_controle = {
    'CMGR': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), -5],
        'ruim': [-5, 0],
        'controle': [0, 10],
        'bom': [10, 20],
        'excelente': [20, float('inf')]
    },
    'Lucratividade': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), -5],
        'ruim': [-5, 0],
        'controle': [0, 10],
        'bom': [10, 20],
        'excelente': [20, float('inf')]
    },
    'Hunt (Eficiência Comercial)': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 1],
        'ruim': [1, 1.5],
        'controle': [1.5, 2],
        'bom': [2, 2.5],
        'excelente': [2.5, float('inf')]
    },
    'Net Revenue Retention': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), -5],
        'ruim': [-5, 0],
        'controle': [0, 10],
        'bom': [10, 20],
        'excelente': [20, float('inf')]
    },
    'Inadimplência': {
        'comportamento': 'Negativo',
        'critico': [5, float('inf')],
        'ruim': [3, 5],
        'controle': [2, 3],
        'bom': [1, 2],
        'excelente': [-float('inf'), 1]
    },
    'Inadimplência Real': {
        'comportamento': 'Negativo',
        'critico': [5, float('inf')],
        'ruim': [3, 5],
        'controle': [2, 3],
        'bom': [1, 2],
        'excelente': [-float('inf'), 1]
    },
    'EBITDA': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), -5],
        'ruim': [-5, 0],
        'controle': [0, 10],
        'bom': [10, 20],
        'excelente': [20, float('inf')]
    },
    'Receita por Colaborador': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 8333],
        'ruim': [8333, 12500],
        'controle': [12500, 16667],
        'bom': [16667, 25000],
        'excelente': [25000, float('inf')]
    },
    'Nível de Serviço': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 85],
        'ruim': [85, 90],
        'controle': [90, 95],
        'bom': [95, 98],
        'excelente': [98, float('inf')]
    },
    'Palcos Vazios': {
        'comportamento': 'Negativo',
        'critico': [5, float('inf')],
        'ruim': [3, 5],
        'controle': [1, 3],
        'bom': [0, 1],
        'excelente': [-float('inf'), 0]
    },
    'Perdas Operacionais': {
        'comportamento': 'Negativo',
        'critico': [1, float('inf')],
        'ruim': [0.75, 1],
        'controle': [0.30, 0.75],
        'bom': [0.15, 0.30],
        'excelente': [-float('inf'), 0.15]
    },
    'Churn %': {
        'comportamento': 'Negativo',
        'critico': [15, float('inf')],
        'ruim': [9, 15],
        'controle': [5, 9],
        'bom': [3, 5],
        'excelente': [-float('inf'), 3]
    },
    'Sucesso da Implantação': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 30],
        'ruim': [30, 50],
        'controle': [50, 70],
        'bom': [70, 90],
        'excelente': [90, float('inf')]
    },
    'Autonomia do Usuário': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 20],
        'ruim': [20, 30],
        'controle': [30, 45],
        'bom': [45, 60],
        'excelente': [60, float('inf')]
    },
    'NPS Artistas': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 0],
        'ruim': [0, 30],
        'controle': [30, 50],
        'bom': [50, 70],
        'excelente': [70, float('inf')]
    },
    'Take Rate': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 4],
        'ruim': [4, 6],
        'controle': [6, 10],
        'bom': [10, 15],
        'excelente': [15, float('inf')]
    },
    'NPS Equipe': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 0],
        'ruim': [0, 30],
        'controle': [30, 50],
        'bom': [50, 70],
        'excelente': [70, float('inf')]
    },
    'Estabilidade': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 50],
        'ruim': [50, 65],
        'controle': [65, 75],
        'bom': [75, 90],
        'excelente': [90, float('inf')]
    },
    'Eficiência de Atendimento': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 50],
        'ruim': [50, 70],
        'controle': [70, 80],
        'bom': [80, 90],
        'excelente': [90, float('inf')]
    },
    'Turn Over': {
        'comportamento': 'Negativo',
        'critico': [15, float('inf')],
        'ruim': [10, 15],
        'controle': [5, 10],
        'bom': [2, 5],
        'excelente': [-float('inf'), 2]
    },
    'Perfis Completos': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 20],
        'ruim': [20, 30],
        'controle': [30, 45],
        'bom': [45, 60],
        'excelente': [60, float('inf')]
    },
    'Crescimento Sustentável': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), -20],
        'ruim': [-20, -5],
        'controle': [-5, 5],
        'bom': [5, 15],
        'excelente': [15, float('inf')]
    },
    'Conformidade Jurídica': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 50],
        'ruim': [50, 70],
        'controle': [70, 80],
        'bom': [80, 95],
        'excelente': [95, float('inf')]
    },
    'Eficiência Comercial': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 0],
        'ruim': [0, 1],
        'controle': [1, 2],
        'bom': [2, 3],
        'excelente': [3, float('inf')]
    },
    'Score Médio do Show': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 2.5],
        'ruim': [2.5, 3],
        'controle': [3, 3.5],
        'bom': [3.5, 4.2],
        'excelente': [4.2, float('inf')]
    },
    'Churn em Valor': {
        'comportamento': 'Negativo',
        'critico': [10, float('inf')],
        'ruim': [5, 10],
        'controle': [3, 5],
        'bom': [1, 3],
        'excelente': [-float('inf'), 1]
    },
    'Receita por Pessoal': {
        'comportamento': 'Positivo',
        'critico': [-float('inf'), 1.5],
        'ruim': [1.5, 2],
        'controle': [2, 2.5],
        'bom': [2.5, 3.5],
        'excelente': [3.5, float('inf')]
    },
    'CSAT Artistas': {
        'comportamento': 'Positivo',
        'critico':   [-float('inf'), 2.50],
        'ruim':      [2.50, 3.00],
        'controle':  [3.00, 3.50],
        'bom':       [3.50, 4.50],
        'excelente': [4.50, float('inf')]
    },
    'CSAT Operação': {
        'comportamento': 'Positivo',
        'critico':   [-float('inf'), 2.50],
        'ruim':      [2.50, 3.00],
        'controle':  [3.00, 3.50],
        'bom':       [3.50, 4.50],
        'excelente': [4.50, float('inf')]
    },
}

# Mapeamento de KPIs para Áreas
kpi_area_mapping = {
    'CMGR': 'Institucional',
    'Lucratividade': 'Institucional',
    'Hunt (Eficiência Comercial)': 'Comercial',
    'Net Revenue Retention': 'Comercial',
    'Inadimplência': 'Financeiro',
    'Inadimplência Real': 'Financeiro',
    'EBITDA': 'Financeiro',
    'Receita por Colaborador': 'Institucional',
    'Nível de Serviço': 'Operações',
    'Palcos Vazios': 'Operações',
    'Perdas Operacionais': 'Operações',
    'Churn %': 'Operações',
    'Sucesso da Implantação': 'Comercial',
    'Autonomia do Usuário': 'Produto',
    'NPS Artistas': 'Produto',
    'Take Rate': 'Comercial',
    'NPS Equipe': 'Jurídico & Pessoas',
    'Estabilidade': 'Produto',
    'Eficiência de Atendimento': 'Operações',
    'Turn Over': 'Jurídico & Pessoas',
    'Perfis Completos': 'Produto',
    'Crescimento Sustentável': 'Institucional',
    'Conformidade Jurídica': 'Jurídico & Pessoas',
    'Roll 6M Growth': "Institucional",
    'Eficiência Comercial': 'Comercial',
    'Score Médio do Show': 'Operações',
    'Churn $': 'Operações',
    'Receita por Pessoal': 'Financeiro',
    'CSAT Artistas': 'Operações',
    'CSAT Operação': 'Operações'
}

def sanitize_id(value: str) -> str:
    """
    Converte uma string para um ID seguro, mantendo:
      • letras, números e underscores  (\\w)
      • espaços                        (\\s)
      • hífens                         (-)
      • símbolo de porcentagem         (%)

    Remove qualquer outro caractere.
    """
    # raw-string correta: agora \w, \s e \- são interpretados como metacaracteres
    sanitized = re.sub(r'[^\w\s%-]', '', value)
    return sanitized.strip()          # opcional: remove espaços nas pontas

kpis_config = {
    'GMV': {'is_negative': False, 'icon_class': 'fa-solid fa-sack-dollar', 'format_type': 'monetario'},
    'Faturamento': {'is_negative': False, 'icon_class': 'fa-solid fa-chart-line', 'format_type': 'monetario'},
    'Custos': {'is_negative': True, 'icon_class': 'fa-solid fa-chart-pie', 'format_type': 'monetario'},
    'Lucro Líquido': {'is_negative': False, 'icon_class': 'fa-solid fa-piggy-bank', 'format_type': 'monetario'},
    'Shows realizados': {'is_negative': False, 'icon_class': 'fa-solid fa-music', 'format_type': 'numero'},
    'Casas Ativas': {'is_negative': False, 'icon_class': 'fa-solid fa-house', 'format_type': 'numero'},
    'Novas Casas': {'is_negative': False, 'icon_class': 'fa-solid fa-user-plus', 'format_type': 'numero'},
    'Churn': {'is_negative': True, 'icon_class': 'fa-solid fa-user-minus', 'format_type': 'numero'},
    'CAC': {'is_negative': True, 'icon_class': 'fa-solid fa-users', 'format_type': 'monetario'},
    'Projetos Completos': {'is_negative': False, 'icon_class': 'fa-solid fa-microphone', 'format_type': 'numero'},
    'Inadimplência Total': {'is_negative': True, 'icon_class': 'fa-solid fa-microphone', 'format_type': 'monetario'},
    'Receita Top Grupos': {'is_negative': False, 'icon_class': 'fa-solid fa-microphone', 'format_type': 'monetario'},
}

def parse_control_values(control_values):
    """Converte strings 'Infinity' e '-Infinity' para os valores apropriados no Python."""
    for key, value in control_values.items():
        control_values[key] = [
            float('inf') if v == "Infinity" else float('-inf') if v == "-Infinity" else v
            for v in value
        ]
    return control_values

def get_kpi_status(kpi_name, kpi_value, kpi_descriptions=None):
    """
    Determina o status do KPI (crítico, ruim, controle, bom, excelente) com base no valor.
    
    Args:
        kpi_name (str): Nome do KPI
        kpi_value (float): Valor atual do KPI
        kpi_descriptions (dict, optional): Dicionário com as descrições dos KPIs. Se None, usa zonas_de_controle.
        
    Returns:
        tuple: (status, icon_filename)
    """
    # Se não for fornecido kpi_descriptions, usar zonas_de_controle
    if kpi_descriptions is None:
        if kpi_name not in zonas_de_controle:
            return "controle", "controle.png"
        
        zona = zonas_de_controle[kpi_name]
        comportamento = zona.get('comportamento', 'Positivo')
        
        # Verificar a qual intervalo o valor pertence
        def valor_entre(valor, intervalo):
            return intervalo[0] <= valor < intervalo[1]
        
        if comportamento == 'Positivo':
            if valor_entre(kpi_value, zona.get('critico', [-float('inf'), -5])):
                status = 'critico'
            elif valor_entre(kpi_value, zona.get('ruim', [-5, 0])):
                status = 'ruim'
            elif valor_entre(kpi_value, zona.get('controle', [0, 10])):
                status = 'controle'
            elif valor_entre(kpi_value, zona.get('bom', [10, 20])):
                status = 'bom'
            elif valor_entre(kpi_value, zona.get('excelente', [20, float('inf')])):
                status = 'excelente'
            else:
                status = 'indefinido'
        else:
            # Comportamento Negativo
            if valor_entre(kpi_value, zona.get('excelente', [-float('inf'), 1])):
                status = 'excelente'
            elif valor_entre(kpi_value, zona.get('bom', [1, 2])):
                status = 'bom'
            elif valor_entre(kpi_value, zona.get('controle', [2, 3])):
                status = 'controle'
            elif valor_entre(kpi_value, zona.get('ruim', [3, 5])):
                status = 'ruim'
            elif valor_entre(kpi_value, zona.get('critico', [5, float('inf')])):
                status = 'critico'
            else:
                status = 'indefinido'
    else:
        # Usar o kpi_descriptions fornecido
        if kpi_name not in kpi_descriptions:
            return "controle", "controle.png"

        zona = kpi_descriptions[kpi_name]
        comportamento = zona.get('behavior', 'Positivo')
        control_values = zona.get('control_values', {})

        def parse_limit(value):
            if value == "Infinity":
                return float('inf')
            elif value == "-Infinity":
                return float('-inf')
            else:
                return float(value)

        intervals = {}
        for key, val in control_values.items():
            start = parse_limit(val[0])
            end = parse_limit(val[1])
            intervals[key] = (start, end)

        def valor_entre(valor, intervalo):
            return intervalo[0] <= valor < intervalo[1]

        if comportamento == 'Positivo':
            if valor_entre(kpi_value, intervals.get('critico', (-float('inf'), -5))):
                status = 'critico'
            elif valor_entre(kpi_value, intervals.get('ruim', (-5, 0))):
                status = 'ruim'
            elif valor_entre(kpi_value, intervals.get('controle', (0, 10))):
                status = 'controle'
            elif valor_entre(kpi_value, intervals.get('bom', (10, 20))):
                status = 'bom'
            elif valor_entre(kpi_value, intervals.get('excelente', (20, float('inf')))):
                status = 'excelente'
            else:
                status = 'indefinido'
        else:
            # Caso de comportamento Negativo
            if valor_entre(kpi_value, intervals.get('excelente', (-float('inf'), 1))):
                status = 'excelente'
            elif valor_entre(kpi_value, intervals.get('bom', (1, 2))):
                status = 'bom'
            elif valor_entre(kpi_value, intervals.get('controle', (2, 3))):
                status = 'controle'
            elif valor_entre(kpi_value, intervals.get('ruim', (3, 5))):
                status = 'ruim'
            elif valor_entre(kpi_value, intervals.get('critico', (5, float('inf')))):
                status = 'critico'
            else:
                status = 'indefinido'

    status_to_icon = {
       'critico': 'critico.png',
       'ruim': 'ruim.png',
       'controle': 'controle.png',
       'bom': 'bom.png',
       'excelente': 'excelente.png',
       'indefinido': 'indefinido.png'
    }

    icon_filename = status_to_icon.get(status, 'indefinido.png')
    return status, icon_filename




