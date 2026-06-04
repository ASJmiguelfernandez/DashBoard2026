# =====================================================================
#  deploy.ps1 - Despliegue de app.py a producción
#  Uso:  .\deploy.ps1
#  Hace:
#    1) Copia de seguridad con fecha del app.py de producción
#    2) Copia el app.py local a producción
#    3) Estampa version.txt en producción con la fecha/hora del despliegue
#    4) Deja solo las 5 copias de seguridad más recientes
#    5) Verifica por hash que producción == local
# =====================================================================

$ErrorActionPreference = "Stop"

$local = $PSScriptRoot
$prod  = "\\172.16.128.203\miguel.fernandez\comparador_excels"
$retencion = 5

$stampNombre  = Get-Date -Format "yyyyMMdd_HHmmss"   # para el nombre del backup
$stampVersion = Get-Date -Format "yyyy-MM-dd HH:mm"  # para mostrar en el login

Write-Host "== Despldegando a $prod ==" -ForegroundColor Cyan

if (-not (Test-Path "$prod\app.py")) {
    throw "No se encuentra producción ($prod\app.py). ¿Estás conectado a la red?"
}

# 1) Backup
Copy-Item "$prod\app.py" "$prod\app.py.bak.$stampNombre" -Force
Write-Host "1) Backup: app.py.bak.$stampNombre"

# 2) Copiar app.py
Copy-Item "$local\app.py" "$prod\app.py" -Force
Write-Host "2) app.py copiado"

# 3) Estampar version.txt
Set-Content -Path "$prod\version.txt" -Value $stampVersion -Encoding UTF8 -NoNewline
Write-Host "3) version.txt = $stampVersion"

# 4) Podar copias antiguas (conservar las $retencion más recientes)
$bks = Get-ChildItem -Path $prod -Filter "app.py.bak*" -File | Sort-Object LastWriteTime -Descending
$borrar = $bks | Select-Object -Skip $retencion
if ($borrar) {
    $borrar | Remove-Item -Force
    Write-Host "4) Podadas $($borrar.Count) copia(s) antigua(s); se conservan $retencion"
} else {
    Write-Host "4) $($bks.Count) copia(s); nada que podar (<= $retencion)"
}

# 5) Verificación por hash
$lh = (Get-FileHash "$local\app.py" -Algorithm SHA256).Hash
$ph = (Get-FileHash "$prod\app.py"  -Algorithm SHA256).Hash
if ($lh -eq $ph) {
    Write-Host "5) OK - produccion == local (hash $($lh.Substring(0,12))...)" -ForegroundColor Green
} else {
    throw "VERIFICACION FALLIDA: el hash de produccion no coincide con el local."
}

Write-Host "== Despliegue completado ==" -ForegroundColor Green
