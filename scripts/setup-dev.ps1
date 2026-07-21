param(
    [switch]$InstallPythonDeps,
    [switch]$InstallFrontendDeps,
    [switch]$SkipMigrations
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

Write-Section 'Environment files'
Initialize-LocalEnvFile -Path (Join-Path (Get-RepoRoot) '.env')
Initialize-LocalEnvFile -Path (Join-Path (Get-RepoRoot) '.env.local-api')
Import-ProjectEnv

Write-Section 'Tool checks'
$python = Resolve-ProjectPython
Write-Host "Python: $python"
& $python --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python check failed.'
}

Test-DockerReady
Write-Host 'Docker: available'

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Host "Node: $($node.Source)"
    & node --version
}
else {
    Write-Host 'Node: not found; kiosk UI currently runs as static files, so Node is optional.'
}

if ($InstallPythonDeps) {
    Write-Section 'Python dependencies'
    & $python -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) {
        throw 'Python dependency installation failed.'
    }
}

if ($InstallFrontendDeps) {
    Write-Section 'Frontend dependencies'
    $frontendPackage = Join-Path (Get-RepoRoot) 'apps\kiosk-ui\package.json'
    $rootPackage = Join-Path (Get-RepoRoot) 'package.json'
    if (Test-Path -LiteralPath $frontendPackage) {
        & npm install --prefix (Split-Path -Parent $frontendPackage)
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    elseif (Test-Path -LiteralPath $rootPackage) {
        & npm install
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    else {
        Write-Host 'No package.json found. Skipping frontend dependency installation.'
    }
}

Write-Section 'Docker infra'
Start-Infra
Wait-PostgresReady
Wait-RedisReady

if (-not $SkipMigrations) {
    Write-Section 'Database migrations'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Get-RepoRoot) 'scripts\migrate.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw 'Migration failed.'
    }
}

Write-Section 'Next commands'
Write-Host 'Start development stack: .\scripts\start-dev.ps1'
Write-Host 'Stop development stack:  .\scripts\stop-dev.ps1'
Write-Host 'API docs:                http://localhost:8000/docs'
Write-Host 'Kiosk UI:                http://localhost:8080'

