param(
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 8080
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$addresses = @(
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*' -and
            $_.PrefixOrigin -ne 'WellKnown'
        } |
        Sort-Object InterfaceAlias, IPAddress
)

if ($addresses.Count -eq 0) {
    throw 'No usable LAN IPv4 address found.'
}

Write-Host 'Local LAN URLs. Use a device on the same Wi-Fi/network.'
Write-Host ''
foreach ($address in $addresses) {
    $ip = $address.IPAddress
    Write-Host "Interface: $($address.InterfaceAlias)"
    Write-Host "API:       http://$ip`:$ApiPort"
    Write-Host "Kiosk UI:  http://$ip`:$FrontendPort"
    Write-Host "Classes:   http://$ip`:$ApiPort/attendance/classes/active"
    Write-Host ''
}
Write-Host 'Phone camera access may require HTTPS. Use Cloudflare Tunnel, ngrok, or Tailscale HTTPS/private access if the browser blocks camera permission.'

