param(
    [switch]$DryRun,
    [switch]$Archive,
    [switch]$Delete,
    [switch]$ConfirmDelete,
    [int]$OlderThanDays = 30
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

$selectedModes = @($DryRun, $Archive, $Delete) | Where-Object { $_ }
if ($selectedModes.Count -gt 1) {
    throw 'Choose only one mode: -DryRun, -Archive, or -Delete.'
}
if (-not $DryRun -and -not $Archive -and -not $Delete) {
    $DryRun = $true
}
if ($Delete -and -not $ConfirmDelete) {
    throw 'Delete mode requires -ConfirmDelete. Prefer -Archive.'
}

$timestamp = Get-Timestamp
$dateStamp = (Get-Date).ToString('yyyyMMdd')
$reportDir = Join-Path (Get-RepoRoot) 'reports\cleanup'
Ensure-Directory -Path $reportDir
$reportPath = Join-Path $reportDir "report-cleanup-$timestamp.md"
$archiveRoot = Join-Path (Get-RepoRoot) "archive\reports\$dateStamp"

$knownGeneratedReports = @(
    'README_PORTABLE_MIGRATION.md',
    'migration_report.md',
    'storage-audit-report.txt',
    'technical-project-audit-report.md',
    'technical-project-audit-report-updated.md',
    'technical-remediation-report.md',
    'docs\fixes\final_project_stabilization_report.md'
)

$candidates = New-Object System.Collections.Generic.List[object]
foreach ($relative in $knownGeneratedReports) {
    $path = Join-Path (Get-RepoRoot) $relative
    if (Test-Path -LiteralPath $path) {
        $candidates.Add([pscustomobject]@{
            RelativePath = $relative
            FullPath = [System.IO.Path]::GetFullPath($path)
            Type = 'known generated report'
            Reason = 'Historical generated report, not required to run the project'
        })
    }
}

$cutoff = (Get-Date).AddDays(-1 * $OlderThanDays)
$reportsRoot = Join-Path (Get-RepoRoot) 'reports'
if (Test-Path -LiteralPath $reportsRoot) {
    Get-ChildItem -LiteralPath $reportsRoot -File -Filter '*.md' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object {
            $relative = [System.IO.Path]::GetRelativePath((Get-RepoRoot), $_.FullName)
            $candidates.Add([pscustomobject]@{
                RelativePath = $relative
                FullPath = $_.FullName
                Type = 'old generated report'
                Reason = "Older than $OlderThanDays days"
            })
        }
}

$lines = New-Object System.Collections.Generic.List[string]
$mode = if ($Archive) { 'ARCHIVE' } elseif ($Delete) { 'DELETE' } else { 'DRY RUN' }
$lines.Add("# REPORT CLEANUP $mode")
$lines.Add('')
$lines.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$lines.Add('')
$lines.Add('| File | Type | Action | Reason |')
$lines.Add('|---|---|---|---|')

foreach ($candidate in $candidates) {
    $action = if ($Archive) { 'Archive' } elseif ($Delete) { 'Delete' } else { 'Review only' }
    $lines.Add("| $($candidate.RelativePath) | $($candidate.Type) | $action | $($candidate.Reason) |")
}

Set-Content -LiteralPath $reportPath -Value $lines -Encoding ASCII
Write-Host "Candidate report written: $reportPath"

if ($Archive) {
    foreach ($candidate in $candidates) {
        $targetPath = Join-Path $archiveRoot $candidate.RelativePath
        $targetDir = Split-Path -Parent $targetPath
        Ensure-Directory -Path $targetDir
        Move-Item -LiteralPath $candidate.FullPath -Destination $targetPath -Force
        Write-Host "Archived $($candidate.RelativePath) -> $targetPath"
    }
}
elseif ($Delete) {
    foreach ($candidate in $candidates) {
        Remove-Item -LiteralPath $candidate.FullPath -Force
        Write-Host "Deleted $($candidate.RelativePath)"
    }
}
else {
    Write-Host 'Dry-run only. No files were moved or deleted.'
}
