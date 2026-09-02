<#
.SYNOPSIS
    Restores the transferred data (database dump + kiosk photos) on a new machine.

.DESCRIPTION
    Run this once after cloning the repository on another laptop, following
    scripts\setup-dev.ps1. It starts the Docker infra, restores
    transfer\db\attendance.dump into PostgreSQL, and reports what landed.

    Restoring REPLACES the current contents of the attendance database.
#>
param(
    [string]$DumpFile = '',
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '_dev-common.ps1')

$repoRoot = Get-RepoRoot
if (-not $DumpFile) {
    $DumpFile = Join-Path $repoRoot 'transfer\db\attendance.dump'
}

if (-not (Test-Path -LiteralPath $DumpFile)) {
    throw "Database dump not found: $DumpFile"
}

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

function Invoke-Psql {
    param([Parameter(Mandatory = $true)][string]$Container, [Parameter(Mandatory = $true)][string]$Sql)
    return (& docker exec $Container psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -t -A -c $Sql)
}

Write-Section 'Environment'
Initialize-LocalEnvFile -Path (Join-Path $repoRoot '.env')
Initialize-LocalEnvFile -Path (Join-Path $repoRoot '.env.local-api')
Import-ProjectEnv
Ensure-Directory -Path (Join-Path $repoRoot 'data\object-storage')
Ensure-Directory -Path (Join-Path $repoRoot 'models\insightface')

Write-Section 'Docker infra'
Start-Infra
Wait-PostgresReady

$container = Get-PostgresContainer
Write-Host "PostgreSQL container: $container"

Write-Section 'Existing data'
$existing = '0'
try {
    $existing = (Invoke-Psql -Container $container -Sql "SELECT count(*) FROM persons;").Trim()
}
catch {
    $existing = '0'
}
Write-Host "Rows currently in persons: $existing"

if ([int]$existing -gt 0 -and -not $Force) {
    Write-Host ''
    Write-Host "The database already holds $existing person rows. Restoring will REPLACE them."
    $answer = Read-Host 'Type yes to continue'
    if ($answer -ne 'yes') {
        Write-Host 'Aborted. Nothing was changed.'
        return
    }
}

Write-Section 'Restore database'
$remote = "/tmp/restore-$([guid]::NewGuid().ToString('N')).dump"
& docker cp $DumpFile "${container}:$remote"
if ($LASTEXITCODE -ne 0) { throw 'Failed to copy the dump into the container.' }

& docker exec $container pg_restore --clean --if-exists --no-owner --no-privileges --username $env:POSTGRES_USER --dbname $env:POSTGRES_DB $remote
$restoreExit = $LASTEXITCODE
& docker exec $container rm -f $remote | Out-Null

if ($restoreExit -ne 0) {
    Write-Host ''
    Write-Host "pg_restore exited with code $restoreExit."
    Write-Host 'Warnings about dropping objects that do not exist are expected on a fresh database.'
}

Write-Section 'Verify'
Invoke-Psql -Container $container -Sql "CREATE EXTENSION IF NOT EXISTS vector;" | Out-Null
$vector = (Invoke-Psql -Container $container -Sql "SELECT extname FROM pg_extension WHERE extname = 'vector';").Trim()
Write-Host "pgvector extension: $(if ($vector) { 'present' } else { 'MISSING' })"

foreach ($table in @('persons', 'face_templates', 'face_samples', 'attendance_records', 'admin_users')) {
    $count = (Invoke-Psql -Container $container -Sql "SELECT count(*) FROM $table;").Trim()
    Write-Host ("  {0,-20} {1}" -f $table, $count)
}

$photoRoot = Join-Path $repoRoot 'data\object-storage'
$photoCount = (Get-ChildItem -LiteralPath $photoRoot -Recurse -File -Filter '*.jpg' -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host ("  {0,-20} {1}" -f 'photos on disk', $photoCount)

$modelRoot = Join-Path $repoRoot 'models\insightface'
$modelFiles = (Get-ChildItem -LiteralPath $modelRoot -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count

Write-Section 'Next steps'
if ($modelFiles -eq 0) {
    Write-Host 'InsightFace model is missing. Download it before starting the app:'
    Write-Host '  powershell -ExecutionPolicy Bypass -File .\scripts\download-insightface-buffalo-l.ps1'
}
else {
    Write-Host "InsightFace model present ($modelFiles files)."
}
Write-Host 'Start the app:'
Write-Host '  powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1'
