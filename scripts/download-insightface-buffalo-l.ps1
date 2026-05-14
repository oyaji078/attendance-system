Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = 'D:\PythonVenvs\attendance-api\Scripts\python.exe'
$modelRoot = 'D:\cnn\attendance-system\models\insightface'
$modelDir = Join-Path $modelRoot 'models\buffalo_l'
$helperScript = Join-Path $PSScriptRoot 'ensure_insightface_model.py'
$expectedFiles = @(
    '1k3d68.onnx',
    '2d106det.onnx',
    'det_10g.onnx',
    'genderage.onnx',
    'w600k_r50.onnx'
)

function Get-MissingModelFiles {
    $missing = @()
    foreach ($fileName in $expectedFiles) {
        $filePath = Join-Path $modelDir $fileName
        if (-not (Test-Path -LiteralPath $filePath)) {
            $missing += $fileName
        }
    }
    return $missing
}

function Show-ModelFiles {
    if (-not (Test-Path -LiteralPath $modelDir)) {
        return
    }

    Get-ChildItem -LiteralPath $modelDir -File -ErrorAction SilentlyContinue |
        Sort-Object Name |
        Select-Object Name, @{Name = 'SizeMB'; Expression = { [math]::Round($_.Length / 1MB, 2) } }
}

Set-Location -LiteralPath $repoRoot

if (-not $modelRoot.StartsWith('D:\cnn\attendance-system\models', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Model root tidak aman untuk mode ini: $modelRoot"
}
if ($modelRoot.StartsWith('E:\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Model root tidak boleh berada di drive E: $modelRoot"
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Venv python tidak ditemukan: $pythonExe"
}
if (-not (Test-Path -LiteralPath $helperScript)) {
    throw "Helper script tidak ditemukan: $helperScript"
}

New-Item -ItemType Directory -Path $modelDir -Force | Out-Null

$missingFiles = @(Get-MissingModelFiles)
if ($missingFiles.Count -eq 0) {
    Write-Host "Model buffalo_l sudah lengkap di $modelDir. Download tidak dijalankan ulang."
    Show-ModelFiles | Format-Table -AutoSize
    exit 0
}

Write-Host 'Model buffalo_l belum lengkap.'
Write-Host "Target download: $modelRoot"
Write-Host 'File yang belum ada:'
$missingFiles | ForEach-Object { Write-Host "- $_" }
Write-Host ''
Write-Host 'Download akan memakai venv Python dan mekanisme resmi InsightFace ke folder D project.'
Write-Host 'Script ini tidak menghapus data lama dan tidak memakai drive E.'
Write-Host ''
$confirmation = (Read-Host 'Ketik DOWNLOAD untuk mulai download model buffalo_l').Trim()
if ($confirmation.ToUpperInvariant() -ne 'DOWNLOAD') {
    Write-Host 'Download dibatalkan. Tidak ada perubahan model.'
    exit 0
}

& $pythonExe $helperScript
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ''
Write-Host 'File model setelah download:'
Show-ModelFiles | Format-Table -AutoSize

$remainingMissing = @(Get-MissingModelFiles)
if ($remainingMissing.Count -gt 0) {
    Write-Host ''
    Write-Warning 'Download selesai, tetapi model masih belum lengkap.'
    $remainingMissing | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host ''
Write-Host 'Model buffalo_l lengkap.'
