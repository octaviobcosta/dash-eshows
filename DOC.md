
# Dashboard Eshows – Documentação Técnica

## 1. Visão Geral
**Dashboard Eshows** é um sistema de dashboard interativo desenvolvido para calcular e exibir **KPIs financeiros, operacionais e de engajamento** da plataforma Eshows. Ele utiliza **Python 3.x** com **Plotly Dash** para a interface web, consome dados do **Supabase** via `supabase-py`, faz cache local em memória (e opcionalmente em Parquet) e apresenta esses indicadores em páginas de Dashboard, KPIs e OKRs. O objetivo é oferecer insights em tempo real sobre o negócio, facilitando a tomada de decisões pelo time de gestão.

## 2. Estrutura de Pastas
```
DashboardEshows/
├── app.py
├── data_manager.py
├── modulobase.py
├── utils.py
├── variacoes.py
├── hist.py
├── kpis.py
├── kpis_charts.py
├── kpi_interpreter.py
├── okrs.py
├── controles.py
├── column_mapping.py
├── kpi_descriptions.json        # em data/
├── assets/
│   ├── custom.css
│   ├── datepicker_input.css
│   ├── kpi_effects.css
│   └── logo.png                 # exemplo
└── README.md
```
*(Ver detalhes de cada arquivo na seção 4.)*

## 3. Arquitetura do Sistema
### Camada de Dados  
- **Supabase** → `data_manager.py` faz fetch paginado, renomeia colunas, converte centavos.  
- **modulobase.py** sanitiza, normaliza e mantém caches em memória.

### Camada de Lógica de Negócio  
- **utils.py**: filtros de período, fórmulas de KPI, helpers.  
- **variacoes.py**: consolida cálculo dos KPIs (período atual × comparação).  
- **hist.py**: séries históricas para gráficos.  
- **controles.py**: zonas de controle (faixas de desempenho).

### Camada de Interface  
- **app.py**: instancia Dash, define rotas multipáginas, sidebar, callbacks globais.  
- **kpis.py**: página “Painel de KPIs”.  
- **okrs.py**: página de OKRs.  
- **kpis_charts.py**: mini‑gráficos e indicadores visuais.  
- **assets/**: CSS e imagens.

Fluxo resumido: Supabase → `data_manager` → `modulobase` (cache) → `variacoes`/`utils` → `dcc.Store` → componentes Dash.

## 4. Descrição dos Módulos
### app.py
Ponto de entrada. Carrega dados iniciais, define sidebar, rotas (Dashboard, /kpis, /okrs) e callbacks:
- **`render_page_content`**: troca a página conforme `pathname`.
- **`atualiza_base`**: limpa caches → refaz carregamento → mostra alerta.

### data_manager.py
- `_fetch(table)`: paginação (1 000 linhas), renomeia colunas, divide centavos.  
- `_get(table)`: cache simples.  
- `get_df_*()` wrappers por tabela.  
- `reset_all_data()`: limpa cache.

### modulobase.py
Sanitiza cada DataFrame (shows, base2, pessoas, boletos, ocorrências), gera colunas Ano/Mês, downcast de tipos, guarda em caches globais. Funções `carregar_*()` retornam dados prontos para uso.

### utils.py
- **Filtros** `filtrar_periodo_principal`, `filtrar_periodo_comparacao`.  
- **Fórmulas KPI**: churn, churn novos, ticket, take‑rate, NRR, CMGR etc.  
- **Helpers**: `formatar_valor_utils`, `create_donut_chart`, `create_comparacao_component`.

### variacoes.py
Função principal `calcular_indicadores_periodo(...)`:
1. Carrega bases via modulobase.  
2. Filtra período atual e comparação.  
3. Calcula todos KPIs (≈40).  
4. Usa `controles.get_kpi_status` para classificar.  
5. Retorna dicionário → guardado em `all-indicators-store`.

### hist.py
Funções `*_historico()` que agregam DataFrames por mês → séries temporais usadas no Dashboard.

### controles.py
Dicionário `zonas_de_controle` com faixas (_crítico / ruim / controle / bom / excelente_) e função `get_kpi_status`.

### kpis.py
- Carrega `kpi_descriptions.json`.  
- Define layout da página KPIs (filtros + cards).  
- Callbacks: atualizam filtros, calculam KPIs (via variacoes) e montam cartões.

### kpis_charts.py
`generate_kpi_figure()` cria `go.Indicator`, donuts, sparklines, usando cores positivas/negativas definidas.

### kpi_interpreter.py
Classe `KPIInterpreter` (opcional) usa Anthropic/Claude para gerar textos interpretativos.

### okrs.py
Agrupa KPIs por Objetivo. Exibe meta vs valor atual. Pode gerar resumo automático (IA) se API key presente.

## 5. Fluxo de Dados
1. **Fetch Supabase** → DataFrames brutos (JSON).  
2. **Sanitização** em modulobase → cache memória.  
3. **Filtros** do usuário (ano, período, estado).  
4. **Cálculo** dos KPIs em variacoes/utils.  
5. **Armazenamento** no `dcc.Store`.  
6. **Renderização**: Painel de KPIs, Dashboard histórico, OKRs.

## 6. KPIs e Fórmulas
| KPI | Fórmula | Código | Tela |
|-----|---------|--------|------|
| GMV | Σ Valor Total do Show | `variacoes` | Dashboard, KPIs |
| Faturamento | Σ (Comissões + SaaS …) | `variacoes` | Dashboard, KPIs |
| Custos Totais | Σ Custos | `variacoes` (base2) | KPIs |
| Lucro Líquido | Faturamento – Custos – Impostos | `variacoes` | KPIs |
| Lucratividade | Lucro / Faturamento (%) | `variacoes` | KPIs |
| EBITDA | Lucro + Deprec. + Impostos | `variacoes` | KPIs |
| NumShows | count(shows) | `variacoes` | Dashboard, KPIs |
| Ticket Médio | GMV / NumShows | `variacoes` | Dashboard, KPIs |
| Cidades | unique(Cidade) | `variacoes` | KPIs |
| Palcos Ativos | unique(Id Casa) | `variacoes` | KPIs |
| Novos Palcos | casas cujo 1º show ∈ período | `variacoes` | KPIs |
| Lifetime Médio | média(último – primeiro show dos churnados) | `variacoes` | KPIs |
| Churn | casas sem show >45 d | `utils.calcular_churn` | KPIs |
| Churn % | Churn / base anterior | `variacoes` | KPIs |
| CMGR | ((B/A)^(1/n) – 1) % | `variacoes.get_roll_6m_growth` | KPIs |
| NRR | Receita clientes antigos atual / anterior | `variacoes` | KPIs |
| Take Rate | Faturamento / GMV % | `variacoes` | Dashboard, KPIs |
| … | … *(lista completa de 40 KPIs)* | | |

## 7. Pontos Críticos / Débitos Técnicos
- **Churn** em pandas pode ser lento → considerar pré‑cálculo SQL ou materialized views.  
- **Cache** só em memória; falta TTL ou Parquet persistente.  
- **Inconsistência de nomes** (“Palcos Vazios” vs “PalcosVazios”).  
- **Assets** fora da pasta `assets/` → mover CSS/imagens para carregar automático.  
- **Integração IA** opcional; se sem chave, evitar chamar.  
- **Tratamento de erros Supabase**: melhorar UX se DF vazio.  
- **Zonas de controle hard‑coded** → extrair para config/DB.

## 8. Guia de Execução Local
1. `python -m venv venv && source venv/bin/activate`  
2. `pip install -r requirements.txt` (Dash 2.x, supabase-python).  
3. `.env` → `SUPABASE_URL=…`, `SUPABASE_KEY=…`  
4. Mover CSS/imagens → `assets/`.  
5. `python app.py` e abrir `http://localhost:8050`.  
6. Use botão **Atualizar Base** para refetch do Supabase.

## 9. Glossário
**Palcos** – clientes (casas).  
**Palcos Vazios** – shows cancelados sem substituto.  
**Churn** – perda de clientes (>45 d sem show).  
**Take Rate** – % do GMV capturado como receita.  
**NRR** – Net Revenue Retention.  
**Key Accounts (KA)** – top 5 clientes por receita.  
*(e outros termos listados na seção 9 original).*

---

*Documento gerado automaticamente em 01‑05‑2025.*
