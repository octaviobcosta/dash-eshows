###############################################################################
# arruma_tudo.ps1 – reorganiza arquivos .py e corrige imports
# (execute a partir da raiz do projeto)
###############################################################################

# 1) Variáveis básicas
$PkgName = "app"                     # nome do pacote
$Here    = Get-Location              # diretório atual (raiz do projeto)

###############################################################################
# 2) Move QUALQUER .py que ainda esteja fora de /app
###############################################################################
Get-ChildItem -Path $Here -Filter *.py -File -Recurse |
Where-Object {
    $_.FullName -notmatch "\\$PkgName(\\|$)" -and   # fora de /app
    $_.FullName -notmatch "\\venv\\"                # fora do venv
} |
ForEach-Object {
    $dest = switch -Regex ($_.Name) {
        '^kpis.*\.py$' { "$PkgName\kpis"; break }
        '^okrs.*\.py$' { "$PkgName\okrs"; break }
        default        { "$PkgName" }
    }
    if (-not (Test-Path $dest)) { New-Item -Type Directory -Path $dest | Out-Null }
    Move-Item $_.FullName -Destination $dest -Force
    Write-Host " [MOVE] $($_.Name)  →  $dest"
}

###############################################################################
# 3) Módulos que precisam de import relativo
###############################################################################
$patterns = @(
  'modulobase','utils','hist','kpis_charts','column_mapping',
  'controles','data_manager','variacoes','kpis','okrs'
)

###############################################################################
# 4) Ajusta os imports em todo o pacote /app
###############################################################################
Get-ChildItem -Path $PkgName -Recurse -Filter *.py | ForEach-Object {
    $code = Get-Content $_.FullName -Raw
    foreach ($p in $patterns) {
        # from modulox import X  →  from .modulox import X
        $code = [regex]::Replace($code,'(?m)^\s*from\s+'+$p+'(\s+import)','from .'+$p+'$1')
        # import modulox         →  from . import modulox   (caso raro)
        $code = [regex]::Replace($code,'(?m)^\s*import\s+'+$p+'(\s|$)','from . import '+$p+'$1')
    }
    if ($code -ne (Get-Content $_.FullName -Raw)) {
        Set-Content $_.FullName -Value $code
        Write-Host " [FIX ] imports → $($_.Name)"
    }
}

###############################################################################
# 5) Garante que kpis/__init__.py exporte painel_kpis_layout
###############################################################################
$kpisInit = "$PkgName\kpis\__init__.py"
if (-not (Test-Path $kpisInit)) { New-Item -Type File -Path $kpisInit | Out-Null }
$initCode = Get-Content $kpisInit -Raw
if ($initCode -notmatch 'painel_kpis_layout') {
    Add-Content $kpisInit "`n# re-exporta layout principal do painel KPIs`nfrom .kpis import painel_kpis_layout"
    Write-Host " [ADD ] painel_kpis_layout exportado em kpis/__init__.py"
}

###############################################################################
# 6) Move a pasta data/ para app/data (se ainda não estiver lá)
###############################################################################
if ((Test-Path "data") -and (-not (Test-Path "$PkgName\data"))) {
    Move-Item "data" "$PkgName" -Force
    Write-Host " [MOVE] pasta data → $PkgName\data"
}

###############################################################################
Write-Host "`n✅  Tudo pronto! Rode:  python -m $PkgName.main"
###############################################################################
