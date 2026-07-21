param(
    [switch]$DryRun,
    [switch]$Execute,
    [switch]$BackupFirst
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)
Import-ProjectEnv
Test-DockerReady

if ($DryRun -and $Execute) {
    throw 'Choose either -DryRun or -Execute, not both.'
}
if (-not $DryRun -and -not $Execute) {
    $DryRun = $true
}
if ($Execute -and -not $BackupFirst) {
    throw 'Execute mode requires -BackupFirst.'
}

$timestamp = Get-Timestamp
$reportDir = Join-Path (Get-RepoRoot) 'reports\cleanup'
Ensure-Directory -Path $reportDir
$reportPath = Join-Path $reportDir "face-data-cleanup-$timestamp.md"

function Invoke-PsqlText {
    param([Parameter(Mandatory = $true)][string]$Sql)

    $output = & docker exec -i docker-postgres-1 psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -t -A -v ON_ERROR_STOP=1 -c $Sql
    if ($LASTEXITCODE -ne 0) {
        throw 'psql command failed.'
    }
    return @($output)
}

function Get-Count {
    param([Parameter(Mandatory = $true)][string]$Sql)
    $value = Invoke-PsqlText -Sql $Sql | Select-Object -First 1
    if (-not $value) { return 0 }
    return [int]$value
}

function Get-RedisCount {
    param([Parameter(Mandatory = $true)][string]$Pattern)

    $cursor = '0'
    $count = 0
    do {
        $scan = @(& docker exec docker-redis-1 redis-cli SCAN $cursor MATCH $Pattern COUNT 100)
        if ($LASTEXITCODE -ne 0 -or $scan.Count -lt 1) {
            return 0
        }
        $cursor = [string]$scan[0]
        if ($scan.Count -gt 1) {
            $count += ($scan.Count - 1)
        }
    } while ($cursor -ne '0')
    return $count
}

$counts = [ordered]@{
    'Inactive face templates' = Get-Count "SELECT count(*) FROM face_templates WHERE is_active = false OR deleted_at IS NOT NULL;"
    'Templates linked to inactive/deleted/missing persons' = Get-Count "SELECT count(*) FROM face_templates ft LEFT JOIN persons p ON p.id = ft.person_id WHERE p.id IS NULL OR p.is_active = false OR p.is_deleted = true OR p.deleted_at IS NOT NULL;"
    'Inactive/deleted face samples' = Get-Count "SELECT count(*) FROM face_samples WHERE is_active = false OR is_deleted = true OR deleted_at IS NOT NULL;"
    'Samples linked to inactive/deleted/missing persons' = Get-Count "SELECT count(*) FROM face_samples fs LEFT JOIN persons p ON p.id = fs.person_id WHERE p.id IS NULL OR p.is_active = false OR p.is_deleted = true OR p.deleted_at IS NOT NULL;"
    'Face samples with missing enrollment session' = Get-Count "SELECT count(*) FROM face_samples fs LEFT JOIN attendance_sessions s ON s.id = fs.enrollment_session_id WHERE fs.enrollment_session_id IS NOT NULL AND s.id IS NULL;"
    'Face templates with missing built_from_session' = Get-Count "SELECT count(*) FROM face_templates ft LEFT JOIN attendance_sessions s ON s.id = ft.built_from_session_id WHERE ft.built_from_session_id IS NOT NULL AND s.id IS NULL;"
    'Accepted attendance logs not deleted' = Get-Count "SELECT count(*) FROM attendance_logs WHERE decision = 'accepted' AND is_deleted = false;"
    'Redis enrollment keys' = Get-RedisCount 'enrollment:*'
    'Redis cooldown keys' = Get-RedisCount 'cooldown:*'
    'Redis recent-match keys' = Get-RedisCount 'recent-match:*'
    'Redis color-challenge keys' = Get-RedisCount 'color-challenge:*'
}

$objectRoot = if ($env:OBJECT_STORAGE_ROOT) { $env:OBJECT_STORAGE_ROOT } else { './data/object-storage' }
if (-not [System.IO.Path]::IsPathRooted($objectRoot)) {
    $objectRoot = Join-Path (Get-RepoRoot) $objectRoot
}
$objectRoot = [System.IO.Path]::GetFullPath($objectRoot)
$allObjectFiles = @()
if (Test-Path -LiteralPath $objectRoot) {
    $allObjectFiles = @(Get-ChildItem -LiteralPath $objectRoot -Recurse -File -ErrorAction SilentlyContinue)
}

$referencedUris = @(
    Invoke-PsqlText -Sql "SELECT image_uri FROM face_samples WHERE image_uri IS NOT NULL UNION SELECT captured_image_uri FROM attendance_logs WHERE captured_image_uri IS NOT NULL;"
)
$referencedPaths = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($uri in $referencedUris) {
    if (-not $uri) { continue }
    $path = [string]$uri
    if (-not [System.IO.Path]::IsPathRooted($path)) {
        $path = Join-Path $objectRoot $path
    }
    try {
        [void]$referencedPaths.Add([System.IO.Path]::GetFullPath($path).ToLowerInvariant())
    }
    catch {
        continue
    }
}

$unreferencedFiles = @()
foreach ($file in $allObjectFiles) {
    $normalized = $file.FullName.ToLowerInvariant()
    if (-not $referencedPaths.Contains($normalized)) {
        $unreferencedFiles += $file
    }
}

$executionOutput = @()
if ($Execute) {
    Write-Section 'Backup'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Get-RepoRoot) 'scripts\backup-db.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw 'Backup failed. Cleanup was not executed.'
    }

    Write-Section 'Execute cleanup'
    $sql = @"
BEGIN;

WITH template_candidates AS (
    SELECT ft.id
    FROM face_templates ft
    LEFT JOIN persons p ON p.id = ft.person_id
    WHERE ft.is_active = false
       OR ft.deleted_at IS NOT NULL
       OR p.id IS NULL
       OR p.is_active = false
       OR p.is_deleted = true
       OR p.deleted_at IS NOT NULL
),
updated_templates AS (
    UPDATE face_templates ft
    SET is_active = false,
        deleted_at = COALESCE(ft.deleted_at, now()),
        updated_at = now()
    FROM template_candidates c
    WHERE ft.id = c.id
    RETURNING ft.id
),
sample_candidates AS (
    SELECT fs.id
    FROM face_samples fs
    LEFT JOIN persons p ON p.id = fs.person_id
    WHERE fs.is_active = false
       OR fs.is_deleted = true
       OR fs.deleted_at IS NOT NULL
       OR p.id IS NULL
       OR p.is_active = false
       OR p.is_deleted = true
       OR p.deleted_at IS NOT NULL
),
updated_samples AS (
    UPDATE face_samples fs
    SET is_active = false,
        is_deleted = true,
        deleted_at = COALESCE(fs.deleted_at, now())
    FROM sample_candidates c
    WHERE fs.id = c.id
    RETURNING fs.id
)
SELECT
    (SELECT count(*) FROM updated_templates)::text || ' templates inactivated' AS result
UNION ALL
SELECT
    (SELECT count(*) FROM updated_samples)::text || ' samples soft-deleted' AS result;

COMMIT;
"@
    $executionOutput = Invoke-PsqlText -Sql $sql
    $executionOutput | ForEach-Object { Write-Host $_ }
}

$mode = if ($Execute) { 'EXECUTE' } else { 'DRY RUN' }
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# FACE DATA CLEANUP $mode")
$lines.Add('')
$lines.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$lines.Add('')
$lines.Add('| Category | Count | Action Proposed | Risk |')
$lines.Add('|---|---:|---|---|')
$lines.Add("| Inactive face templates | $($counts['Inactive face templates']) | Inactivate and stamp deleted_at | Low |")
$lines.Add("| Templates linked to inactive/deleted/missing persons | $($counts['Templates linked to inactive/deleted/missing persons']) | Inactivate and stamp deleted_at | Medium |")
$lines.Add("| Inactive/deleted face samples | $($counts['Inactive/deleted face samples']) | Soft-delete and stamp deleted_at | Low |")
$lines.Add("| Samples linked to inactive/deleted/missing persons | $($counts['Samples linked to inactive/deleted/missing persons']) | Soft-delete and stamp deleted_at | Medium |")
$lines.Add("| Face samples with missing enrollment session | $($counts['Face samples with missing enrollment session']) | Report only; FK should SET NULL | Medium |")
$lines.Add("| Face templates with missing built_from_session | $($counts['Face templates with missing built_from_session']) | Report only; FK should SET NULL | Medium |")
$lines.Add("| Accepted attendance logs not deleted | $($counts['Accepted attendance logs not deleted']) | No action | Protected |")
$lines.Add("| Redis enrollment keys | $($counts['Redis enrollment keys']) | Report only in this script version | Medium |")
$lines.Add("| Redis cooldown keys | $($counts['Redis cooldown keys']) | No action | Protected |")
$lines.Add("| Redis recent-match keys | $($counts['Redis recent-match keys']) | No action | Protected |")
$lines.Add("| Redis color-challenge keys | $($counts['Redis color-challenge keys']) | No action | Protected |")
$lines.Add("| Object storage files | $($allObjectFiles.Count) | Report only | Medium |")
$lines.Add("| Unreferenced object storage files | $($unreferencedFiles.Count) | Report only; no file deletion | Medium |")
$lines.Add('')
$lines.Add('## Execution')
if ($Execute) {
    $lines.Add('Mode: execute')
    $lines.Add('Backup was required and attempted before cleanup.')
    foreach ($line in $executionOutput) {
        $lines.Add("- $line")
    }
    $lines.Add('')
    $lines.Add('Rollback note: restore the latest backups/attendance_*.dump if cleanup must be reverted.')
}
else {
    $lines.Add('Mode: dry-run. No database rows, Redis keys, or files were changed.')
}
$lines.Add('')
$lines.Add('## Object Storage Samples')
$lines.Add('Unreferenced files are listed for review only; this script does not delete files.')
foreach ($file in ($unreferencedFiles | Select-Object -First 20)) {
    $lines.Add("- $($file.FullName)")
}

Set-Content -LiteralPath $reportPath -Value $lines -Encoding ASCII
Write-Host "Cleanup report written: $reportPath"

