param(
    [int]$ApiPort = 8000,
    [int]$KioskPort = 8080,
    [int]$TunnelPort = 8000,
    [switch]$Detached
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)
Import-ProjectEnv

Write-Section 'Start local app'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Get-RepoRoot) 'scripts\start-dev.ps1') -ApiPort $ApiPort -KioskPort $KioskPort

Write-Section 'Start Cloudflare tunnel'
$tunnelArgs = @('-Port', "$TunnelPort")
if ($Detached) {
    $tunnelArgs += '-Detached'
}
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Get-RepoRoot) 'scripts\tunnel-cloudflare.ps1') @tunnelArgs

Write-Section 'Done'
Write-Host "Local app should be available at http://localhost:$ApiPort"
Write-Host "Tunnel will expose http://localhost:$TunnelPort over HTTPS"
Write-Host 'If cloudflared is run detached, stop it with .\scripts\stop-tunnel.ps1'
