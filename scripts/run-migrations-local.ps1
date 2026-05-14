Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = 'D:\PythonVenvs\attendance-api'
$activateScript = Join-Path $venvRoot 'Scripts\Activate.ps1'
$pythonExe = Join-Path $venvRoot 'Scripts\python.exe'
$alembicExe = Join-Path $venvRoot 'Scripts\alembic.exe'
$envFile = Join-Path $repoRoot '.env.local-api'

function Import-EnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Environment file not found: $Path"
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        $separatorIndex = $line.IndexOf('=')
        if ($separatorIndex -lt 1) {
            continue
        }

        $name = $line.Substring(0, $separatorIndex).Trim()
        $value = $line.Substring($separatorIndex + 1).Trim()
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Venv python not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $activateScript)) {
    throw "Venv activation script not found: $activateScript"
}

Set-Location -LiteralPath $repoRoot
. $activateScript
Import-EnvFile -Path $envFile
[Environment]::SetEnvironmentVariable('POSTGRES_HOST', 'localhost', 'Process')

$apiPath = Join-Path $repoRoot 'apps\api-python'
$existingPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
if ($existingPythonPath) {
    $env:PYTHONPATH = "$repoRoot;$apiPath;$existingPythonPath"
}
else {
    $env:PYTHONPATH = "$repoRoot;$apiPath"
}

if (Test-Path -LiteralPath $alembicExe) {
    & $alembicExe upgrade head
}
else {
    & $pythonExe -m alembic upgrade head
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
