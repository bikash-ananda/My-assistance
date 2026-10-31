$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root ".env"))) { throw "Run scripts/setup.ps1 and create your owner password first." }
$python = Join-Path $root ".venv/Scripts/python.exe"
$node = (Get-Command node.exe -ErrorAction Stop).Source
$webRoot = Join-Path $root "apps/web"
$runtime = Join-Path $root ".runtime"
$logs = Join-Path $runtime "logs"
New-Item -ItemType Directory -Path $logs -Force | Out-Null
if (-not (Test-Path $python)) { throw "Run scripts/install.ps1 first." }
if (-not (Test-Path (Join-Path $webRoot "node_modules"))) { throw "Run scripts/install.ps1 first." }
if (-not (Test-Path (Join-Path $webRoot ".next/standalone/server.js"))) {
  Push-Location $webRoot
  try { npm run build; if ($LASTEXITCODE -ne 0) { throw "Web production build failed." } }
  finally { Pop-Location }
}
$standalone = Join-Path $webRoot ".next/standalone"
$standaloneStatic = Join-Path $standalone ".next/static"
$sourceStatic = Join-Path $webRoot ".next/static"
$standalonePublic = Join-Path $standalone "public"
New-Item -ItemType Directory -Path $standaloneStatic,$standalonePublic -Force | Out-Null
Get-ChildItem -LiteralPath $sourceStatic -Force | Copy-Item -Destination $standaloneStatic -Recurse -Force
Get-ChildItem -LiteralPath (Join-Path $webRoot "public") -Force | Copy-Item -Destination $standalonePublic -Recurse -Force
foreach ($port in @(8000, 3000)) {
  $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($listener) { throw "Port $port is already in use. Check the existing service before starting Bikash AI." }
}
$started = @()
try {
  $started += Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "services/api", "--host", "127.0.0.1", "--port", "8000", "--no-access-log") -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "api.log") -RedirectStandardError (Join-Path $logs "api-error.log")
  $started += Start-Process -FilePath $node -ArgumentList @("scripts/start-web-loopback.cjs") -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "web.log") -RedirectStandardError (Join-Path $logs "web-error.log")
  $started += Start-Process -FilePath $python -ArgumentList @("-m", "app.worker", "--poll-seconds", "5") -WorkingDirectory (Join-Path $root "services/api") -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "worker.log") -RedirectStandardError (Join-Path $logs "worker-error.log")
  $deadline = (Get-Date).AddSeconds(30)
  $ready = $false
  while ((Get-Date) -lt $deadline) {
    try {
      Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready" -TimeoutSec 2 | Out-Null
      Invoke-WebRequest -Uri "http://127.0.0.1:3000" -TimeoutSec 2 | Out-Null
      $ready = $true
      break
    } catch { Start-Sleep -Seconds 1 }
  }
  if (-not $ready) { throw "Local services did not become ready. Review .runtime/logs." }
  $pidEntries = @($started | ForEach-Object { [pscustomobject]@{ ProcessId = $_.Id; StartTicks = $_.StartTime.ToUniversalTime().Ticks } })
  ConvertTo-Json -InputObject $pidEntries | Set-Content -LiteralPath (Join-Path $runtime "service-pids.json") -Encoding utf8
  Write-Host "Bikash AI is running at http://127.0.0.1:3000. Logs: .runtime/logs"
} catch {
  foreach ($process in $started) { if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } }
  throw
}
