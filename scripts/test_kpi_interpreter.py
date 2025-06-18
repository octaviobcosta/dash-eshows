#!/usr/bin/env python3
"""Testa o KPI Interpreter com as novas chaves"""

import os
import sys
from dotenv import load_dotenv

# Força recarregar o .env
load_dotenv(override=True)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.kpis.kpi_interpreter import KPIInterpreter

def test_kpi_interpreter():
    print("=== Teste do KPI Interpreter ===\n")
    
    # Verifica chaves
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    print(f"[INFO] Anthropic Key: {anthropic_key[:20]}...{anthropic_key[-5:]}")
    print(f"[INFO] OpenAI Key: {openai_key[:20]}...{openai_key[-5:]}")
    
    # Descrições de KPI mock
    kpi_descriptions = {
        "CMGR": {
            "description": "Taxa de crescimento mensal composta",
            "formula": "((Valor Final / Valor Inicial)^(1/n) - 1) * 100"
        }
    }
    
    # Inicializa interpreter
    interpreter = KPIInterpreter(kpi_descriptions)
    
    # Dados mock
    kpi_values = {
        "resultado": 5.2,
        "periodo": "1º Trimestre 2024",
        "status": "Acima da meta"
    }
    
    strategy_info = {
        "estrategia": "Crescimento sustentável",
        "pilares": "Inovação, Eficiência, Satisfação"
    }
    
    all_indicators = {
        "faturamento": 1000000,
        "crescimento_ytd": 15.3,
        "nps": 72,
        "churn": 8.5
    }
    
    # Testa interpretação
    print("\n[INFO] Testando interpretação de KPI...")
    
    try:
        result = interpreter.generate_kpi_interpretation_claude(
            kpi_name="CMGR",
            kpi_values=kpi_values,
            strategy_info=strategy_info,
            all_indicators=all_indicators
        )
        
        print(f"\n[SUCESSO] Interpretação gerada com {len(result)} caracteres")
        print(f"\nPrimeiras linhas da resposta:")
        print("-" * 50)
        print(result[:300] + "...")
        
        # Mostra métricas
        metrics = interpreter.get_metrics_summary()
        print(f"\n[METRICAS]")
        print(f"- Total de chamadas: {metrics['total_calls']}")
        print(f"- Chamadas à API: {metrics['api_calls']}")
        print(f"- Cache hits: {metrics['cache_hits']}")
        print(f"- Tempo médio: {metrics['avg_response_time']}s")
        
    except Exception as e:
        print(f"\n[ERRO] {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test_kpi_interpreter()