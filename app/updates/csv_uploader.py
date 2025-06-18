"""
Uploader de CSV para Supabase
Implementa o upload real dos dados validados para o banco
"""

import os
import pandas as pd
import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class CSVUploader:
    """Classe para fazer upload de dados CSV para o Supabase"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY devem estar configurados")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.batch_size = 1000
        
    def upload_data(self, 
                   df: pd.DataFrame, 
                   table_name: str, 
                   mode: str = "replace",
                   error_handling: str = "stop",
                   column_mapping: Dict[str, str] = None,
                   default_values: Dict[str, str] = None,
                   generate_ids: bool = True,
                   progress_callback = None) -> Dict[str, Any]:
        """
        Faz upload dos dados para o Supabase
        
        Args:
            df: DataFrame com os dados
            table_name: Nome da tabela de destino
            mode: "replace", "append" ou "upsert"
            error_handling: "stop" ou "continue"
            column_mapping: Mapeamento de colunas CSV -> Tabela
            progress_callback: Função para reportar progresso
            
        Returns:
            Dict com resultados do upload
        """
        
        start_time = datetime.now()
        results = {
            "success": True,
            "rows_processed": 0,
            "rows_inserted": 0,
            "rows_updated": 0,
            "rows_failed": 0,
            "errors": [],
            "duration": 0
        }
        
        try:
            # Aplicar mapeamento de colunas se fornecido
            if column_mapping:
                df = self._apply_column_mapping(df, column_mapping)
            
            # Aplicar valores padrão
            if default_values:
                df = self._apply_default_values(df, default_values)
            
            # Gerar IDs se necessário
            if generate_ids and 'id' not in df.columns:
                df = self._generate_ids(df, table_name)
            
            # Preparar dados
            df = self._prepare_data(df, table_name)
            
            # Executar operação baseada no modo
            if mode == "replace":
                results = self._replace_data(df, table_name, error_handling, progress_callback, results)
            elif mode == "append":
                results = self._append_data(df, table_name, error_handling, progress_callback, results)
            elif mode == "upsert":
                results = self._upsert_data(df, table_name, error_handling, progress_callback, results)
            
            # Calcular duração
            results["duration"] = (datetime.now() - start_time).total_seconds()
            
        except Exception as e:
            logger.error(f"Erro no upload: {e}")
            results["success"] = False
            results["errors"].append({
                "type": "upload_error",
                "message": str(e)
            })
        
        return results
    
    def _apply_column_mapping(self, df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Aplica mapeamento de colunas"""
        # Renomear colunas conforme mapeamento
        rename_dict = {k: v for k, v in mapping.items() if v and k in df.columns}
        df = df.rename(columns=rename_dict)
        
        # Remover colunas não mapeadas
        mapped_columns = [v for v in mapping.values() if v]
        df = df[mapped_columns]
        
        return df
    
    def _apply_default_values(self, df: pd.DataFrame, default_values: Dict[str, str]) -> pd.DataFrame:
        """Aplica valores padrão para colunas ausentes"""
        from datetime import datetime, timedelta
        
        for col, default in default_values.items():
            if col not in df.columns:
                # Processar valores especiais
                if default == "current_date":
                    df[col] = datetime.now().strftime('%Y-%m-%d')
                elif default == "current_date + 30":
                    df[col] = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                elif default == "True" or default is True:
                    df[col] = True
                elif default == "False" or default is False:
                    df[col] = False
                else:
                    df[col] = default
                    
                logger.info(f"Aplicado valor padrão '{default}' para coluna '{col}'")
        
        return df
    
    def _generate_ids(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """Gera IDs únicos para registros"""
        import uuid
        
        # Opção 1: UUID (mais seguro)
        df['id'] = [str(uuid.uuid4()) for _ in range(len(df))]
        
        # Opção 2: Sequencial baseado em timestamp (alternativa)
        # base_id = int(datetime.now().timestamp() * 1000)
        # df['id'] = range(base_id, base_id + len(df))
        
        logger.info(f"Gerados {len(df)} IDs únicos para tabela {table_name}")
        return df
    
    def _prepare_data(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """Prepara dados para upload"""
        from app.update_modal_improved import brl_to_cents
        
        # Definir colunas monetárias por tabela
        monetary_columns = {
            "baseeshows": ["gmv", "receita", "valor"],
            "base2": ["valor", "receita"],
            "custosabertos": ["valor"],
            "boletoartistas": ["valor"],
            "boletocasas": ["valor"]
        }
        
        # Converter valores monetários de formato BR para centavos
        if table_name in monetary_columns:
            for col in monetary_columns[table_name]:
                if col in df.columns:
                    logger.info(f"Convertendo coluna {col} de formato BR para centavos")
                    # Se a coluna já for numérica, multiplica por 100
                    if pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = (df[col] * 100).round().astype('Int64')
                    else:
                        # Se for string, usa a função de conversão BR
                        df[col] = df[col].apply(brl_to_cents)
        
        # Converter datas para formato ISO
        date_columns = []
        for col in df.columns:
            if 'data' in col.lower() or 'vencimento' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], dayfirst=True)
                    date_columns.append(col)
                except:
                    pass
        
        for col in date_columns:
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Converter NaN para None
        df = df.where(pd.notnull(df), None)
        
        return df
    
    def _replace_data(self, df: pd.DataFrame, table_name: str, 
                     error_handling: str, progress_callback, results: Dict) -> Dict:
        """Modo replace: Remove todos os dados e insere novos"""
        
        try:
            # Deletar todos os registros existentes
            if progress_callback:
                progress_callback("Removendo dados existentes...", 0)
            
            self.client.table(table_name).delete().neq('id', -1).execute()
            
            # Inserir novos dados
            results = self._insert_batch(df, table_name, error_handling, progress_callback, results)
            
        except Exception as e:
            results["success"] = False
            results["errors"].append({
                "type": "delete_error",
                "message": f"Erro ao deletar dados existentes: {str(e)}"
            })
        
        return results
    
    def _append_data(self, df: pd.DataFrame, table_name: str,
                    error_handling: str, progress_callback, results: Dict) -> Dict:
        """Modo append: Adiciona dados aos existentes"""
        return self._insert_batch(df, table_name, error_handling, progress_callback, results)
    
    def _upsert_data(self, df: pd.DataFrame, table_name: str,
                    error_handling: str, progress_callback, results: Dict) -> Dict:
        """Modo upsert: Atualiza existentes e insere novos"""
        
        total_rows = len(df)
        
        for start_idx in range(0, total_rows, self.batch_size):
            end_idx = min(start_idx + self.batch_size, total_rows)
            batch = df.iloc[start_idx:end_idx]
            
            if progress_callback:
                progress = (start_idx / total_rows) * 100
                progress_callback(f"Processando linhas {start_idx+1} a {end_idx}...", progress)
            
            try:
                # Upsert batch
                response = self.client.table(table_name).upsert(
                    batch.to_dict('records'),
                    on_conflict='id'
                ).execute()
                
                results["rows_processed"] += len(batch)
                # Não temos como distinguir inserts de updates no upsert
                results["rows_inserted"] += len(batch)
                
            except Exception as e:
                if error_handling == "stop":
                    results["success"] = False
                    results["errors"].append({
                        "type": "upsert_error",
                        "message": str(e),
                        "batch": f"{start_idx}-{end_idx}"
                    })
                    break
                else:
                    # Continue e registre erro
                    results["rows_failed"] += len(batch)
                    results["errors"].append({
                        "type": "batch_error",
                        "message": str(e),
                        "batch": f"{start_idx}-{end_idx}"
                    })
        
        return results
    
    def _insert_batch(self, df: pd.DataFrame, table_name: str,
                     error_handling: str, progress_callback, results: Dict) -> Dict:
        """Insere dados em lotes"""
        
        total_rows = len(df)
        
        for start_idx in range(0, total_rows, self.batch_size):
            end_idx = min(start_idx + self.batch_size, total_rows)
            batch = df.iloc[start_idx:end_idx]
            
            if progress_callback:
                progress = (start_idx / total_rows) * 100
                progress_callback(f"Inserindo linhas {start_idx+1} a {end_idx}...", progress)
            
            try:
                # Inserir batch
                response = self.client.table(table_name).insert(
                    batch.to_dict('records')
                ).execute()
                
                results["rows_processed"] += len(batch)
                results["rows_inserted"] += len(batch)
                
            except Exception as e:
                if error_handling == "stop":
                    results["success"] = False
                    results["errors"].append({
                        "type": "insert_error",
                        "message": str(e),
                        "batch": f"{start_idx}-{end_idx}"
                    })
                    break
                else:
                    # Continue e registre erro
                    results["rows_failed"] += len(batch)
                    results["errors"].append({
                        "type": "batch_error",
                        "message": str(e),
                        "batch": f"{start_idx}-{end_idx}"
                    })
        
        return results
    
    def test_connection(self) -> bool:
        """Testa a conexão com o Supabase"""
        try:
            # Tenta fazer uma query simples
            self.client.table('baseeshows').select('id').limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao testar conexão: {e}")
            return False