# Dash‑Eshows

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Dash](https://img.shields.io/badge/dash-3.0+-green.svg)
![Status](https://img.shields.io/badge/status-ativo-brightgreen.svg)

Painel de indicadores da eShows construído em Python 🎯 com Dash e banco de dados Supabase (PostgreSQL).

Este README é a cola oficial para quem precisar clonar, rodar ou contribuir no projeto — inclusive você, futuro você.

## 📖 Sobre o Projeto

O **Dash-Eshows** é um sistema de Business Intelligence desenvolvido para monitorar e analisar a performance da eShows, empresa especializada em eventos e shows. O dashboard oferece visualizações interativas dos principais KPIs de negócio, permitindo tomadas de decisão baseadas em dados.

### Principais KPIs monitorados:
- **Receita vs Custos** por período e região
- **NPS de Artistas** e satisfação
- **Churn de Clientes** e retenção
- **Performance Geográfica** por estados
- **Acompanhamento de OKRs** 2025

## 🏗️ Arquitetura

```
Frontend (Dash/Plotly) → Backend (Python) → Database (Supabase/PostgreSQL)
```

### Principais módulos:
- `app/kpis/`: Lógica de cálculo dos indicadores
- `app/okrs/`: Gestão de objetivos e resultados
- `app/data_manager.py`: Interface com banco de dados
- `app/controles.py`: Componentes de interface
- `assets/`: CSS, JS e imagens customizadas

## 📂 Estrutura do repositório

```
dash-eshows/
├─ app/                  # código Python (Dash, scripts, utilitários)
│   ├─ kpis/            # definições e cálculos dos KPIs
│   ├─ okrs/            # gestão de objetivos e resultados
│   ├─ data/            # dados estáticos (CSV, JSON)
│   └─ scripts/         # scripts de ETL e processamento
├─ assets/               # CSS, JS e imagens do frontend
├─ supabase/             # config.toml + migrations/*.sql
│   └─ migrations/
├─ requirements.txt      # dependências PyPI fixadas
├─ .env.example          # template de variáveis de ambiente
└─ README.md             # este arquivo
```

## ✨ Funcionalidades

- 📊 **Dashboard interativo** com 15+ KPIs de negócio
- 🗺️ **Mapas geográficos** de performance por estado
- 📈 **Análise de tendências** e variações temporais
- 🎯 **Acompanhamento de OKRs** 2025
- 📤 **Exportação** de dados em CSV/Excel
- 🔄 **Atualização em tempo real** dos indicadores
- 🎨 **Interface responsiva** para desktop e mobile
- 🔍 **Filtros avançados** por período, região e categoria

## 📋 Pré-requisitos

### Obrigatórios
- **Python 3.12+** - use pyenv ou instalador oficial
- **Git** - para controle de versão
- **Conta Supabase ativa** - banco de dados

### Opcionais (desenvolvimento avançado)
- **Docker Desktop 4.20+** - para supabase db pull/push
- **Node.js 20 LTS** - para Supabase CLI via npx

**Nota:** Windows 10/11 precisa do WSL 2 habilitado ⚙️ para o Docker.

## 🖥️ Como rodar localmente

### Windows (PowerShell)
```powershell
# 1 – clonar
git clone https://github.com/octaviobcosta/dash-eshows.git
cd dash-eshows

# 2 – criar ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3 – instalar dependências
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4 – configurar variáveis de ambiente
Copy-Item .env.example .env
notepad .env  # preencher as chaves necessárias

# 5 – verificar instalação
python -c "import dash; print('Dash OK')"

# 6 – executar aplicação
python app/main.py
```

### Linux/macOS
```bash
# 1-2 – clonar e criar venv
git clone https://github.com/octaviobcosta/dash-eshows.git
cd dash-eshows
python3 -m venv .venv
source .venv/bin/activate

# 3-6 – seguir mesmos passos do Windows
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# editar .env com suas credenciais
python app/main.py
```

## 🎮 Como usar

1. Acesse `http://localhost:8050` após executar o app
2. Use os **filtros de período** no topo da página
3. Navegue entre as abas: **KPIs**, **Mapas**, **OKRs**, **Exportar**
4. **Clique nos gráficos** para interagir e fazer drill-down
5. Use o botão **"Exportar"** para baixar relatórios

## 🔐 Configuração (.env)

Copie `.env.example` para `.env` e configure as seguintes variáveis:

| Variável | Obrigatório | Descrição | Exemplo |
|----------|-------------|-----------|---------|
| SUPABASE_URL | ✅ | URL do projeto Supabase | https://xxxxx.supabase.co |
| SUPABASE_KEY | ✅ | Chave de API (anon/service_role) | eyJhbGciOiJIUzI1NiIs... |
| SUPABASE_DB_PASSWORD | ✅ | Senha do PostgreSQL | sua_senha_segura |
| DEBUG | ❌ | Modo debug (desenvolvimento) | true/false |
| PORT | ❌ | Porta da aplicação | 8050 |

**⚠️ Importante:** Nunca commite essas chaves. Mantenha-as no .env ou nos Secrets do GitHub.

## 🗄️ Fluxo de migrations (Supabase CLI)

```bash
# criar nova migration
npx supabase migration new "ALTER TABLE kpis ADD COLUMN xyz INT;"

# aplicar no banco remoto
npx supabase db push

# sincronizar schema local
npx supabase db pull -p "$SUPABASE_DB_PASSWORD"

# versionar no Git
git add supabase/migrations
git commit -m "feat(db): coluna xyz em kpis"
```

## 🔁 Rotina diária (sincronização)

| Início da sessão | Fim da sessão |
|------------------|---------------|
| `git pull` | `git add . && git commit -m "feat: descrição" && git push` |
| `npx supabase db pull -p "$SUPABASE_DB_PASSWORD"` (se houver mudanças no schema) | |

## 👨‍💻 Para desenvolvedores

### Estrutura de código
- `app/kpis/kpis.py`: Definições e cálculos dos KPIs
- `app/data_manager.py`: Conexão e queries do banco
- `app/controles.py`: Componentes da interface
- `assets/custom.css`: Estilos personalizados

### Adicionando novo KPI
1. **Defina a função** em `app/kpis/kpis.py`
2. **Adicione ao mapeamento** em `app/config_data.py`
3. **Teste a implementação** com dados reais
4. **Documente** a lógica de cálculo

### Comandos úteis
```bash
# atualizar dependências
pip install nova-biblioteca
pip freeze > requirements.txt

# executar testes (se disponível)
python -m pytest app/tests/

# limpeza de cache
python -c "import gc; gc.collect()"
```

## 🌳 Convenções de Git

- **Commits semânticos:** `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`
- **Branch principal:** `main` sempre estável
- **Branches de trabalho:** `dev/feature-nome` ou `fix/issue-123`
- **Pull Requests obrigatórios** para merges na main

### Exemplos de commits:
```
feat(kpis): adiciona cálculo de ROI por evento
fix(dashboard): corrige erro de carregamento em mapas
chore(deps): atualiza versão do dash para 3.0.4
docs(readme): melhora instruções de instalação
```

## ❓ FAQ e Troubleshooting

**Q: O app não carrega os dados**  
A: Verifique as variáveis `SUPABASE_*` no arquivo `.env` e teste a conexão

**Q: Erro "ModuleNotFoundError"**  
A: Execute `pip install -r requirements.txt` novamente no ambiente virtual ativo

**Q: Dashboard muito lento**  
A: Reduza o período de análise ou limpe o cache com `Ctrl+F5`

**Q: Erro de conexão com Supabase**  
A: Confirme se o projeto Supabase está ativo e as credenciais estão corretas

**Q: Gráficos não aparecem**  
A: Verifique se há dados para o período selecionado e se o JavaScript está habilitado

## 🤝 Contribuindo

1. **Fork** o repositório
2. Crie uma **branch** para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. **Implemente** suas mudanças seguindo as convenções
4. **Teste** localmente antes de subir
5. Abra um **Pull Request** descrevendo o problema + solução
6. Aguarde **revisão** (CI precisa passar)

## 📜 Licença

MIT — faça bom proveito, mas mantenha os créditos.

## 📞 Contato

**Octávio Costa** — octavio@eshows.com.br

**Issues e discussões** → [GitHub Issues](https://github.com/octaviobcosta/dash-eshows/issues)

---

⭐ Se este projeto foi útil para você, considere dar uma estrela no repositório!