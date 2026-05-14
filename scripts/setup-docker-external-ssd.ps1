param(
    [string]$ExternalRoot = 'E:\DockerData'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Write-Host ("Created: {0}" -f $Path)
        return
    }

    Write-Host ("Exists : {0}" -f $Path)
}

$driveName = Split-Path -Path $ExternalRoot -Qualifier
if (-not $driveName) {
    throw "ExternalRoot harus memakai path drive Windows, contoh: E:\DockerData"
}

$driveLetter = $driveName.TrimEnd(':')
$driveRoot = "{0}\" -f $driveName

if (-not (Test-Path -LiteralPath $driveRoot)) {
    throw "Drive $driveName tidak tersedia. Pasang SSD eksternal sebagai Local Disk E: terlebih dahulu."
}

$volume = Get-Volume -DriveLetter $driveLetter -ErrorAction SilentlyContinue
if ($volume) {
    Write-Host ("Drive {0} filesystem: {1}" -f $driveName, $volume.FileSystem)
    if ($volume.FileSystem -ne 'NTFS') {
        Write-Warning "Filesystem drive $driveName bukan NTFS. Untuk Docker Desktop di Windows, NTFS direkomendasikan."
        Write-Warning "Script ini tidak memformat drive. Backup data penting sebelum melakukan perubahan filesystem secara manual."
    }
}
else {
    Write-Warning "Tidak bisa membaca informasi filesystem drive $driveName. Lanjut membuat folder jika path tersedia."
}

$directories = @(
    $ExternalRoot,
    (Join-Path $ExternalRoot 'docker'),
    (Join-Path $ExternalRoot 'volumes'),
    (Join-Path $ExternalRoot 'cache'),
    (Join-Path $ExternalRoot 'logs')
)

foreach ($directory in $directories) {
    Ensure-Directory -Path $directory
}

Write-Host ''
Write-Host 'Folder SSD eksternal siap.'
Write-Host ''
Write-Host 'Langkah manual berikutnya di Docker Desktop:'
Write-Host '1. Buka Docker Desktop.'
Write-Host '2. Buka Settings > Resources > Advanced.'
Write-Host '3. Ubah Disk image location ke:'
Write-Host ("   {0}" -f (Join-Path $ExternalRoot 'docker'))
Write-Host '4. Pilih Apply & Restart.'
Write-Host '5. Jalankan scripts\verify-docker-storage.ps1 untuk verifikasi.'
Write-Host ''
Write-Host 'Catatan: script ini tidak memformat drive, tidak membersihkan Docker data lama, dan tidak memindahkan data otomatis.'
