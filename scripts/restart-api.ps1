. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Get-RepoRoot)
Import-ProjectEnv

Write-Section 'Docker infra'
Start-Infra
Wait-PostgresReady
Wait-RedisReady

Write-Section 'Stop API'
Stop-ProcessByPidFile -PidPath $script:ApiPidFile -Name 'API'
Stop-ExpectedPortProcess -Port 8000 -Kind api
Assert-PortAvailable -Port 8000 -Purpose 'API'

Write-Section 'Database migrations'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Get-RepoRoot) 'scripts\migrate.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'Migration failed.'
}

Write-Section 'Start API'
$python = Resolve-ProjectPython
$apiOutLog = Join-Path $script:LogDir 'api.out.log'
$apiErrLog = Join-Path $script:LogDir 'api.err.log'
$apiArgs = @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'apps/api-python', '--reload', '--host', '0.0.0.0', '--port', '8000')
$apiProcess = Start-BackgroundCommand -FilePath $python -ArgumentList $apiArgs -WorkingDirectory (Get-RepoRoot) -OutLog $apiOutLog -ErrLog $apiErrLog -PidPath $script:ApiPidFile
Write-Host "API started with PID $($apiProcess.Id)."

Write-Section 'Verify API'
Wait-HttpNot404 -Url 'http://localhost:8000/openapi.json' -TimeoutSeconds 90 | Out-Null
Wait-HttpNot404 -Url 'http://localhost:8000/attendance/classes/active' -TimeoutSeconds 30 | Out-Null
Write-Host 'API restart verified.'

