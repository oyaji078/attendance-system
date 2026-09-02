param(
    [switch]$Detached
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Test-DockerReady

Write-Section 'Adminer'

# Adminer defaults to the 'bridge' network while the infra stack sits on its own
# compose network, so the container name only resolves if Adminer joins it too.
$infraNetwork = $null
$networkList = & docker inspect docker-postgres-1 --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>$null
if ($LASTEXITCODE -eq 0 -and $networkList) {
    $infraNetwork = @($networkList -split '\s+' | Where-Object { $_ }) | Select-Object -First 1
}

Write-Host 'URL:      http://localhost:8081'
Write-Host 'System:   PostgreSQL'
Write-Host 'Server:   host.docker.internal:5432'
Write-Host 'Username: attendance'
Write-Host 'Password: attendance'
Write-Host 'Database: attendance'
Write-Host ''
if ($infraNetwork) {
    Write-Host "Fallback server (Adminer joins network '$infraNetwork'): docker-postgres-1:5432"
}
else {
    Write-Host 'Postgres is not running, so only host.docker.internal:5432 will work.'
    Write-Host 'Start it first with .\scripts\start-dev.ps1.'
}
Write-Host ''

$existing = & docker ps -a --filter 'name=^/attendance-adminer$' --format '{{.Names}}|{{.Status}}'
if ($existing) {
    if ($existing -like '*Up*') {
        Write-Host 'attendance-adminer is already running.'
        exit 0
    }
    & docker rm attendance-adminer | Out-Null
}

$runArgs = @('--rm', '--name', 'attendance-adminer', '-p', '8081:8080')
if ($infraNetwork) {
    $runArgs += @('--network', $infraNetwork)
}

if ($Detached) {
    & docker run -d @runArgs adminer
}
else {
    Write-Host 'Starting Adminer in the foreground. Press Ctrl+C to stop it.'
    & docker run @runArgs adminer
}

