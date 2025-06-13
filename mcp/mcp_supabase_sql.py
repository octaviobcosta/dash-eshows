#!/usr/bin/env python3
"""
MCP Server para executar SQL diretamente no Supabase
Permite executar DDL (CREATE TABLE, etc) e DML (INSERT, UPDATE, etc)
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# MCP SDK
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Carrega variáveis de ambiente
load_dotenv()

class SupabaseSQLServer:
    def __init__(self):
        self.server = Server("supabase-sql")
        self.db_url = None
        self.setup_handlers()
        
    def get_db_url(self) -> str:
        """Constrói a URL de conexão do banco"""
        # Primeiro tenta PGURL direto
        db_url = os.getenv('PGURL')
        if db_url:
            return db_url
            
        # Senão, constrói a partir das partes
        supabase_url = os.getenv('SUPABASE_URL')
        db_password = os.getenv('SUPABASE_DB_PASSWORD')
        
        if not supabase_url or not db_password:
            raise ValueError("PGURL ou SUPABASE_URL + SUPABASE_DB_PASSWORD devem estar definidos")
            
        # Extrai o project_id da URL
        project_id = supabase_url.split('//')[1].split('.')[0]
        return f"postgresql://postgres:{db_password}@db.{project_id}.supabase.co:5432/postgres?sslmode=require"
    
    def execute_sql(self, query: str) -> Dict[str, Any]:
        """Executa uma query SQL e retorna o resultado"""
        conn = None
        cursor = None
        try:
            # Conecta ao banco
            conn = psycopg2.connect(self.db_url)
            conn.autocommit = True
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Executa a query
            cursor.execute(query)
            
            # Determina o tipo de resultado
            if cursor.description:
                # SELECT ou RETURNING
                rows = cursor.fetchall()
                return {
                    "success": True,
                    "type": "select",
                    "rows": rows,
                    "rowCount": cursor.rowcount,
                    "columns": [desc[0] for desc in cursor.description]
                }
            else:
                # INSERT, UPDATE, DELETE, CREATE, etc
                return {
                    "success": True,
                    "type": "command",
                    "rowCount": cursor.rowcount,
                    "message": f"Query executada com sucesso. Linhas afetadas: {cursor.rowcount}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "type": "error"
            }
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def setup_handlers(self):
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """Lista as ferramentas disponíveis"""
            return [
                types.Tool(
                    name="execute_sql",
                    description="Executa qualquer comando SQL no Supabase (SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, etc)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Query SQL para executar"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                types.Tool(
                    name="list_tables",
                    description="Lista todas as tabelas do schema public",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="describe_table",
                    description="Mostra a estrutura de uma tabela específica",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "Nome da tabela para descrever"
                            }
                        },
                        "required": ["table_name"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, 
            arguments: Optional[Dict[str, Any]]
        ) -> List[types.TextContent]:
            """Executa uma ferramenta"""
            
            # Inicializa conexão se necessário
            if not self.db_url:
                try:
                    self.db_url = self.get_db_url()
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=f"Erro ao configurar conexão: {str(e)}"
                    )]
            
            if name == "execute_sql":
                query = arguments.get("query", "").strip()
                if not query:
                    return [types.TextContent(
                        type="text",
                        text="Erro: Query SQL não fornecida"
                    )]
                
                result = self.execute_sql(query)
                
                # Formata o resultado
                if result["success"]:
                    if result["type"] == "select":
                        text = f"✅ Query executada com sucesso\n"
                        text += f"Colunas: {', '.join(result['columns'])}\n"
                        text += f"Linhas retornadas: {result['rowCount']}\n\n"
                        
                        # Mostra até 50 linhas
                        for i, row in enumerate(result['rows'][:50]):
                            text += f"--- Linha {i+1} ---\n"
                            for col, val in row.items():
                                text += f"  {col}: {val}\n"
                        
                        if result['rowCount'] > 50:
                            text += f"\n... e mais {result['rowCount'] - 50} linhas"
                    else:
                        text = f"✅ {result['message']}"
                else:
                    text = f"❌ Erro: {result['error']}"
                
                return [types.TextContent(type="text", text=text)]
            
            elif name == "list_tables":
                query = """
                SELECT table_name, 
                       obj_description(pgc.oid, 'pg_class') as comment
                FROM information_schema.tables
                LEFT JOIN pg_class pgc ON pgc.relname = table_name
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
                """
                
                result = self.execute_sql(query)
                
                if result["success"]:
                    text = "📋 Tabelas no schema public:\n\n"
                    for row in result['rows']:
                        comment = f" - {row['comment']}" if row['comment'] else ""
                        text += f"• {row['table_name']}{comment}\n"
                else:
                    text = f"❌ Erro: {result['error']}"
                
                return [types.TextContent(type="text", text=text)]
            
            elif name == "describe_table":
                table_name = arguments.get("table_name", "").strip()
                if not table_name:
                    return [types.TextContent(
                        type="text",
                        text="Erro: Nome da tabela não fornecido"
                    )]
                
                query = f"""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default,
                    col_description(pgc.oid, a.attnum) as comment
                FROM information_schema.columns c
                LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
                LEFT JOIN pg_attribute a ON a.attrelid = pgc.oid AND a.attname = c.column_name
                WHERE table_schema = 'public'
                AND table_name = '{table_name}'
                ORDER BY ordinal_position;
                """
                
                result = self.execute_sql(query)
                
                if result["success"]:
                    if result['rowCount'] == 0:
                        text = f"❌ Tabela '{table_name}' não encontrada"
                    else:
                        text = f"📊 Estrutura da tabela '{table_name}':\n\n"
                        for row in result['rows']:
                            nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
                            default = f" DEFAULT {row['column_default']}" if row['column_default'] else ""
                            comment = f" -- {row['comment']}" if row['comment'] else ""
                            
                            data_type = row['data_type']
                            if row['character_maximum_length']:
                                data_type += f"({row['character_maximum_length']})"
                            
                            text += f"• {row['column_name']}: {data_type} {nullable}{default}{comment}\n"
                else:
                    text = f"❌ Erro: {result['error']}"
                
                return [types.TextContent(type="text", text=text)]
            
            else:
                return [types.TextContent(
                    type="text",
                    text=f"Ferramenta '{name}' não reconhecida"
                )]
    
    async def run(self):
        """Inicia o servidor MCP"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="supabase-sql",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

def main():
    """Ponto de entrada principal"""
    server = SupabaseSQLServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()