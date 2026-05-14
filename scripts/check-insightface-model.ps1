param(
    [switch]$Download
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = 'D:\PythonVenvs\attendance-api\Scripts\python.exe'
$modelRoot = 'D:\cnn\attendance-system\models\insightface'
$modelDir = Join-Path $modelRoot 'models\buffalo_l'
$expectedFiles = @(
    '1k3d68.onnx',
    '2d106det.onnx',
    'det_10g.onnx',
    'genderage.onnx',
    'w600k_r50.onnx'
)

function Write-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Ok,
        [string]$Detail = ''
    )

    if ($Ok) {
        Write-Host "[OK]      $Name $Detail"
    }
    else {
        Write-Host "[MISSING] $Name $Detail"
    }
}

function Get-DirectorySizeGb {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }

    $files = @(Get-ChildItem -LiteralPath $Path -Recurse -Force -File -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) {
        return 0
    }

    $size = $files | Measure-Object -Property Length -Sum
    return [math]::Round(($size.Sum / 1GB), 3)
}

Set-Location -LiteralPath $repoRoot

Write-Host 'InsightFace buffalo_l model check'
Write-Host "Repo       : $repoRoot"
Write-Host "Model root : $modelRoot"
Write-Host "Model dir  : $modelDir"
Write-Host ''

$missingFiles = @()
Write-Check -Name 'Model directory' -Ok (Test-Path -LiteralPath $modelDir) -Detail $modelDir

foreach ($fileName in $expectedFiles) {
    $filePath = Join-Path $modelDir $fileName
    $exists = Test-Path -LiteralPath $filePath
    Write-Check -Name $fileName -Ok $exists -Detail $filePath
    if (-not $exists) {
        $missingFiles += $fileName
    }
}

Write-Host ''
Write-Host ("Model folder size: {0} GB" -f (Get-DirectorySizeGb -Path $modelDir))

$pythonExists = Test-Path -LiteralPath $pythonExe
Write-Host ''
Write-Check -Name 'Venv python' -Ok $pythonExists -Detail $pythonExe
if (-not $pythonExists) {
    Write-Host ''
    Write-Host 'Venv python tidak ditemukan. Perbaiki path venv sebelum validasi model.'
    exit 1
}

Write-Host ''
& $pythonExe (Join-Path $PSScriptRoot 'check_insightface_model.py')
$pythonExit = $LASTEXITCODE

if ($missingFiles.Count -gt 0) {
    Write-Host ''
    Write-Warning 'Model buffalo_l belum lengkap. Jalankan scripts/download-insightface-buffalo-l.ps1 atau taruh file ONNX manual.'
    Write-Host 'Missing ONNX files:'
    $missingFiles | ForEach-Object { Write-Host "- $_" }
    Write-Host ''
    Write-Host 'Download aman ke drive D:'
    Write-Host 'powershell -ExecutionPolicy Bypass -File scripts/download-insightface-buffalo-l.ps1'

    if ($Download) {
        Write-Host ''
        Write-Host 'Parameter -Download diterima. Menjalankan script download dengan konfirmasi user.'
        & (Join-Path $PSScriptRoot 'download-insightface-buffalo-l.ps1')
        exit $LASTEXITCODE
    }

    exit 0
}

if ($pythonExit -ne 0) {
    Write-Host ''
    Write-Host "FaceAnalysis/API model validation failed with exit code $pythonExit."
    exit $pythonExit
}

Write-Host ''
Write-Host 'InsightFace buffalo_l model check passed.'
