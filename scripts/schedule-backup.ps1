[CmdletBinding()]
param(
    [string]$Time = '02:00',
    [switch]$Unregister
)

# Registers (or removes) a daily Windows Task Scheduler job that runs
# backup-db.ps1. Run from an elevated PowerShell.

$taskName = 'AttendanceSystem-DailyDbBackup'
$repoRoot = Split-Path -Parent $PSScriptRoot
$backupScript = Join-Path $repoRoot 'scripts\backup-db.ps1'

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Scheduled task '$taskName' removed (if it existed)."
    exit 0
}

if (-not (Test-Path -LiteralPath $backupScript)) {
    throw "backup-db.ps1 not found at $backupScript"
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$backupScript`"" `
    -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description 'Daily PostgreSQL backup for the attendance system' -Force | Out-Null

Write-Host "Scheduled task '$taskName' registered: daily at $Time -> $backupScript"
Write-Host "Backups are written to $repoRoot\backups (keep an eye on disk usage)."
