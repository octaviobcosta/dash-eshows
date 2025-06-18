# Plano de Otimização de Performance - Dashboard eShows

## 📊 Análise Executiva

Este documento apresenta um plano abrangente para otimizar a performance do Dashboard eShows, com foco em reduzir tempo de carregamento, melhorar responsividade e otimizar uso de recursos.

### Métricas Atuais
- **Tempo de carregamento inicial**: ~15-20 segundos
- **Uso de memória**: ~400-500MB
- **Tempo de resposta callbacks**: 2-5 segundos
- **Cache hit rate**: ~30% (subótimo)

### Metas de Performance
- **Tempo de carregamento**: < 5 segundos
- **Uso de memória**: < 300MB
- **Tempo de resposta**: < 1 segundo
- **Cache hit rate**: > 80%

---

## 🔍 Problemas Identificados

### 1. Sistema de Cache Fragmentado

#### Problema
- **3 níveis de cache** não coordenados (RAM, Parquet, modulobase)
- Cache duplicado causando uso excessivo de memória
- Falta de invalidação coordenada

#### Impacto
- Uso de memória 2x maior que necessário
- Inconsistências entre caches
- Complexidade desnecessária

#### Arquivos Afetados
- `app/data/data_manager.py`
- `app/data/modulobase.py`
- `app/core/main.py`

### 2. Carregamento Excessivo de Dados

#### Problema
- DataFrames globais carregados no início (`utils.py`)
- Todos os dados carregados mesmo quando não necessários
- Falta de lazy loading

#### Impacto
- Tempo de inicialização lento
- Memória desperdiçada com dados não utilizados

#### Arquivos Afetados
- `app/utils/utils.py` (linhas 39-48)
- `app/core/main.py`

### 3. Processamentos Redundantes

#### Problema
- Múltiplas conversões de tipo nas mesmas colunas
- Filtros de período aplicados repetidamente
- Cálculos duplicados de KPIs

#### Impacto
- CPU desperdiçada em reprocessamento
- Tempo de resposta lento em callbacks

#### Arquivos Afetados
- `app/kpis/variacoes.py`
- `app/core/main.py` (callback `atualizar_kpis`)

### 4. Consultas Ineficientes ao Banco

#### Problema
- Paginação sem índices otimizados
- Fetch de todos os dados + filtro em Python
- Queries não otimizadas para o caso de uso

#### Impacto
- Múltiplas requisições desnecessárias
- Transferência excessiva de dados
- Latência aumentada

#### Arquivos Afetados
- `app/data/data_manager.py` (função `_fetch`)

### 5. Callbacks Monolíticos

#### Problema
- Callback principal calcula TODOS os KPIs de uma vez
- Falta de granularidade nas atualizações
- Sem processamento assíncrono

#### Impacto
- Interface travada durante cálculos
- Usuário espera mesmo por KPIs não visíveis

#### Arquivos Afetados
- `app/core/main.py` (linhas 2053-2499)

---

## 💡 Soluções Propostas

### Fase 1: Quick Wins (1-2 semanas)

#### 1.1 Implementar Cache Unificado
```python
# Criar classe UnifiedCache em app/utils/cache.py
class UnifiedCache:
    def __init__(self, ttl_hours=12):
        self._cache = {}
        self._timestamps = {}
        self.ttl = timedelta(hours=ttl_hours)
    
    def get(self, key, loader_func):
        if key in self._cache and self._is_fresh(key):
            return self._cache[key]
        
        data = loader_func()
        self._cache[key] = data
        self._timestamps[key] = datetime.now()
        return data
    
    def invalidate(self, pattern=None):
        # Invalidar cache por padrão
        pass
```

**Benefício**: Redução de 50% no uso de memória

#### 1.2 Otimizar Tipos de Dados
```python
def optimize_dataframe_types(df):
    """Reduz uso de memória em 60-70%"""
    for col in df.columns:
        col_type = df[col].dtype
        
        if col_type != 'object':
            c_min = df[col].min()
            c_max = df[col].max()
            
            if str(col_type)[:3] == 'int':
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
    
    return df
```

**Benefício**: Redução de 60% no uso de memória dos DataFrames

#### 1.3 Implementar Memoização
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def calculate_kpi_cached(kpi_name, period, year):
    # Cálculo do KPI
    pass
```

**Benefício**: 80% menos recálculos

### Fase 2: Otimizações Estruturais (2-4 semanas)

#### 2.1 Lazy Loading de Dados
```python
class LazyDataManager:
    def __init__(self):
        self._data = {}
        self._loaders = {
            'baseeshows': self._load_baseeshows,
            'base2': self._load_base2,
            # etc
        }
    
    def get(self, dataset_name):
        if dataset_name not in self._data:
            self._data[dataset_name] = self._loaders[dataset_name]()
        return self._data[dataset_name]
```

**Benefício**: Carregamento 3x mais rápido

#### 2.2 Callbacks Granulares
```python
# Dividir callback grande em vários menores
@app.callback(
    Output('kpi-gmv-col', 'children'),
    Input('dashboard-ano-dropdown', 'value'),
    prevent_initial_call=True
)
def update_gmv_only(ano):
    # Calcular apenas GMV
    pass

@app.callback(
    Output('kpi-nrr-col', 'children'),
    Input('dashboard-ano-dropdown', 'value'),
    prevent_initial_call=True
)
def update_nrr_only(ano):
    # Calcular apenas NRR
    pass
```

**Benefício**: Interface 5x mais responsiva

#### 2.3 Otimização de Queries
```python
def fetch_optimized(table: str, filters: dict = None):
    query = supa.table(table).select("*")
    
    # Aplicar filtros no banco
    if filters:
        for key, value in filters.items():
            if isinstance(value, tuple):
                query = query.gte(key, value[0]).lte(key, value[1])
            else:
                query = query.eq(key, value)
    
    # Limitar colunas retornadas
    if table == "baseeshows":
        query = query.select("Id do Show,Data,Valor Total do Show,Id_da_Casa")
    
    return query.execute()
```

**Benefício**: 70% menos dados transferidos

### Fase 3: Otimizações Avançadas (4-6 semanas)

#### 3.1 Implementar Data Streaming
```python
def stream_large_datasets(table_name, chunk_size=5000):
    """Processa dados em chunks para economizar memória"""
    offset = 0
    
    while True:
        chunk = fetch_chunk(table_name, offset, chunk_size)
        
        if chunk.empty:
            break
            
        # Processar chunk
        yield process_chunk(chunk)
        
        offset += chunk_size
```

**Benefício**: Suporte para datasets 10x maiores

#### 3.2 Background Processing
```python
from dash.long_callback import DiskcacheLongCallbackManager
import diskcache

cache = diskcache.Cache("./cache")
long_callback_manager = DiskcacheLongCallbackManager(cache)

@app.long_callback(
    Output('kpi-results', 'data'),
    Input('calculate-btn', 'n_clicks'),
    manager=long_callback_manager,
    progress=[Output("progress", "value"), Output("progress", "max")]
)
def calculate_kpis_background(n_clicks):
    # Processamento pesado em background
    pass
```

**Benefício**: Interface nunca trava

#### 3.3 Índices no Banco de Dados
```sql
-- Criar índices para queries comuns
CREATE INDEX idx_baseeshows_data ON baseeshows(Data);
CREATE INDEX idx_baseeshows_casa ON baseeshows("Id_da_Casa");
CREATE INDEX idx_base2_competencia ON base2(Ano, Mes);
CREATE INDEX idx_base2_tipo ON base2("Tipo de receita");

-- Índice composto para filtros combinados
CREATE INDEX idx_baseeshows_data_casa ON baseeshows(Data, "Id_da_Casa");
```

**Benefício**: Queries 10x mais rápidas

---

## 📈 Implementação e Monitoramento

### Cronograma

| Fase | Duração | Impacto Esperado |
|------|---------|------------------|
| Fase 1 | 1-2 semanas | 50% melhoria |
| Fase 2 | 2-4 semanas | 80% melhoria |
| Fase 3 | 4-6 semanas | 95% melhoria |

### Métricas de Acompanhamento

#### 1. Performance Profiling
```python
import cProfile
import pstats

def profile_app():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Executar operações
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
```

#### 2. Monitoramento de Memória
```python
import tracemalloc

tracemalloc.start()

# Código

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 10**6:.1f} MB")
print(f"Peak memory usage: {peak / 10**6:.1f} MB")
```

#### 3. Dashboard de Performance
```python
# Adicionar página de métricas ao dashboard
@app.callback(
    Output('performance-metrics', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_metrics(n):
    return html.Div([
        html.H4("Performance Metrics"),
        html.P(f"Cache Hit Rate: {cache.hit_rate:.1%}"),
        html.P(f"Avg Response Time: {avg_response_time:.2f}s"),
        html.P(f"Memory Usage: {get_memory_usage():.1f} MB")
    ])
```

### Testes de Performance

#### 1. Teste de Carga
```python
import concurrent.futures
import time

def load_test(num_users=10):
    def simulate_user():
        start = time.time()
        # Simular interações do usuário
        return time.time() - start
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = [executor.submit(simulate_user) for _ in range(num_users)]
        results = [f.result() for f in futures]
    
    print(f"Avg response time: {sum(results)/len(results):.2f}s")
```

#### 2. Benchmark de Queries
```python
def benchmark_queries():
    queries = [
        ("baseeshows", {}),
        ("baseeshows", {"Data": ("2024-01-01", "2024-12-31")}),
        ("base2", {"Ano": 2024})
    ]
    
    for table, filters in queries:
        start = time.time()
        data = fetch_optimized(table, filters)
        duration = time.time() - start
        print(f"{table} with {filters}: {duration:.2f}s ({len(data)} rows)")
```

---

## 🎯 Resultados Esperados

### Performance
- **Tempo de carregamento**: 15s → 3s (80% redução)
- **Tempo de resposta**: 3s → 0.5s (83% redução)
- **Uso de memória**: 450MB → 200MB (55% redução)

### Experiência do Usuário
- Interface mais fluida e responsiva
- Sem travamentos durante cálculos
- Feedback visual de progresso

### Escalabilidade
- Suporte para 10x mais dados
- Capacidade para 50+ usuários simultâneos
- Preparado para crescimento futuro

---

## 🚀 Próximos Passos

1. **Aprovar plano** e definir prioridades
2. **Criar branch** `feature/performance-optimization`
3. **Implementar Fase 1** (quick wins)
4. **Medir resultados** e ajustar plano
5. **Prosseguir com Fases 2 e 3**

---

## 📝 Notas Adicionais

- Todas as otimizações devem ser testadas em ambiente de desenvolvimento
- Manter compatibilidade com código existente
- Documentar mudanças significativas
- Considerar rollback plan para cada fase

**Última atualização**: 18/06/2025