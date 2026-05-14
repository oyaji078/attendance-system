Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = 'D:\PythonVenvs\attendance-api'
$pythonExe = Join-Path $venvRoot 'Scripts\python.exe'
$modelDir = 'D:\cnn\attendance-system\models'
$dataDir = 'D:\cnn\attendance-system\data'
$composeFile = 'docker/docker-compose.infra.yml'
$failed = 0

function Write-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Ok,
        [string]$Detail = ''
    )

    if ($Ok) {
        Write-Host "[OK]   $Name $Detail"
    }
    else {
        Write-Host "[FAIL] $Name $Detail"
        $script:failed += 1
    }
}

Set-Location -LiteralPath $repoRoot

Write-Host "Local setup check"
Write-Host "Repo: $repoRoot"
Write-Host ''

$dockerReady = $false
try {
    docker info *> $null
    $dockerReady = $true
}
catch {
    $dockerReady = $false
}
Write-Check -Name 'Docker daemon reachable via docker info' -Ok $dockerReady

$composeReady = $false
try {
    docker compose version *> $null
    $composeReady = $true
}
catch {
    $composeReady = $false
}
Write-Check -Name 'Docker Compose plugin available' -Ok $composeReady

$venvExists = Test-Path -LiteralPath $pythonExe
Write-Check -Name 'Venv python exists' -Ok $venvExists -Detail $pythonExe

if ($venvExists) {
$importCode = @'
import importlib
import sys

modules = ['numpy', 'cv2', 'onnxruntime', 'insightface', 'fastapi', 'sqlalchemy', 'asyncpg', 'redis']
failed = []

for module in modules:
    try:
        importlib.import_module(module)
    except Exception as exc:
        failed.append('%s: %r' % (module, exc))

if failed:
    print('\n'.join(failed))
    sys.exit(1)

print('imports ok: ' + ', '.join(modules))
'@

    & $pythonExe -c $importCode
    Write-Check -Name 'Python dependencies importable' -Ok ($LASTEXITCODE -eq 0)
}

Write-Check -Name 'Model directory exists' -Ok (Test-Path -LiteralPath $modelDir) -Detail $modelDir
Write-Check -Name 'Data directory exists' -Ok (Test-Path -LiteralPath $dataDir) -Detail $dataDir

if (Test-Path -LiteralPath $venvRoot) {
    Write-Host ''
    Write-Host 'Venv size:'
    $venvSize = Get-ChildItem -LiteralPath $venvRoot -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum
    $venvSizeGb = [math]::Round(($venvSize.Sum / 1GB), 3)
    Write-Host "$venvRoot = $venvSizeGb GB"
}

if ($dockerReady -and $composeReady) {
    Write-Host ''
    Write-Host 'Infra container status:'
    docker compose -f $composeFile ps

    Write-Host ''
    Write-Host 'Docker system df:'
    docker system df
}
else {
    Write-Host ''
    Write-Host 'Skipping container status and docker system df because Docker is not ready.'
}

Write-Host ''
if ($failed -gt 0) {
    Write-Host "Local setup check finished with $failed failure(s)."
    exit 1
}

Write-Host 'Local setup check passed.'
