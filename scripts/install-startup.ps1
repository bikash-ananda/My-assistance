$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $PSScriptRoot "start-local.ps1"
$taskName = "Bikash AI Local Workspace"
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw "A scheduled task with this name already exists; inspect it before changing it." }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Description "Start the owner's Bikash AI local services at sign-in." | Out-Null
Write-Host "Startup task registered for this Windows user. Remove it with scripts/uninstall-startup.ps1."
