$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "apps/web")
npm run dev -- --hostname 127.0.0.1