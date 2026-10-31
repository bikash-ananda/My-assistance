$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root ".runtime/service-pids.json"
if (-not (Test-Path $pidFile)) { Write-Host "No Bikash AI process list was found."; exit 0 }
$entries = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
foreach ($entry in $entries) {
  $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.ProcessId)" -ErrorAction SilentlyContinue
  if (-not $processInfo) { continue }
  $currentProcess = Get-Process -Id $entry.ProcessId -ErrorAction SilentlyContinue
  if (-not $currentProcess -or $currentProcess.StartTime.ToUniversalTime().Ticks -ne [long]$entry.StartTicks) { continue }
  $commandLine = [string]$processInfo.CommandLine
  $owned = ($commandLine.Contains("uvicorn") -and $commandLine.Contains("app.main:app")) -or ($commandLine.Contains("app.worker")) -or $commandLine.Contains("start-web-loopback.cjs")
  if ($owned) { Stop-Process -Id $entry.ProcessId -Force -ErrorAction SilentlyContinue }
}
Remove-Item -LiteralPath $pidFile -Force
Write-Host "Bikash AI services stopped. Logs remain in .runtime/logs."
