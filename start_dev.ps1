# Dev launcher (Windows): backend (sim vehicle) + Vite dev server with hot reload.
#
#   .\start_dev.ps1            # sim data
#   .\start_dev.ps1 elm327     # real adapter plugged into this machine
#
# First run bootstraps the venv and node_modules automatically.
# Native HUD opens in a 640x480 window (mirroring off for readability).
# Phone pages with hot reload: http://localhost:5173/settings/
param([string]$Source = "sim")

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Port = 8000  # vite.config.ts proxies /ws and /api to this port

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "==> first run: creating .venv and installing python deps"
    python -m venv .venv
    & $py -m pip install -q -e ".[dev,ui]"
}

if (-not (Test-Path "web\node_modules")) {
    Write-Host "==> first run: installing frontend deps"
    Push-Location web
    npm install --no-fund --no-audit
    Pop-Location
}

Write-Host "==> backend on :$Port (vehicle source: $Source)"
$backend = Start-Process -FilePath $py -ArgumentList "-m", "hud", "--ui", "--mirror", "off", "--source", $Source, "--port", "$Port" `
    -PassThru -NoNewWindow

Write-Host "==> vite dev server for the phone pages - http://localhost:5173/settings/"
try {
    Set-Location web
    npm run dev
}
finally {
    # runs on Ctrl-C too - take the backend down with us
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
    Set-Location $PSScriptRoot
}
