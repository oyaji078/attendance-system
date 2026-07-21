param(
    [string]$BackupDir = 'backups'
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)
Import-ProjectEnv
Test-DockerReady

$backupRoot = if ([System.IO.Path]::IsPathRooted($BackupDir)) { $BackupDir } else { Join-Path (Get-RepoRoot) $BackupDir }
Ensure-Directory -Path $backupRoot

$timestamp = Get-Timestamp
$fileName = "attendance_$timestamp.dump"
$backupPath = Join-Path $backupRoot $fileName
$containerPath = "/tmp/$fileName"

Write-Section 'Database backup'
& docker exec docker-postgres-1 pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB -Fc -f $containerPath
if ($LASTEXITCODE -ne 0) {
    throw 'pg_dump failed.'
}

& docker cp "docker-postgres-1:$containerPath" $backupPath
if ($LASTEXITCODE -ne 0) {
    throw 'docker cp failed while copying database backup.'
}

& docker exec docker-postgres-1 rm -f $containerPath | Out-Null

$backupFile = Get-Item -LiteralPath $backupPath
if ($backupFile.Length -le 0) {
    throw "Backup file is empty: $backupPath"
}

Write-Host "Backup created: $backupPath"

