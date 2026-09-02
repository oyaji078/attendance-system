<#
.SYNOPSIS
    Refreshes transfer\db\attendance.dump from the running database.

.DESCRIPTION
    Run this on the machine that holds the current data, before committing and
    pushing, so the other laptop can pull an up-to-date snapshot. Kiosk photos
    under data\object-storage are tracked by git directly and need no export.
#>
param(
    [string]$DumpFile = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '_dev-common.ps1')

$repoRoot = Get-RepoRoot
if (-not $DumpFile) {
    $DumpFile = Join-Path $repoRoot 'transfer\db\attendance.dump'
}
Ensure-Directory -Path (Split-Path -Parent $DumpFile)

function Get-PostgresContainer {
    $id = ''
    try {
        $id = (& docker compose -f (Join-Path (Get-RepoRoot) 'docker\docker-compose.infra.yml') ps -q postgres 2>$null | Select-Object -First 1)
    }
    catch { }

    if ($id) {
        return $id.Trim()
    }

    foreach ($name in @('docker-postgres-1', 'attendance-postgres')) {
        $found = (& docker ps --filter "name=$name" --format '{{.ID}}' 2>$null | Select-Object -First 1)
        if ($found) {
            return $found.Trim()
        }
    }

    throw 'PostgreSQL container is not running. Start Docker Desktop and retry.'
}

Import-ProjectEnv

Write-Section 'Docker infra'
Start-Infra
Wait-PostgresReady
$container = Get-PostgresContainer
Write-Host "PostgreSQL container: $container"

Write-Section 'Export database'
$remote = "/tmp/export-$([guid]::NewGuid().ToString('N')).dump"
& docker exec $container pg_dump --format=custom --no-owner --no-privileges --compress=9 --username $env:POSTGRES_USER --dbname $env:POSTGRES_DB --file $remote
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed.' }

& docker cp "${container}:$remote" $DumpFile
if ($LASTEXITCODE -ne 0) { throw 'Failed to copy the dump out of the container.' }
& docker exec $container rm -f $remote | Out-Null

$size = [math]::Round((Get-Item -LiteralPath $DumpFile).Length / 1MB, 2)
Write-Host "Dump written: $DumpFile ($size MB)"

$photoRoot = Join-Path $repoRoot 'data\object-storage'
$photoCount = (Get-ChildItem -LiteralPath $photoRoot -Recurse -File -Filter '*.jpg' -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "Photos tracked under data\object-storage: $photoCount"

Write-Section 'Next steps'
Write-Host 'Commit and push so the other laptop can pull:'
Write-Host '  git add -A'
Write-Host '  git commit -m "Update transferred data"'
Write-Host '  git push'
