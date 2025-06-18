"""
Validador de CSV para Upload de Dados
Valida estrutura, tipos e integridade dos dados antes do upload
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from datetime import datetime

# Mapeamento de aliases de colunas (variações comuns)
COLUMN_ALIASES = {
    "custosabertos": {
        "id": ["id_custo", "codigo", "cod", "id_despesa"],
        "vencimento": ["data_vencimento", "dt_vencimento", "vencto", "data_vcto"],
        "valor": ["vlr", "value", "montante", "valor_total"],
        "descricao": ["desc", "description", "historico", "descr"],
        "fornecedor_id": ["fornecedor", "id_fornecedor", "cod_fornecedor"],
        "status": ["situacao", "status_pagamento", "pago"]
    },
    "baseeshows": {
        "id": ["id_show", "codigo", "cod_show"],
        "data_show": ["data", "dt_show", "data_evento"],
        "artista": ["nome_artista", "artist", "banda"],
        "casa": ["local", "venue", "casa_show", "espaco"],
        "gmv": ["receita", "faturamento", "valor_total"]
    },
    "base2": {
        "id": ["id_base2", "codigo"],
        "show_id": ["id_show", "show", "evento_id"],
        "valor": ["vlr", "value", "montante"]
    },
    "pessoas": {
        "id": ["id_pessoa", "codigo", "cod"],
        "nome": ["name", "razao_social", "nome_completo"],
        "tipo": ["type", "categoria", "tipo_pessoa"]
    },
    "boletoartistas": {
        "id": ["id_boleto", "codigo"],
        "artista_id": ["id_artista", "artista", "cod_artista"],
        "show_id": ["id_show", "show", "evento_id"],
        "valor": ["vlr", "value", "montante"],
        "vencimento": ["data_vencimento", "dt_vencimento", "vencto"]
    },
    "boletocasas": {
        "id": ["id_boleto", "codigo"],
        "casa_id": ["id_casa", "casa", "cod_casa"],
        "show_id": ["id_show", "show", "evento_id"],
        "valor": ["vlr", "value", "montante"],
        "vencimento": ["data_vencimento", "dt_vencimento", "vencto"]
    },
    "npsartistas": {
        "id": ["id_nps", "codigo"],
        "artista_id": ["id_artista", "artista", "cod_artista"],
        "show_id": ["id_show", "show", "evento_id"],
        "nota": ["score", "avaliacao", "rating"]
    },
    "metas": {
        "id": ["id_meta", "codigo"],
        "ano": ["year", "ano_meta"],
        "mes": ["month", "mes_meta"],
        "valor_meta": ["valor", "target", "objetivo", "meta"]
    }
}

# Definição das estruturas esperadas para cada tabela
TABLE_SCHEMAS = {
    "baseeshows": {
        "essential_columns": ["data_show", "artista", "casa"],  # Mínimo necessário
        "required_columns": ["id", "data_show", "artista", "casa", "cidade", "estado"],
        "optional_columns": ["gmv", "publico", "status", "observacoes"],
        "auto_generated": ["id"],  # Pode ser gerado se não vier
        "default_values": {
            "cidade": "A definir",
            "estado": "SP",
            "status": "confirmado"
        },
        "unique_columns": ["id"],
        "date_columns": ["data_show"],
        "numeric_columns": ["gmv", "publico"],
        "validators": {
            "estado": lambda x: len(str(x)) == 2 if pd.notna(x) else True,
            "gmv": lambda x: float(x) >= 0 if pd.notna(x) else True
        }
    },
    "base2": {
        "essential_columns": ["show_id", "tipo", "valor"],
        "required_columns": ["id", "show_id", "tipo", "valor"],
        "optional_columns": ["descricao", "data_lancamento"],
        "auto_generated": ["id"],
        "default_values": {},
        "unique_columns": ["id"],
        "date_columns": ["data_lancamento"],
        "numeric_columns": ["valor"],
        "validators": {}
    },
    "pessoas": {
        "required_columns": ["id", "nome", "tipo"],
        "optional_columns": ["email", "telefone", "cpf_cnpj", "ativo"],
        "unique_columns": ["id", "cpf_cnpj"],
        "date_columns": [],
        "numeric_columns": [],
        "validators": {
            "email": lambda x: "@" in str(x) if pd.notna(x) else True,
            "tipo": lambda x: str(x).upper() in ["ARTISTA", "CASA", "FORNECEDOR", "COLABORADOR"]
        }
    },
    "custosabertos": {
        "essential_columns": ["descricao", "valor"],  # Mínimo necessário
        "required_columns": ["id", "descricao", "valor", "vencimento"],
        "optional_columns": ["fornecedor_id", "status", "observacoes"],
        "auto_generated": ["id"],
        "default_values": {
            "vencimento": "current_date + 30",  # 30 dias a partir de hoje
            "status": "pendente"
        },
        "unique_columns": ["id"],
        "date_columns": ["vencimento"],
        "numeric_columns": ["valor"],
        "validators": {
            "valor": lambda x: True  # Remover validação aqui, será feita após conversão
        }
    },
    "boletoartistas": {
        "essential_columns": ["artista_id", "show_id", "valor"],
        "required_columns": ["id", "artista_id", "show_id", "valor"],
        "optional_columns": ["vencimento", "status", "observacoes"],
        "auto_generated": ["id"],
        "default_values": {
            "vencimento": "current_date + 30",
            "status": "pendente"
        },
        "unique_columns": ["id"],
        "date_columns": ["vencimento"],
        "numeric_columns": ["valor"],
        "validators": {}
    },
    "boletocasas": {
        "essential_columns": ["casa_id", "show_id", "valor"],
        "required_columns": ["id", "casa_id", "show_id", "valor"],
        "optional_columns": ["vencimento", "status", "observacoes"],
        "auto_generated": ["id"],
        "default_values": {
            "vencimento": "current_date + 30",
            "status": "pendente"
        },
        "unique_columns": ["id"],
        "date_columns": ["vencimento"],
        "numeric_columns": ["valor"],
        "validators": {}
    },
    "npsartistas": {
        "essential_columns": ["artista_id", "show_id", "nota"],
        "required_columns": ["id", "artista_id", "show_id", "nota"],
        "optional_columns": ["comentario", "data_pesquisa"],
        "auto_generated": ["id"],
        "default_values": {
            "data_pesquisa": "current_date"
        },
        "unique_columns": ["id"],
        "date_columns": ["data_pesquisa"],
        "numeric_columns": ["nota"],
        "validators": {
            "nota": lambda x: 0 <= float(x) <= 10 if pd.notna(x) else False
        }
    },
    "metas": {
        "essential_columns": ["ano", "mes", "tipo", "valor_meta"],
        "required_columns": ["id", "ano", "mes", "tipo", "valor_meta"],
        "optional_columns": ["descricao", "responsavel"],
        "auto_generated": ["id"],
        "default_values": {},
        "unique_columns": ["id"],
        "date_columns": [],
        "numeric_columns": ["ano", "mes", "valor_meta"],
        "validators": {
            "mes": lambda x: 1 <= int(x) <= 12 if pd.notna(x) else False,
            "ano": lambda x: 2020 <= int(x) <= 2030 if pd.notna(x) else False
        }
    },
    "pessoas": {
        "essential_columns": ["nome", "tipo"],
        "required_columns": ["id", "nome", "tipo"],
        "optional_columns": ["email", "telefone", "cpf_cnpj", "ativo"],
        "auto_generated": ["id"],
        "default_values": {
            "ativo": True
        },
        "unique_columns": ["id", "cpf_cnpj"],
        "date_columns": [],
        "numeric_columns": [],
        "validators": {
            "email": lambda x: "@" in str(x) if pd.notna(x) else True,
            "tipo": lambda x: str(x).upper() in ["ARTISTA", "CASA", "FORNECEDOR", "COLABORADOR"]
        }
    }
}


class CSVValidator:
    """Classe para validar arquivos CSV antes do upload"""
    
    def __init__(self, df: pd.DataFrame, table_name: str):
        self.df = df.copy()  # Trabalhar com cópia
        self.table_name = table_name
        self.schema = TABLE_SCHEMAS.get(table_name, {})
        self.aliases = COLUMN_ALIASES.get(table_name, {})
        self.errors = []
        self.warnings = []
        self.stats = {}
        self.column_mapping = {}
        self.missing_essential = []
        self.missing_required = []
        self.default_values_to_apply = {}
        
    def validate(self) -> Dict[str, Any]:
        """Executa todas as validações e retorna relatório completo"""
        
        # 0. Aplicar mapeamento de aliases automaticamente
        self._apply_alias_mapping()
        
        # 1. Validar estrutura (novo sistema)
        self._validate_structure()
        
        # 2. Validar tipos de dados
        self._validate_data_types()
        
        # 3. Validar valores únicos
        self._validate_unique_values()
        
        # 4. Validar regras de negócio
        self._validate_business_rules()
        
        # 5. Gerar estatísticas
        self._generate_statistics()
        
        return {
            "valid": len(self.errors) == 0 and len(self.missing_essential) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
            "preview_data": self._get_preview_data(),
            "column_mapping": self.column_mapping,
            "missing_essential": self.missing_essential,
            "missing_required": self.missing_required,
            "default_values": self.default_values_to_apply,
            "can_proceed": len(self.missing_essential) == 0  # Pode prosseguir se tem essenciais
        }
    
    def _apply_alias_mapping(self):
        """Aplica mapeamento automático de aliases de colunas"""
        if not self.aliases:
            return
            
        # Para cada coluna esperada, verificar se existe um alias no CSV
        for expected_col, aliases in self.aliases.items():
            if expected_col not in self.df.columns:
                # Procurar aliases
                for csv_col in self.df.columns:
                    if csv_col.lower() in [alias.lower() for alias in aliases]:
                        # Encontrou um alias! Mapear
                        self.df.rename(columns={csv_col: expected_col}, inplace=True)
                        self.column_mapping[csv_col] = expected_col
                        break
    
    def _validate_structure(self):
        """Valida se o CSV tem as colunas necessárias usando sistema de níveis"""
        csv_columns = set(self.df.columns)
        essential = set(self.schema.get("essential_columns", []))
        required = set(self.schema.get("required_columns", []))
        optional = set(self.schema.get("optional_columns", []))
        auto_generated = set(self.schema.get("auto_generated", []))
        
        # 1. Verificar colunas essenciais (bloqueante)
        missing_essential = essential - csv_columns
        if missing_essential:
            self.missing_essential = list(missing_essential)
            self.errors.append({
                "type": "missing_essential_columns",
                "message": f"Colunas ESSENCIAIS faltando (bloqueante): {', '.join(missing_essential)}",
                "columns": list(missing_essential)
            })
        
        # 2. Verificar colunas obrigatórias mas não essenciais (aviso)
        missing_required = (required - csv_columns) - auto_generated
        if missing_required:
            self.missing_required = list(missing_required)
            # Determinar quais serão geradas e quais terão valores padrão
            will_generate = []
            will_default = []
            
            for col in missing_required:
                if col in auto_generated:
                    will_generate.append(col)
                elif col in self.schema.get("default_values", {}):
                    will_default.append(col)
                    self.default_values_to_apply[col] = self.schema["default_values"][col]
            
            # Criar avisos apropriados
            if will_generate:
                self.warnings.append({
                    "type": "auto_generated_columns",
                    "message": f"Colunas que serão GERADAS automaticamente: {', '.join(will_generate)}",
                    "columns": will_generate
                })
            
            if will_default:
                self.warnings.append({
                    "type": "default_value_columns",
                    "message": f"Colunas que receberão valores PADRÃO: {', '.join(will_default)}",
                    "columns": will_default,
                    "defaults": {col: self.default_values_to_apply[col] for col in will_default}
                })
            
            # Avisar sobre colunas faltando sem solução
            no_solution = [col for col in missing_required if col not in will_generate and col not in will_default]
            if no_solution:
                self.warnings.append({
                    "type": "missing_columns",
                    "message": f"Colunas recomendadas faltando: {', '.join(no_solution)}",
                    "columns": no_solution
                })
        
        # 3. Colunas extras (informativo)
        expected = essential | required | optional
        extra = csv_columns - expected
        if extra:
            self.warnings.append({
                "type": "extra_columns",
                "message": f"Colunas não reconhecidas (serão ignoradas): {', '.join(extra)}",
                "columns": list(extra)
            })
    
    def _validate_data_types(self):
        """Valida tipos de dados das colunas"""
        
        # Validar datas
        for col in self.schema.get("date_columns", []):
            if col in self.df.columns:
                try:
                    pd.to_datetime(self.df[col], errors='coerce')
                    invalid_dates = self.df[pd.to_datetime(self.df[col], errors='coerce').isna() & self.df[col].notna()]
                    if len(invalid_dates) > 0:
                        self.errors.append({
                            "type": "invalid_date",
                            "message": f"Coluna '{col}' tem {len(invalid_dates)} data(s) inválida(s)",
                            "column": col,
                            "rows": invalid_dates.index.tolist()[:10]  # Primeiras 10 linhas
                        })
                except:
                    self.errors.append({
                        "type": "date_parse_error",
                        "message": f"Erro ao processar datas na coluna '{col}'",
                        "column": col
                    })
        
        # Validar números (com suporte para formato brasileiro)
        from app.update_modal_improved import brl_to_cents
        
        for col in self.schema.get("numeric_columns", []):
            if col in self.df.columns:
                # Se for coluna de valor monetário, não validar aqui
                # A conversão será feita depois
                monetary_columns = ["valor", "gmv", "receita", "valor_meta", "valor_total"]
                if col in monetary_columns:
                    # Apenas avisar que será convertido
                    self.warnings.append({
                        "type": "monetary_conversion",
                        "message": f"Coluna '{col}' contém valores monetários que serão convertidos para centavos",
                        "column": col
                    })
                else:
                    # Para outras colunas numéricas, validar normalmente
                    try:
                        pd.to_numeric(self.df[col], errors='coerce')
                        invalid_numbers = self.df[pd.to_numeric(self.df[col], errors='coerce').isna() & self.df[col].notna()]
                        if len(invalid_numbers) > 0:
                            self.errors.append({
                                "type": "invalid_number",
                                "message": f"Coluna '{col}' tem {len(invalid_numbers)} número(s) inválido(s)",
                                "column": col,
                                "rows": invalid_numbers.index.tolist()[:10]
                            })
                    except:
                        self.errors.append({
                            "type": "number_parse_error",
                            "message": f"Erro ao processar números na coluna '{col}'",
                            "column": col
                        })
    
    def _validate_unique_values(self):
        """Valida valores que devem ser únicos"""
        for col in self.schema.get("unique_columns", []):
            if col in self.df.columns:
                duplicates = self.df[self.df.duplicated(subset=[col], keep=False)]
                if len(duplicates) > 0:
                    self.errors.append({
                        "type": "duplicate_values",
                        "message": f"Coluna '{col}' tem {len(duplicates)} valores duplicados",
                        "column": col,
                        "values": duplicates[col].value_counts().head(10).to_dict()
                    })
    
    def _validate_business_rules(self):
        """Valida regras de negócio específicas"""
        validators = self.schema.get("validators", {})
        
        for col, validator in validators.items():
            if col in self.df.columns:
                try:
                    # Aplicar validador
                    mask = self.df[col].apply(validator)
                    invalid_rows = self.df[~mask]
                    
                    if len(invalid_rows) > 0:
                        self.errors.append({
                            "type": "business_rule_violation",
                            "message": f"Coluna '{col}' tem {len(invalid_rows)} valor(es) inválido(s)",
                            "column": col,
                            "rows": invalid_rows.index.tolist()[:10],
                            "sample_values": invalid_rows[col].head(5).tolist()
                        })
                except Exception as e:
                    self.warnings.append({
                        "type": "validation_error",
                        "message": f"Erro ao validar coluna '{col}': {str(e)}",
                        "column": col
                    })
    
    def _generate_statistics(self):
        """Gera estatísticas sobre os dados"""
        self.stats = {
            "total_rows": len(self.df),
            "total_columns": len(self.df.columns),
            "memory_usage": f"{self.df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB",
            "column_stats": {}
        }
        
        # Estatísticas por coluna
        for col in self.df.columns:
            col_stats = {
                "type": str(self.df[col].dtype),
                "non_null": self.df[col].notna().sum(),
                "null": self.df[col].isna().sum(),
                "unique": self.df[col].nunique()
            }
            
            # Estatísticas específicas por tipo
            if col in self.schema.get("numeric_columns", []):
                try:
                    numeric_col = pd.to_numeric(self.df[col], errors='coerce')
                    col_stats.update({
                        "min": numeric_col.min(),
                        "max": numeric_col.max(),
                        "mean": numeric_col.mean(),
                        "median": numeric_col.median()
                    })
                except:
                    pass
            
            self.stats["column_stats"][col] = col_stats
    
    def _get_preview_data(self):
        """Retorna dados para preview com destaque de problemas"""
        preview_df = self.df.head(10).copy()
        
        # Marcar células com problemas
        problem_cells = {}
        
        # Marcar valores nulos em colunas obrigatórias
        for col in self.schema.get("required_columns", []):
            if col in preview_df.columns:
                null_mask = preview_df[col].isna()
                if null_mask.any():
                    problem_cells[col] = preview_df[null_mask].index.tolist()
        
        return {
            "data": preview_df.to_dict('records'),
            "columns": list(preview_df.columns),
            "problem_cells": problem_cells
        }


def suggest_column_mapping(csv_columns: List[str], table_name: str) -> Dict[str, str]:
    """Sugere mapeamento automático de colunas baseado em aliases e similaridade"""
    import difflib
    
    mapping = {}
    schema = TABLE_SCHEMAS.get(table_name, {})
    aliases = COLUMN_ALIASES.get(table_name, {})
    
    # Colunas esperadas (todas)
    expected_columns = (
        set(schema.get("essential_columns", [])) |
        set(schema.get("required_columns", [])) |
        set(schema.get("optional_columns", []))
    )
    
    for csv_col in csv_columns:
        csv_col_lower = csv_col.lower()
        
        # 1. Primeiro verificar se é exatamente uma coluna esperada
        if csv_col in expected_columns:
            mapping[csv_col] = csv_col
            continue
            
        # 2. Verificar aliases definidos
        mapped = False
        for expected_col, col_aliases in aliases.items():
            if csv_col_lower in [alias.lower() for alias in col_aliases]:
                mapping[csv_col] = expected_col
                mapped = True
                break
        
        if mapped:
            continue
            
        # 3. Tentar similaridade com difflib
        matches = difflib.get_close_matches(
            csv_col_lower, 
            [col.lower() for col in expected_columns], 
            n=1, 
            cutoff=0.6
        )
        
        if matches:
            # Encontrar a coluna original (com case correto)
            for expected_col in expected_columns:
                if expected_col.lower() == matches[0]:
                    mapping[csv_col] = expected_col
                    break
    
    return mapping