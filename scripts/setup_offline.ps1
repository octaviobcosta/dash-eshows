# cria venv se não existir
if (-not (Test-Path .\.venv)) {
    python -m venv .venv
}

# ativa a venv
& .\.venv\Scripts\Activate.ps1

# instala pacotes a partir da wheelhouse
python -m pip install --no-index --find-links ./wheelhouse -r requirements_offline.txt

# põe o app pra rodar
python -m app.main
