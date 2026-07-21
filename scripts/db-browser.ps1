param(
    [switch]$Detached
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Test-DockerReady

Write-Section 'Adminer'
Write-Host 'URL:      http://localhost:8081'
Write-Host 'System:   PostgreSQL'
Write-Host 'Server:   host.docker.internal:5432'
Write-Host 'Username: attendance'
Write-Host 'Password: attendance'
Write-Host 'Database: attendance'
Write-Host ''
Write-Host 'Fallback server when joining the Docker network: docker-postgres-1'
Write-Host ''

$existing = & docker ps -a --filter 'name=^/attendance-adminer$' --format '{{.Names}}|{{.Status}}'
if ($existing) {
    if ($existing -like '*Up*') {
        Write-Host 'attendance-adminer is already running.'
        exit 0
    }
    & docker rm attendance-adminer | Out-Null
}

if ($Detached) {
    & docker run -d --rm --name attendance-adminer -p 8081:8080 adminer
}
else {
    Write-Host 'Starting Adminer in the foreground. Press Ctrl+C to stop it.'
    & docker run --rm --name attendance-adminer -p 8081:8080 adminer
}

