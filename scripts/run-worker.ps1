$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "services/api")
$python = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) { throw "Run Python setup first." }
& $python -m app.worker --poll-seconds 5
