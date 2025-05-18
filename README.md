# Dash‑Eshows

Painel de indicadores da eShows construído em Python 🎯 com Dash e banco de dados Supabase (PostgreSQL).

Este README é a cola oficial para quem precisar clonar, rodar ou contribuir no projeto — inclusive você, futuro você.

## 📂 Estrutura do repositório

dash-eshows/
├─ app/                  # código Python (Dash, scripts, utilitários)
├─ assets/               # CSS, JS e imagens do front
├─ supabase/             # config.toml + migrations/*.sql
│   └─ migrations/
├─ requirements.txt      # dependências PyPI fixadas
├─ .env.example          # template de variáveis de ambiente (sem segredos)
└─ README.md             # este arquivo

## 🚀 Requisitos

| Ferramenta     | Versão mínima | Observação                           |
|----------------|---------------|--------------------------------------|
| Python         | 3.12          | use pyenv ou instalador oficial    |
| Node.js        | 20 LTS        | para Supabase CLI via npx            |
| Docker Desktop | 4.20+         | preciso para supabase db pull/push   |
| Git            | qualquer      | fluxo Git padrão                     |

Windows 10/11 precisa do WSL 2 habilitado ⚙️ para o Docker.

## 🖥️ Como rodar localmente

```powershell
# 1 – clonar
$ git clone <https://github.com/octaviobcosta/dash-eshows.git>
$ cd dash-eshows

# 2 – criar venv
$ python -m venv .venv
$ .\.venv\Scripts\Activate.ps1

# 3 – deps
$ python -m pip install --upgrade pip
$ pip install -r requirements.txt

# 4 – copiar variáveis e preencher chaves
$ Copy-Item .env.example .env
$ notepad .env

# 5 – subir o app
$ python app/main.py                  # ou "python -m flask run" se for Flask
```

## 🔑 Variáveis de ambiente (essenciais)

| Nome                 | Descrição                                  |
|----------------------|--------------------------------------------|
| SUPABASE_URL         | URL do projeto Supabase                    |
| SUPABASE_KEY         | Chave anon ou service_role                 |
| SUPABASE_DB_PASSWORD | Senha do Postgres usada pelo CLI           |
| …                    | …                                          |

Nunca commit essas chaves. Mantenha-as no .env ou nos Secrets do GitHub.

## 📶 Modo offline

Sem `SUPABASE_URL` e `SUPABASE_KEY` o dashboard lê os arquivos Parquet em
`app/_cache_parquet/`. Somente as colunas listadas em `app/column_mapping.py`
são carregadas para reduzir o consumo inicial de RAM.

Para incluir uma nova coluna no futuro:

1. Adicione o nome em `COLS_<TABELA>` no mesmo arquivo.
2. Caso seja valor em centavos, inclua também em `CENTAVOS_<TABELA>`.
3. Rode o app online uma vez para atualizar o Parquet local.

## 🗄️ Fluxo de migrations (Supabase CLI)

```bash
# criar nova migration
act supabase db new "ALTER TABLE kpis ADD COLUMN xyz INT;"

# aplicar no banco remoto
act supabase db push

# versionar no Git
git add supabase/migrations
git commit -m "feat(db): coluna xyz em kpis"
```

## 🔁 Rotina diária (duas máquinas)

| Início                                             | Fim                                                  |
|----------------------------------------------------|------------------------------------------------------|
| `git pull`                                         | `git add . + git commit -m "msg" + git push`           |
| (se houver migrations ⇩)                           |                                                      |
| `supabase db pull -p "$SUPABASE_DB_PASSWORD"`       |                                                      |

## 🌳 Convenções de Git

- Commits semânticos: `feat:`, `fix:`, `chore:`, `docs:` …
- `main` sempre estável; `dev/feature‑x` para trabalho.
- Pull Requests obrigatórios para merges.

## 🛠️ Scripts úteis

```bash
# atualizar dependências
act pip install nova-lib && pip freeze | Select-String '==' > requirements.txt

# limpeza de requirements (remove caminhos locais)
act pip freeze | Select-String '==' > requirements.txt
```

(“act” == digite no terminal com venv ativo)

## 🤝 Contribuindo

- Fork / branch
- Abra Pull Request descrevendo o problema + solução
- Aguarde revisão (CI precisa passar)

## 📜 Licença

MIT — faça bom proveito, mas mantenha os créditos.

## Contato

Octávio Costa — <octavio@eshows.com.br>

## Issues e discussões → GitHub Issues
