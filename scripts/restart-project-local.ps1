param(
    [switch]$RunMigrations
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$stopScript = Join-Path $repoRoot 'scripts\stop-project-local.ps1'
$startScript = Join-Path $repoRoot 'scripts\start-project-local.ps1'

Set-Location -LiteralPath $repoRoot

& powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript -ForceDetectedPorts
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($RunMigrations) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $startScript -RunMigrations
}
else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $startScript
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
