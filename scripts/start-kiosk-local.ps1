Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = 'D:\PythonVenvs\attendance-api\Scripts\python.exe'
$kioskRoot = Join-Path $repoRoot 'apps\kiosk-ui\src'

if (-not (Test-Path -LiteralPath $kioskRoot)) {
    throw "Kiosk UI directory not found: $kioskRoot"
}

Set-Location -LiteralPath $repoRoot

if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -m http.server 8080 --directory apps/kiosk-ui/src
}
else {
    python -m http.server 8080 --directory apps/kiosk-ui/src
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
