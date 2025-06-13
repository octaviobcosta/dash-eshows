# Scripts Utilitários

## Scripts de Setup

### setup_offline.ps1 / setup_offline.sh
Scripts para instalação offline usando os wheels pré-baixados na pasta `wheelhouse/`.

**Windows PowerShell:**
```powershell
.\scripts\setup_offline.ps1
```

**Linux/macOS:**
```bash
./scripts/setup_offline.sh
```

## Scripts Auxiliares

### ss.ps1
Script PowerShell para captura de screenshots simplificada.

## Scripts de Aplicação

Os scripts Python específicos da aplicação estão em `app/scripts/`:
- Autenticação: `setup_auth_complete.py`, `generate_password_hash.py`
- ETL: `etl_custosabertos.py`, `etl_npsartistas.py`
- Testes: `test_cac.py`