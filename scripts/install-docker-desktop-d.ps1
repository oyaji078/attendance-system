param(
    [string]$InstallRoot = 'D:\DockerDesktop',
    [string]$DockerUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
    [switch]$DownloadOnly,
    [switch]$ElevatedInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-DockerInstallerMetadata {
    $fallback = [pscustomobject]@{
        Version = 'latest'
        Url = 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe'
    }

    try {
        $showOutput = winget show Docker.DockerDesktop --accept-source-agreements 2>$null | Out-String
        $versionMatch = [regex]::Match($showOutput, 'Version:\s+([^\r\n]+)')
        $urlMatch = [regex]::Match($showOutput, 'Installer Url:\s+([^\r\n]+)')

        if (-not $versionMatch.Success -or -not $urlMatch.Success) {
            return $fallback
        }

        return [pscustomobject]@{
            Version = $versionMatch.Groups[1].Value.Trim()
            Url = $urlMatch.Groups[1].Value.Trim()
        }
    }
    catch {
        return $fallback
    }
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-InstallerPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Version
    )

    $installerDir = Join-Path $Root 'installers'
    Ensure-Directory -Path $installerDir
    return Join-Path $installerDir ("DockerDesktopInstaller-{0}.exe" -f $Version)
}

function Download-Installer {
    param(
        [Parameter(Mandatory = $true)][pscustomobject]$Metadata,
        [Parameter(Mandatory = $true)][string]$InstallerPath
    )

    if (Test-Path -LiteralPath $InstallerPath) {
        Write-Host ("Installer sudah ada: {0}" -f $InstallerPath)
        return
    }

    Write-Host ("Mengunduh Docker Desktop {0}..." -f $Metadata.Version)
    try {
        if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
            Start-BitsTransfer -Source $Metadata.Url -Destination $InstallerPath -DisplayName 'Docker Desktop Installer' -Description 'Download Docker Desktop installer' -Priority Foreground
        }
        else {
            & curl.exe -L --fail --retry 5 --retry-delay 5 -o $InstallerPath $Metadata.Url
            if ($LASTEXITCODE -ne 0) {
                throw ("curl.exe gagal dengan exit code {0}" -f $LASTEXITCODE)
            }
        }
    }
    catch {
        if (Test-Path -LiteralPath $InstallerPath) {
            Remove-Item -LiteralPath $InstallerPath -Force -ErrorAction SilentlyContinue
        }

        throw
    }

    Write-Host ("Installer tersimpan di: {0}" -f $InstallerPath)
}

function Add-DockerUsersMembership {
    param([Parameter(Mandatory = $true)][string]$Member)

    try {
        Add-LocalGroupMember -Group 'docker-users' -Member $Member -ErrorAction Stop
        Write-Host ("User {0} ditambahkan ke group docker-users." -f $Member)
        return
    }
    catch {
        if ($_.Exception.Message -match 'already a member') {
            Write-Host ("User {0} sudah ada di group docker-users." -f $Member)
            return
        }

        throw ("Gagal menambahkan user ke docker-users: {0}" -f $_.Exception.Message)
    }
}

function Add-UserPathEntry {
    param([Parameter(Mandatory = $true)][string]$Entry)

    $currentUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @()
    if ($currentUserPath) {
        $entries = $currentUserPath -split ';' | Where-Object { $_ }
    }

    if ($entries -contains $Entry) {
        return
    }

    $newEntries = @($entries + $Entry)
    [Environment]::SetEnvironmentVariable('Path', ($newEntries -join ';'), 'User')

    if (($env:Path -split ';') -notcontains $Entry) {
        $env:Path = '{0};{1}' -f $Entry, $env:Path
    }
}

function Install-DockerDesktop {
    param(
        [Parameter(Mandatory = $true)][string]$InstallerPath,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Member
    )

    $appRoot = Join-Path $Root 'app'
    $wslRoot = Join-Path $Root 'wsl'
    $hyperVRoot = Join-Path $Root 'hyper-v'
    $windowsRoot = Join-Path $Root 'windows-containers'

    foreach ($path in @($appRoot, $wslRoot, $hyperVRoot, $windowsRoot)) {
        Ensure-Directory -Path $path
    }

    $arguments = @(
        'install',
        '--quiet',
        '--accept-license',
        '--backend=wsl-2',
        '--always-run-service',
        "--installation-dir=$appRoot",
        "--wsl-default-data-root=$wslRoot",
        "--hyper-v-default-data-root=$hyperVRoot",
        "--windows-containers-default-data-root=$windowsRoot"
    )

    Write-Host ("Memasang Docker Desktop ke {0}" -f $appRoot)
    Start-Process -FilePath $InstallerPath -ArgumentList $arguments -Wait
    Add-DockerUsersMembership -Member $Member
    Add-UserPathEntry -Entry (Join-Path $appRoot 'resources\bin')
}

$metadata = Get-DockerInstallerMetadata
$installerPath = Get-InstallerPath -Root $InstallRoot -Version $metadata.Version

Ensure-Directory -Path $InstallRoot
Download-Installer -Metadata $metadata -InstallerPath $installerPath

if ($DownloadOnly) {
    Write-Host 'Unduhan selesai. Instalasi belum dijalankan.'
    exit 0
}

if ($ElevatedInstall -or (Test-IsAdministrator)) {
    Install-DockerDesktop -InstallerPath $installerPath -Root $InstallRoot -Member $DockerUser
    exit 0
}

Write-Host 'Meminta izin administrator untuk menjalankan instalasi Docker Desktop.'
$selfPath = (Resolve-Path -LiteralPath $PSCommandPath).Path
$elevatedArgs = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $selfPath,
    '-InstallRoot', $InstallRoot,
    '-DockerUser', $DockerUser,
    '-ElevatedInstall'
)
Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $elevatedArgs -Wait
