param(
    [int]$Port = 8080,
    [string]$HostHeader,
    [switch]$Detached
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)

$blockedPorts = @(5432, 6379, 2375, 2376, 8081)
if ($blockedPorts -contains $Port) {
    throw "Refusing to tunnel port $Port. Do not expose PostgreSQL, Redis, Docker, or Adminer."
}

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    throw 'ngrok is not installed or not on PATH. Install ngrok first.'
}

Ensure-Directory -Path $script:RuntimeDir
Ensure-Directory -Path $script:LogDir
$pidPath = Join-Path $script:RuntimeDir 'ngrok.pid'
$logPath = Join-Path $script:LogDir 'ngrok-tunnel.log'
$errLogPath = Join-Path $script:LogDir 'ngrok-tunnel.err.log'

$args = @('http', "$Port")
if ($HostHeader) {
    $args += @('--host-header', $HostHeader)
}

Write-Section 'ngrok Tunnel'
Write-Host "Target: http://localhost:$Port"
Write-Host 'Do not tunnel PostgreSQL, Redis, Docker daemon, or Adminer.'
Write-Host 'If admin is used through a tunnel, use HTTPS and strong admin credentials.'

if ($Detached) {
    Stop-ProcessByPidFile -PidPath $pidPath -Name 'ngrok tunnel'
    Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $errLogPath -Force -ErrorAction SilentlyContinue
    $process = Start-Process `
        -FilePath 'ngrok' `
        -ArgumentList $args `
        -WorkingDirectory (Get-RepoRoot) `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError $errLogPath `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $pidPath -Value ([string]$process.Id) -Encoding ASCII
    Write-Host "ngrok started with PID $($process.Id). Dashboard: http://127.0.0.1:4040"

    $deadline = (Get-Date).AddSeconds(30)
    $publicUrl = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $tunnels = Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2
            $publicUrl = @($tunnels.tunnels | Where-Object { $_.proto -eq 'https' } | Select-Object -First 1).public_url
            if ($publicUrl) {
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    if ($publicUrl) {
        Write-Host "Public URL: $publicUrl"
        if ($Port -eq 8080) {
            Write-Host 'For two-URL mode, append ?api_base_url=<API_TUNNEL_URL> if API is exposed separately.'
        }
    }
    else {
        Write-Host 'Public URL was not detected yet. Check http://127.0.0.1:4040 or the log file.'
    }
}
else {
    Write-Host 'Starting ngrok in the foreground. Copy the generated HTTPS URL from the output.'
    & ngrok @args
}
