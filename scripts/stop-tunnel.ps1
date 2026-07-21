param(
    [switch]$All
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

Write-Section 'Stopping tunnel processes'
Stop-ProcessByPidFile -PidPath (Join-Path $script:RuntimeDir 'cloudflared.pid') -Name 'Cloudflare tunnel'
Stop-ProcessByPidFile -PidPath (Join-Path $script:RuntimeDir 'ngrok.pid') -Name 'ngrok tunnel'

if ($All) {
    foreach ($name in @('cloudflared', 'ngrok')) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "Stopping $name process $($_.Id)."
            Stop-Process -Id $_.Id -Force
        }
    }
}

Write-Section 'Remaining tunnel processes'
$remaining = @(Get-Process -Name cloudflared, ngrok -ErrorAction SilentlyContinue)
if ($remaining.Count -eq 0) {
    Write-Host 'No cloudflared/ngrok process remains.'
}
else {
    $remaining | Select-Object ProcessName, Id, StartTime | Format-Table -AutoSize
}

Write-Section 'Application ports'
foreach ($port in @(8000, 8080, 8081, 5432, 6379)) {
    $listeners = @(Get-ListeningPortProcesses -Port $port)
    Write-Host "Port $port listeners: $($listeners.Count)"
}

