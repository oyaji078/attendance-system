param(
    [string]$ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$ComposeFile = '',
    [string]$BackupDir = '',
    [string]$BackupFile = '',
    [switch]$Restore,
    [switch]$StartCompose
)

$ErrorActionPreference = 'Stop'

function Read-EnvFile {
    param([string]$Path)
    $map = @{}
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in Get-Content -LiteralPath $Path) {
            if ($line -match '^\s*([^#][A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
                $map[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
            }
        }
    }
    return $map
}

function Invoke-Docker {
    param([string[]]$Args)
    Write-Host ">> docker $($Args -join ' ')"
    & docker @Args
    if ($LASTEXITCODE -ne 0) { throw "docker command failed: docker $($Args -join ' ')" }
}

$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ComposeFile) { $ComposeFile = Join-Path $ProjectPath 'docker\docker-compose.yml' }
if (-not $BackupDir) { $BackupDir = Join-Path $ProjectPath 'backups\postgres' }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$env = Read-EnvFile (Join-Path $ProjectPath 'docker\compose.env')
$db = if ($env.POSTGRES_DB) { $env.POSTGRES_DB } else { 'attendance' }
$user = if ($env.POSTGRES_USER) { $env.POSTGRES_USER } else { 'attendance' }

if ($StartCompose) {
    Invoke-Docker @('compose','-f',$ComposeFile,'up','-d','postgres')
}

$containerId = ''
try {
    $containerId = (& docker compose -f $ComposeFile ps -q postgres 2>$null).Trim()
} catch { }
if (-not $containerId) {
    $containerId = (& docker ps --filter 'name=attendance-postgres' --format '{{.ID}}' 2>$null | Select-Object -First 1).Trim()
}
if (-not $containerId) {
    throw 'PostgreSQL container is not running. Start Docker Desktop and the compose postgres service first.'
}

Write-Host "Using PostgreSQL container: $containerId"
Write-Host "Database: $db User: $user"

if ($Restore) {
    if (-not $BackupFile -or -not (Test-Path -LiteralPath $BackupFile)) {
        throw 'Restore requires -BackupFile pointing to an existing .dump file.'
    }
    $remote = "/tmp/restore-$([guid]::NewGuid().ToString('N')).dump"
    Invoke-Docker @('cp',$BackupFile,"${containerId}:$remote")
    Invoke-Docker @('exec',$containerId,'pg_restore','--clean','--if-exists','--no-owner','--username',$user,'--dbname',$db,$remote)
    Invoke-Docker @('exec',$containerId,'rm','-f',$remote)
} else {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $BackupFile = Join-Path $BackupDir "postgres-$db-$stamp.dump"
    Invoke-Docker @('exec',$containerId,'pg_dump','--format=custom','--no-owner','--username',$user,'--dbname',$db,'--file','/tmp/attendance.dump')
    Invoke-Docker @('cp',"${containerId}:/tmp/attendance.dump",$BackupFile)
    Invoke-Docker @('exec',$containerId,'rm','-f','/tmp/attendance.dump')
    Write-Host "Backup written: $BackupFile"
}

Write-Host 'Verifying pgvector extension'
Invoke-Docker @('exec',$containerId,'psql','--username',$user,'--dbname',$db,'-c','CREATE EXTENSION IF NOT EXISTS vector;')
Invoke-Docker @('exec',$containerId,'psql','--username',$user,'--dbname',$db,'-c',"SELECT extname FROM pg_extension WHERE extname = 'vector';")
