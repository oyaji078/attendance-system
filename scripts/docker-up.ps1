param(
    [switch]$EdgeProfile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-DockerCli {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        'D:\DockerDesktop\app\resources\bin\docker.exe',
        'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $dockerDir = Split-Path -Parent $candidate
            if (($env:Path -split ';') -notcontains $dockerDir) {
                $env:Path = '{0};{1}' -f $dockerDir, $env:Path
            }

            return $candidate
        }
    }

    throw 'Docker CLI belum tersedia. Jalankan scripts\install-docker-desktop-d.ps1 dulu.'
}

function Resolve-DockerDesktopExe {
    $candidates = @(
        'D:\DockerDesktop\app\Docker Desktop.exe',
        'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

function Test-DockerReady {
    param([Parameter(Mandatory = $true)][string]$DockerCli)

    try {
        & $DockerCli info *> $null
        return $true
    }
    catch {
        return $false
    }
}

function Wait-DockerReady {
    param(
        [Parameter(Mandatory = $true)][string]$DockerCli,
        [int]$TimeoutSeconds = 240
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerReady -DockerCli $DockerCli) {
            return
        }

        Start-Sleep -Seconds 3
    }

    throw 'Docker daemon belum siap. Pastikan Docker Desktop sudah terbuka dan statusnya Running.'
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Start-DockerDesktopIfNeeded {
    param([Parameter(Mandatory = $true)][string]$DockerCli)

    if (Test-DockerReady -DockerCli $DockerCli) {
        return
    }

    $desktopExe = Resolve-DockerDesktopExe
    if (-not $desktopExe) {
        return
    }

    $desktopProcess = Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue
    if (-not $desktopProcess) {
        Start-Process -FilePath $desktopExe | Out-Null
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

Ensure-Directory -Path (Join-Path $repoRoot 'data\object-storage')
Ensure-Directory -Path (Join-Path $repoRoot 'models\insightface')

$dockerCli = Resolve-DockerCli
Start-DockerDesktopIfNeeded -DockerCli $dockerCli
Wait-DockerReady -DockerCli $dockerCli

$composeArgs = @(
    'compose',
    '-f', 'docker/docker-compose.yml'
)

if ($EdgeProfile) {
    $composeArgs += @('--profile', 'edge')
}

$composeArgs += @('up', '--build', '-d')

& $dockerCli @composeArgs

Write-Host ''
Write-Host 'Stack aktif.'
Write-Host 'API      : http://localhost:8000/health'
Write-Host 'Kiosk UI : http://localhost:8080'
