param(
    [string]$ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$ComposeFile = '',
    [string]$ApiHealthUrl = 'http://127.0.0.1:8000/health',
    [string]$KioskUrl = 'http://127.0.0.1:8080'
)

$ErrorActionPreference = 'Continue'
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ComposeFile) { $ComposeFile = Join-Path $ProjectPath 'docker\docker-compose.yml' }
$checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param([string]$Name, [bool]$Pass, [string]$Detail)
    $script:checks.Add([pscustomobject]@{ Name = $Name; Pass = $Pass; Detail = $Detail })
}

function Test-Http {
    param([string]$Url)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return @{ Pass = ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500); Detail = "HTTP $($r.StatusCode)" }
    } catch {
        return @{ Pass = $false; Detail = $_.Exception.Message }
    }
}

$venvPython = Join-Path $ProjectPath '.venv\Scripts\python.exe'
Add-Check 'Target project exists' (Test-Path -LiteralPath $ProjectPath) $ProjectPath
Add-Check 'Python venv exists' (Test-Path -LiteralPath $venvPython) $venvPython

if (Test-Path -LiteralPath $venvPython) {
    $code = @'
import importlib
mods = ["fastapi","sqlalchemy","asyncpg","redis","numpy","cv2","onnxruntime","insightface","pgvector"]
failed = []
for mod in mods:
    try:
        importlib.import_module(mod)
    except Exception as exc:
        failed.append(f"{mod}: {exc}")
if failed:
    print("\n".join(failed))
    raise SystemExit(1)
print("Python imports OK")
'@
    $out = & $venvPython -c $code 2>&1
    Add-Check 'Python imports' ($LASTEXITCODE -eq 0) ($out -join '; ')
}

$modelRoot = Join-Path $ProjectPath 'models\insightface\models\buffalo_l'
$requiredModels = @('1k3d68.onnx','2d106det.onnx','det_10g.onnx','genderage.onnx','w600k_r50.onnx')
$missingModels = @($requiredModels | Where-Object { -not (Test-Path -LiteralPath (Join-Path $modelRoot $_)) })
Add-Check 'InsightFace buffalo_l model files' ($missingModels.Count -eq 0) ($(if ($missingModels.Count) { 'Missing: ' + ($missingModels -join ', ') } else { $modelRoot }))
Add-Check 'Data directory exists' (Test-Path -LiteralPath (Join-Path $ProjectPath 'data')) (Join-Path $ProjectPath 'data')

if (Get-Command docker -ErrorAction SilentlyContinue) {
    $ps = & docker compose -f $ComposeFile ps --format json 2>&1
    Add-Check 'Docker compose reachable' ($LASTEXITCODE -eq 0) (($ps | Select-Object -First 1) -join '')
    $pg = & docker compose -f $ComposeFile exec -T postgres pg_isready -U attendance -d attendance 2>&1
    Add-Check 'PostgreSQL ready' ($LASTEXITCODE -eq 0) ($pg -join '; ')
    $vec = & docker compose -f $ComposeFile exec -T postgres psql -U attendance -d attendance -c "SELECT extname FROM pg_extension WHERE extname = 'vector';" 2>&1
    Add-Check 'pgvector extension' (($LASTEXITCODE -eq 0) -and (($vec -join "`n") -match 'vector')) ($vec -join '; ')
    $redis = & docker compose -f $ComposeFile exec -T redis redis-cli ping 2>&1
    Add-Check 'Redis ping' (($LASTEXITCODE -eq 0) -and (($redis -join '') -match 'PONG')) ($redis -join '; ')
} else {
    Add-Check 'Docker installed' $false 'docker command not found'
}

$api = Test-Http $ApiHealthUrl
Add-Check 'API health URL' $api.Pass $api.Detail
$kiosk = Test-Http $KioskUrl
Add-Check 'Kiosk URL' $kiosk.Pass $kiosk.Detail

Write-Host ''
Write-Host 'Migration Verification Report'
Write-Host '============================='
$failures = 0
foreach ($check in $checks) {
    $status = if ($check.Pass) { 'PASS' } else { 'FAIL'; $failures++ }
    Write-Host ("[{0}] {1} - {2}" -f $status, $check.Name, $check.Detail)
}

if ($failures -gt 0) {
    Write-Host "Final result: FAIL ($failures failing checks)"
    exit 1
}
Write-Host 'Final result: PASS'
