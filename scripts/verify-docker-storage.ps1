param(
    [string]$ExternalRoot = 'E:\DockerData'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$driveName = Split-Path -Path $ExternalRoot -Qualifier

if (-not $driveName) {
    throw "ExternalRoot harus memakai path drive Windows, contoh: E:\DockerData"
}

$driveRoot = "{0}\" -f $driveName
if (-not (Test-Path -LiteralPath $driveRoot)) {
    throw "Drive $driveName tidak tersedia. Pasang SSD eksternal sebelum menjalankan Docker Desktop."
}

if (-not (Test-Path -LiteralPath $ExternalRoot)) {
    throw "Folder $ExternalRoot belum ada. Jalankan scripts\setup-docker-external-ssd.ps1 lebih dulu."
}

$requiredFolders = @(
    $ExternalRoot,
    (Join-Path $ExternalRoot 'docker'),
    (Join-Path $ExternalRoot 'volumes'),
    (Join-Path $ExternalRoot 'cache'),
    (Join-Path $ExternalRoot 'logs')
)

foreach ($folder in $requiredFolders) {
    if (Test-Path -LiteralPath $folder) {
        Write-Host ("OK folder: {0}" -f $folder)
    }
    else {
        Write-Warning ("Folder belum ada: {0}" -f $folder)
    }
}

$modelsPath = Join-Path $repoRoot 'models'
if (Test-Path -LiteralPath $modelsPath) {
    Write-Host ("OK models folder: {0}" -f $modelsPath)
}
else {
    Write-Warning "Folder ./models belum ada. Buat folder ini agar bind mount ./models:/app/models dapat dibaca container."
}

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    throw 'Docker CLI tidak ditemukan di PATH.'
}

Push-Location -LiteralPath $repoRoot
try {
    Write-Host ''
    Write-Host '== docker info =='
    & $docker.Source info
    if ($LASTEXITCODE -ne 0) {
        throw "docker info gagal dengan exit code $LASTEXITCODE"
    }

    Write-Host ''
    Write-Host '== docker system df =='
    & $docker.Source system df
    if ($LASTEXITCODE -ne 0) {
        throw "docker system df gagal dengan exit code $LASTEXITCODE"
    }

    Write-Host ''
    Write-Host '== docker compose config =='
    & $docker.Source compose -f docker/docker-compose.yml config
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose config gagal dengan exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Host ''
Write-Host 'Verifikasi selesai. Pastikan Docker Desktop Disk image location di UI mengarah ke E:\DockerData\docker.'
