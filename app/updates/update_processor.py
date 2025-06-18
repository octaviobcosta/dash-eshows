"""
Processador de arquivos para atualização de base de dados
Suporta CSV e Excel com conversão automática de valores BRL para centavos
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Mapeamento de todas as tabelas do Supabase
SUPABASE_TABLES = {
    "baseeshows": {
        "label": "Base eShows",
        "description": "Dados principais de shows e eventos",
        "money_columns": ["Valor da Casa", "Valor do Artista", "Valor Bruto", "Valor Líquido"],
        "date_columns": ["Data do Show"],
        "required_columns": ["Id da Casa", "Data do Show", "Cidade"]
    },
    "base2": {
        "label": "Base2", 
        "description": "Dados complementares de shows",
        "money_columns": ["valor_bruto", "valor_liquido"],
        "date_columns": ["data"],
        "required_columns": []
    },
    "pessoas": {
        "label": "Pessoas",
        "description": "Cadastro de pessoas (clientes, artistas, etc)",
        "money_columns": [],
        "date_columns": ["data_nascimento", "data_cadastro"],
        "required_columns": ["nome"]
    },
    "ocorrencias": {
        "label": "Ocorrências",
        "description": "Registro de ocorrências e eventos",
        "money_columns": [],
        "date_columns": ["data_ocorrencia"],
        "required_columns": ["tipo", "descricao"]
    },
    "metas": {
        "label": "Metas",
        "description": "Metas e objetivos",
        "money_columns": ["valor_meta"],
        "date_columns": ["data_inicio", "data_fim"],
        "required_columns": ["indicador", "valor_meta"]
    },
    "custosabertos": {
        "label": "Custos Abertos",
        "description": "Detalhamento de custos por categoria",
        "money_columns": ["valor"],
        "date_columns": ["mes"],
        "required_columns": ["categoria", "valor"]
    },
    "npsartistas": {
        "label": "NPS Artistas",
        "description": "Avaliações e NPS dos artistas",
        "money_columns": [],
        "date_columns": ["data_avaliacao"],
        "required_columns": ["artista", "nota"]
    },
    "senhasdash": {
        "label": "Senhas Dashboard",
        "description": "Usuários do dashboard (cuidado ao atualizar!)",
        "money_columns": [],
        "date_columns": ["criado_em", "ultimo_acesso"],
        "required_columns": ["email", "nome", "senha_hash"]
    },
    "custos_fixos": {
        "label": "Custos Fixos",
        "description": "Custos fixos mensais",
        "money_columns": ["valor"],
        "date_columns": ["mes"],
        "required_columns": ["categoria", "valor"]
    },
    "receitas": {
        "label": "Receitas",
        "description": "Receitas detalhadas",
        "money_columns": ["valor"],
        "date_columns": ["data"],
        "required_columns": ["tipo", "valor"]
    }
}

def brl_to_cents(value) -> int:
    """
    Converte valor em formato brasileiro (1.234,56) para centavos (123456)
    Aceita também formatos com ponto decimal (1234.56)
    """
    if pd.isna(value) or value == "" or value is None:
        return 0
    
    # Se já for número, multiplica por 100
    if isinstance(value, (int, float)):
        return int(round(value * 100))
    
    # Converte para string e limpa
    value_str = str(value).strip()
    
    # Remove caracteres não numéricos exceto vírgula e ponto
    value_str = ''.join(c for c in value_str if c.isdigit() or c in '.,')
    
    if not value_str:
        return 0
    
    # Detecta formato brasileiro (vírgula como decimal)
    if ',' in value_str:
        # Remove pontos de milhar e substitui vírgula por ponto
        value_str = value_str.replace('.', '').replace(',', '.')
    
    try:
        value_float = float(value_str)
        return int(round(value_float * 100))
    except:
        logger.warning(f"Não foi possível converter valor: {value}")
        return 0

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpa nomes de colunas: snake_case, sem acentos, sem espaços extras
    """
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('ç', 'c')
        .str.replace('ã', 'a')
        .str.replace('õ', 'o')
        .str.replace('á', 'a')
        .str.replace('é', 'e')
        .str.replace('í', 'i')
        .str.replace('ó', 'o')
        .str.replace('ú', 'u')
        .str.replace('â', 'a')
        .str.replace('ê', 'e')
        .str.replace('ô', 'o')
        .str.replace(r'[^a-z0-9_]', '', regex=True)
    )
    return df

def process_date_column(series: pd.Series) -> pd.Series:
    """
    Processa coluna de data para formato ISO
    """
    # Tenta diferentes formatos de data
    formats = [
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%Y/%m/%d',
        '%d.%m.%Y',
        '%Y.%m.%d'
    ]
    
    for fmt in formats:
        try:
            return pd.to_datetime(series, format=fmt).dt.strftime('%Y-%m-%d')
        except:
            continue
    
    # Se nenhum formato funcionar, tenta inferir
    try:
        return pd.to_datetime(series, infer_datetime_format=True).dt.strftime('%Y-%m-%d')
    except:
        logger.warning(f"Não foi possível converter datas")
        return series

def validate_dataframe(df: pd.DataFrame, table_name: str) -> Tuple[bool, List[str]]:
    """
    Valida se o DataFrame tem as colunas necessárias para a tabela
    Retorna (is_valid, list_of_errors)
    """
    errors = []
    table_config = SUPABASE_TABLES.get(table_name, {})
    
    # Verifica colunas obrigatórias
    required = table_config.get('required_columns', [])
    df_cols = [col.lower().replace(' ', '_') for col in df.columns]
    
    for col in required:
        col_normalized = col.lower().replace(' ', '_')
        if col_normalized not in df_cols:
            errors.append(f"Coluna obrigatória ausente: {col}")
    
    # Verifica se há pelo menos uma linha de dados
    if len(df) == 0:
        errors.append("Arquivo não contém dados")
    
    return len(errors) == 0, errors

def process_upload_file(content: str, filename: str, table_name: str) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """
    Processa arquivo enviado (CSV ou Excel) e prepara para upload
    Retorna (dataframe_processado, lista_de_erros)
    """
    errors = []
    
    try:
        # Detecta tipo de arquivo
        file_ext = Path(filename).suffix.lower()
        
        # Lê o arquivo
        if file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(content, dtype=str)
        elif file_ext == '.csv':
            # Tenta diferentes encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(content, dtype=str, encoding=encoding)
                    break
                except:
                    continue
            else:
                errors.append("Não foi possível ler o arquivo CSV. Verifique o encoding.")
                return None, errors
        else:
            errors.append(f"Formato de arquivo não suportado: {file_ext}")
            return None, errors
        
        # Limpa nomes de colunas
        df = clean_column_names(df)
        
        # Remove linhas completamente vazias
        df = df.dropna(how='all')
        
        # Valida DataFrame
        is_valid, validation_errors = validate_dataframe(df, table_name)
        if not is_valid:
            errors.extend(validation_errors)
            return None, errors
        
        # Processa colunas específicas da tabela
        table_config = SUPABASE_TABLES.get(table_name, {})
        
        # Converte colunas monetárias
        money_cols = table_config.get('money_columns', [])
        for col in money_cols:
            col_normalized = col.lower().replace(' ', '_')
            if col_normalized in df.columns:
                df[col_normalized] = df[col_normalized].apply(brl_to_cents)
        
        # Processa colunas de data
        date_cols = table_config.get('date_columns', [])
        for col in date_cols:
            col_normalized = col.lower().replace(' ', '_')
            if col_normalized in df.columns:
                df[col_normalized] = process_date_column(df[col_normalized])
        
        # Substitui NaN por None para melhor compatibilidade
        df = df.where(pd.notnull(df), None)
        
        return df, errors
        
    except Exception as e:
        logger.error(f"Erro ao processar arquivo: {str(e)}")
        errors.append(f"Erro ao processar arquivo: {str(e)}")
        return None, errors

def get_table_preview(df: pd.DataFrame, max_rows: int = 5) -> pd.DataFrame:
    """
    Retorna preview do DataFrame para mostrar ao usuário
    """
    preview = df.head(max_rows).copy()
    
    # Para colunas monetárias em centavos, mostra formatado em preview
    for col in preview.columns:
        if any(keyword in col.lower() for keyword in ['valor', 'preco', 'custo', 'receita']):
            if preview[col].dtype in ['int64', 'float64']:
                preview[f"{col}_preview"] = preview[col].apply(
                    lambda x: f"R$ {x/100:,.2f}" if pd.notnull(x) else ""
                )
    
    return preview