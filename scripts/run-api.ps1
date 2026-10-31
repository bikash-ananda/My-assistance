$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) { throw "Run Python setup first." }
& $python -m uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --no-access-log
