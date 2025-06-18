"""
Executor de atualizações para o Supabase
Executa as atualizações reais no banco de dados
"""

import logging
from typing import Dict, List, Tuple, Optional
import pandas as pd
from supabase import Client
from datetime import datetime

logger = logging.getLogger(__name__)

def execute_table_update(
    supabase_client: Client,
    table_name: str,
    data: pd.DataFrame,
    mode: str = "replace"
) -> Tuple[bool, Optional[str]]:
    """
    Executa atualização de uma tabela no Supabase
    
    Args:
        supabase_client: Cliente do Supabase
        table_name: Nome da tabela
        data: DataFrame com os dados
        mode: "replace" (substitui tudo) ou "append" (adiciona)
    
    Returns:
        (sucesso, mensagem_erro)
    """
    try:
        # Converte DataFrame para lista de dicts
        records = data.to_dict('records')
        
        if not records:
            return False, "Nenhum registro para processar"
        
        # Log do início
        logger.info(f"Iniciando atualização da tabela {table_name} com {len(records)} registros")
        
        if mode == "replace":
            # Primeiro, deleta todos os registros existentes
            try:
                logger.info(f"Deletando registros existentes em {table_name}")
                supabase_client.table(table_name).delete().neq('id', 0).execute()
            except Exception as e:
                logger.warning(f"Erro ao deletar registros (pode ser normal se tabela vazia): {e}")
        
        # Insere os novos registros em lotes
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                result = supabase_client.table(table_name).insert(batch).execute()
                total_inserted += len(batch)
                logger.info(f"Inseridos {len(batch)} registros (total: {total_inserted}/{len(records)})")
            except Exception as e:
                error_msg = f"Erro ao inserir lote {i//batch_size + 1}: {str(e)}"
                logger.error(error_msg)
                return False, error_msg
        
        # Registra atualização no log
        try:
            log_entry = {
                "tabela": table_name,
                "registros": len(records),
                "modo": mode,
                "data_atualizacao": datetime.now().isoformat(),
                "status": "sucesso"
            }
            supabase_client.table("log_atualizacoes").insert(log_entry).execute()
        except:
            # Se não tiver tabela de log, apenas ignora
            pass
        
        return True, None
        
    except Exception as e:
        error_msg = f"Erro geral na atualização: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def validate_connection(supabase_client: Client) -> Tuple[bool, Optional[str]]:
    """
    Valida se a conexão com o Supabase está funcionando
    """
    try:
        # Tenta uma query simples
        result = supabase_client.table("baseeshows").select("id").limit(1).execute()
        return True, None
    except Exception as e:
        return False, f"Erro de conexão: {str(e)}"

def get_table_info(supabase_client: Client, table_name: str) -> Dict:
    """
    Obtém informações sobre uma tabela (colunas, tipos, etc)
    """
    try:
        # Pega uma linha para analisar estrutura
        result = supabase_client.table(table_name).select("*").limit(1).execute()
        
        if result.data and len(result.data) > 0:
            sample = result.data[0]
            columns = list(sample.keys())
            return {
                "exists": True,
                "columns": columns,
                "sample": sample
            }
        else:
            # Tabela existe mas está vazia
            return {
                "exists": True,
                "columns": [],
                "sample": None
            }
    except Exception as e:
        return {
            "exists": False,
            "error": str(e)
        }

def backup_table(supabase_client: Client, table_name: str) -> Optional[pd.DataFrame]:
    """
    Faz backup de uma tabela antes de atualizar
    Retorna DataFrame com os dados ou None se falhar
    """
    try:
        logger.info(f"Fazendo backup da tabela {table_name}")
        
        # Busca todos os dados
        all_data = []
        limit = 1000
        offset = 0
        
        while True:
            result = supabase_client.table(table_name).select("*").range(offset, offset + limit - 1).execute()
            
            if not result.data:
                break
                
            all_data.extend(result.data)
            
            if len(result.data) < limit:
                break
                
            offset += limit
        
        if all_data:
            df_backup = pd.DataFrame(all_data)
            logger.info(f"Backup concluído: {len(df_backup)} registros")
            return df_backup
        else:
            logger.info(f"Tabela {table_name} está vazia, sem dados para backup")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Erro ao fazer backup: {str(e)}")
        return None