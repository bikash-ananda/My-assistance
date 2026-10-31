param([Parameter(Mandatory = $true)][string]$BackupPath)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) { throw "Run Python setup first." }
& $python scripts/database_maintenance.py restore --from $BackupPath
