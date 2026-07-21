. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

Write-Section 'Application ports'
foreach ($port in @(8000, 8080, 8081, 5432, 6379)) {
    $listeners = @(Get-ListeningPortProcesses -Port $port)
    if ($listeners.Count -eq 0) {
        Write-Host "Port ${port}: no listener"
        continue
    }
    Write-Host "Port ${port}:"
    $listeners | Select-Object PID, Name, CommandLine | Format-Table -AutoSize
}

Write-Section 'HTTP checks'
foreach ($url in @('http://localhost:8000/openapi.json', 'http://localhost:8000/attendance/classes/active', 'http://localhost:8080', 'http://localhost:8081')) {
    $status = Get-HttpStatusCode -Url $url -TimeoutSeconds 3
    if ($null -eq $status) {
        Write-Host "$url -> unavailable"
    }
    else {
        Write-Host "$url -> HTTP $status"
    }
}

Write-Section 'Tunnel processes'
$processes = @(Get-Process -Name cloudflared, ngrok -ErrorAction SilentlyContinue)
if ($processes.Count -eq 0) {
    Write-Host 'No active cloudflared/ngrok process found.'
}
else {
    $processes | Select-Object ProcessName, Id, StartTime | Format-Table -AutoSize
}
