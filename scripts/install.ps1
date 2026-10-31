$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $env:LOCALAPPDATA "Programs/Python/Python314/python.exe"
if (-not (Test-Path $python)) { throw "Python 3.14.10 was not found at its approved per-user install path." }
$venv = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $venv)) { & $python -m venv (Join-Path $root ".venv") }
& $venv -m pip install --disable-pip-version-check -r services/api/requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw "Python package installation failed." }
Push-Location (Join-Path $root "apps/web")
try {
  npm install --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw "Web package installation failed." }
} finally { Pop-Location }
Write-Host "Dependencies are ready. Next run ./scripts/setup.ps1 once, then start the API and web app in separate terminals."
