param(
    [int]$Port = 8000,
    [switch]$Detached
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

# The API serves the kiosk UI too (single origin), so one tunnel to the API
# port exposes the whole app over HTTPS - which the phone camera requires.
$targetUrl = "http://localhost:$Port"

$blockedPorts = @(5432, 6379, 2375, 2376, 8081)
if ($blockedPorts -contains $Port) {
    throw "Refusing to tunnel port $Port. Never expose PostgreSQL, Redis, Docker, or Adminer."
}

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    throw 'cloudflared is not installed. Install it first: winget install Cloudflare.cloudflared'
}
Ensure-Directory -Path $script:RuntimeDir
Ensure-Directory -Path $script:LogDir

$pidPath = Join-Path $script:RuntimeDir 'cloudflared.pid'
$logPath = Join-Path $script:LogDir 'cloudflared-tunnel.log'
Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue

Write-Section 'Cloudflare Tunnel (HTTPS)'
Write-Host "Exposing: $targetUrl  (API + kiosk, single origin)"
Write-Host 'Never tunnel PostgreSQL, Redis, Docker, or Adminer.'
Write-Host ''

if ($Detached) {
    Stop-ProcessByPidFile -PidPath $pidPath -Name 'Cloudflare tunnel'
    $process = Start-Process `
        -FilePath 'cloudflared' `
        -ArgumentList @('tunnel', '--url', $targetUrl, '--no-autoupdate', '--logfile', $logPath) `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $pidPath -Value ([string]$process.Id) -Encoding ASCII

    $deadline = (Get-Date).AddSeconds(30)
    $publicUrl = $null
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $logPath) {
            $content = Get-Content -LiteralPath $logPath -Raw -ErrorAction SilentlyContinue
            $match = [regex]::Match($content, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
            if ($match.Success) { $publicUrl = $match.Value; break }
        }
        Start-Sleep -Seconds 1
    }

    if ($publicUrl) {
        Write-Host "Open this on your phone:  $publicUrl"
    }
    else {
        Write-Host "Tunnel starting. Find the https://*.trycloudflare.com URL in: $logPath"
    }
}
else {
    Write-Host 'Starting cloudflared. Open the https://*.trycloudflare.com URL below on your phone.'
    Write-Host '(Press Ctrl+C to stop the tunnel.)'
    Write-Host ''
    & cloudflared tunnel --url $targetUrl --no-autoupdate
}
