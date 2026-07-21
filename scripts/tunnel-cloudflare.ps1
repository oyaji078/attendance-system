param(
    [ValidateSet('frontend', 'api')]
    [string]$Target = 'frontend',
    [string]$Url,
    [switch]$Detached
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

function Resolve-TunnelUrl {
    if ($Url) {
        return $Url
    }
    if ($Target -eq 'api') {
        return 'http://localhost:8000'
    }
    return 'http://localhost:8080'
}

function Assert-SafeTunnelUrl {
    param([Parameter(Mandatory = $true)][string]$TunnelUrl)

    $uri = [Uri]$TunnelUrl
    if ($uri.Scheme -notin @('http', 'https')) {
        throw 'Only HTTP/HTTPS application URLs may be tunneled.'
    }

    $blockedPorts = @(5432, 6379, 2375, 2376, 8081)
    if ($blockedPorts -contains $uri.Port) {
        throw "Refusing to tunnel port $($uri.Port). Do not expose PostgreSQL, Redis, Docker, or Adminer."
    }
}

$targetUrl = Resolve-TunnelUrl
Assert-SafeTunnelUrl -TunnelUrl $targetUrl

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    throw 'cloudflared is not installed or not on PATH. Install Cloudflare Tunnel first.'
}
Ensure-Directory -Path $script:RuntimeDir
Ensure-Directory -Path $script:LogDir

$pidPath = Join-Path $script:RuntimeDir 'cloudflared.pid'
$logPath = Join-Path $script:LogDir 'cloudflared-tunnel.log'
Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue

Write-Section 'Cloudflare Tunnel'
Write-Host "Target: $targetUrl"
Write-Host 'Do not tunnel PostgreSQL, Redis, Docker daemon, or Adminer.'
Write-Host 'If admin is used through a tunnel, use HTTPS and strong admin credentials.'

if ($Detached) {
    Stop-ProcessByPidFile -PidPath $pidPath -Name 'Cloudflare tunnel'
    $process = Start-Process `
        -FilePath 'cloudflared' `
        -ArgumentList @('tunnel', '--url', $targetUrl, '--logfile', $logPath) `
        -WorkingDirectory (Get-RepoRoot) `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $pidPath -Value ([string]$process.Id) -Encoding ASCII
    Write-Host "cloudflared started with PID $($process.Id). Log: $logPath"

    $deadline = (Get-Date).AddSeconds(30)
    $publicUrl = $null
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $logPath) {
            $content = Get-Content -LiteralPath $logPath -Raw -ErrorAction SilentlyContinue
            $match = [regex]::Match($content, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
            if ($match.Success) {
                $publicUrl = $match.Value
                break
            }
        }
        Start-Sleep -Seconds 1
    }

    if ($publicUrl) {
        Write-Host "Public URL: $publicUrl"
        if ($Target -eq 'frontend') {
            Write-Host 'For two-URL mode, append ?api_base_url=<API_TUNNEL_URL> if API is exposed separately.'
        }
    }
    else {
        Write-Host 'Public URL was not detected yet. Check the log file above.'
    }
}
else {
    Write-Host 'Starting cloudflared in the foreground. Copy the https://*.trycloudflare.com URL from the output.'
    & cloudflared tunnel --url $targetUrl
}
