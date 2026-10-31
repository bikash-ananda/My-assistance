$ErrorActionPreference = "Stop"
$taskName = "Bikash AI Local Workspace"
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
  $task = Get-ScheduledTask -TaskName $taskName
  if (-not (($task.Actions | ForEach-Object { $_.Arguments }) -match "start-local\.ps1")) { throw "The existing task does not point to Bikash AI's local launcher; it was left untouched." }
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Host "Bikash AI startup task removed."
} else { Write-Host "No Bikash AI startup task was registered." }
