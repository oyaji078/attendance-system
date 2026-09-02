param(
    [switch]$KeepDocker,
    [switch]$StopDocker
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

if ($KeepDocker -and $StopDocker) {
    throw 'Choose either -KeepDocker or -StopDocker, not both.'
}
if (-not $KeepDocker -and -not $StopDocker) {
    $KeepDocker = $true
}

Write-Section 'Stopping local processes'
Stop-ProcessByPidFile -PidPath $script:ApiPidFile -Name 'API'
Stop-ExpectedPortProcess -Port 8000 -Kind api
Stop-ProcessByPidFile -PidPath $script:KioskPidFile -Name 'Kiosk UI'
Stop-ExpectedPortProcess -Port 8080 -Kind kiosk

if ($StopDocker) {
    Write-Section 'Stopping Docker infra'
    Stop-Infra
}
else {
    Write-Host 'Docker infra left running. Use .\scripts\stop-dev.ps1 -StopDocker to stop PostgreSQL and Redis.'
}

Write-Section 'Status'
$apiProcesses = @(Get-ListeningPortProcesses -Port 8000)
$kioskProcesses = @(Get-ListeningPortProcesses -Port 8080)
Write-Host "API port 8000 listeners: $($apiProcesses.Count)"
Write-Host "Kiosk port 8080 listeners: $($kioskProcesses.Count)"

if ($apiProcesses.Count -gt 0 -or $kioskProcesses.Count -gt 0) {
    Write-Host 'A forced cleanup was attempted; if a listener still remains, run:' -ForegroundColor Yellow
    Write-Host '  netstat -ano | findstr :8000' -ForegroundColor Yellow
    Write-Host '  netstat -ano | findstr :8080' -ForegroundColor Yellow
}

& docker ps --filter 'name=docker-postgres-1' --filter 'name=docker-redis-1' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

