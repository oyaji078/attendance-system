. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)
Import-ProjectEnv

$python = Resolve-ProjectPython

Write-Section 'Alembic current before upgrade'
& $python -m alembic current
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to read current Alembic revision.'
}

Write-Section 'Alembic upgrade head'
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw 'Alembic upgrade failed.'
}

Write-Section 'Alembic current after upgrade'
& $python -m alembic current
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to read current Alembic revision after upgrade.'
}

