param(
    [switch]$NoFrontend,
    [switch]$NoMigrations,
    [int]$ApiPort = 8000,
    [int]$KioskPort = 8080
)

. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)
Import-ProjectEnv

Write-Section 'Docker infra'
Start-Infra
Wait-PostgresReady
Wait-RedisReady

if (-not $NoMigrations) {
    Write-Section 'Database migrations'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Get-RepoRoot) 'scripts\migrate.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw 'Migration failed.'
    }
}

$python = Resolve-ProjectPython

Write-Section 'API'
Stop-ProcessByPidFile -PidPath $script:ApiPidFile -Name 'API'
Stop-ExpectedPortProcess -Port $ApiPort -Kind api
Assert-PortAvailable -Port $ApiPort -Purpose 'API'

$apiOutLog = Join-Path $script:LogDir 'api.out.log'
$apiErrLog = Join-Path $script:LogDir 'api.err.log'
$apiArgs = @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'apps/api-python', '--reload', '--host', '0.0.0.0', '--port', "$ApiPort")
$apiProcess = Start-BackgroundCommand -FilePath $python -ArgumentList $apiArgs -WorkingDirectory (Get-RepoRoot) -OutLog $apiOutLog -ErrLog $apiErrLog -PidPath $script:ApiPidFile
Write-Host "API started with PID $($apiProcess.Id). Logs: $apiOutLog, $apiErrLog"
Wait-HttpNot404 -Url "http://localhost:$ApiPort/openapi.json" -TimeoutSeconds 90 | Out-Null

if (-not $NoFrontend) {
    Write-Section 'Kiosk UI'
    Stop-ProcessByPidFile -PidPath $script:KioskPidFile -Name 'Kiosk UI'
    Stop-ExpectedPortProcess -Port $KioskPort -Kind kiosk
    Assert-PortAvailable -Port $KioskPort -Purpose 'kiosk UI'

    $kioskOutLog = Join-Path $script:LogDir 'kiosk.out.log'
    $kioskErrLog = Join-Path $script:LogDir 'kiosk.err.log'
    $kioskArgs = @('-m', 'http.server', "$KioskPort", '--directory', 'apps/kiosk-ui/src')
    $kioskProcess = Start-BackgroundCommand -FilePath $python -ArgumentList $kioskArgs -WorkingDirectory (Get-RepoRoot) -OutLog $kioskOutLog -ErrLog $kioskErrLog -PidPath $script:KioskPidFile
    Write-Host "Kiosk UI started with PID $($kioskProcess.Id). Logs: $kioskOutLog, $kioskErrLog"
}

Write-Section 'URLs'
Write-Host "App (kiosk + API): http://localhost:$ApiPort      <- the API serves the kiosk too"
Write-Host "API docs:          http://localhost:$ApiPort/docs"
if (-not $NoFrontend) {
    Write-Host "Kiosk (dev live):  http://localhost:$KioskPort   (optional; use $ApiPort for one origin)"
}
Write-Host 'DB browser:        run .\scripts\db-browser.ps1, then open http://localhost:8081'
Write-Host ''
Write-Host "Test on your phone (HTTPS): powershell -ExecutionPolicy Bypass -File .\scripts\tunnel-cloudflare.ps1 -Port $ApiPort"

