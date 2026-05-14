param(
    [switch]$RunMigrations
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot 'docker\docker-compose.infra.yml'
$runtimeDir = Join-Path $repoRoot '.runtime'
$logDir = Join-Path $repoRoot 'logs'
$pythonExe = 'D:\PythonVenvs\attendance-api\Scripts\python.exe'
$modelRoot = Join-Path $repoRoot 'models'
$envFile = Join-Path $repoRoot '.env.local-api'
$apiPidFile = Join-Path $runtimeDir 'api.pid'
$kioskPidFile = Join-Path $runtimeDir 'kiosk.pid'
$apiOutLog = Join-Path $logDir 'api.out.log'
$apiErrLog = Join-Path $logDir 'api.err.log'
$kioskOutLog = Join-Path $logDir 'kiosk.out.log'
$kioskErrLog = Join-Path $logDir 'kiosk.err.log'

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)
    Write-Host ''
    Write-Host "== $Title =="
}

function Import-EnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Environment file not found: $Path"
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        $separatorIndex = $line.IndexOf('=')
        if ($separatorIndex -lt 1) {
            continue
        }

        $name = $line.Substring(0, $separatorIndex).Trim()
        $value = $line.Substring($separatorIndex + 1).Trim()
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

function Get-ListeningPortProcesses {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    $processIds = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($processId in $processIds) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        $cimProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        [pscustomobject]@{
            Port = $Port
            PID = $processId
            Name = if ($process) { $process.ProcessName } else { '<unknown>' }
            Path = if ($process) { $process.Path } else { $null }
            CommandLine = if ($cimProcess) { $cimProcess.CommandLine } else { $null }
        }
    }
}

function Test-ExpectedApiProcess {
    param([Parameter(Mandatory = $true)]$PortProcess)
    $commandLine = [string]$PortProcess.CommandLine
    return ($commandLine -like '*uvicorn*app.main:app*--port*8000*')
}

function Test-ExpectedKioskProcess {
    param([Parameter(Mandatory = $true)]$PortProcess)
    $commandLine = [string]$PortProcess.CommandLine
    return ($commandLine -like '*http.server*8080*apps/kiosk-ui/src*' -or $commandLine -like '*http.server*8080*apps\kiosk-ui\src*')
}

function Sync-PidFileFromPort {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$PidPath
    )

    $portProcesses = @(Get-ListeningPortProcesses -Port $Port)
    $expectedProcess = @(
        $portProcesses |
            Where-Object {
                if ($Name -eq 'API') {
                    Test-ExpectedApiProcess $_
                }
                else {
                    Test-ExpectedKioskProcess $_
                }
            } |
            Select-Object -First 1
    )
    if ($expectedProcess.Count -eq 0) {
        return $false
    }

    Set-Content -LiteralPath $PidPath -Value ([string]$expectedProcess[0].PID) -NoNewline
    Write-Host "Recorded $Name PID $($expectedProcess[0].PID) in $PidPath"
    return $true
}

function Clear-StalePidFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $rawPid = (Get-Content -LiteralPath $Path -ErrorAction SilentlyContinue | Select-Object -First 1)
    $processId = 0
    if (-not [int]::TryParse([string]$rawPid, [ref]$processId) -or -not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

function Wait-Command {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Probe,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Probe) {
            Write-Host "$Name ready"
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "$Name was not ready after $TimeoutSeconds seconds"
}

function Invoke-NativeQuiet {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $nativePreferenceExists = Test-Path -LiteralPath Variable:\PSNativeCommandUseErrorActionPreference
    if ($nativePreferenceExists) {
        $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    }

    $output = @()
    $exitCode = 1
    try {
        $ErrorActionPreference = 'Continue'
        if ($nativePreferenceExists) {
            $PSNativeCommandUseErrorActionPreference = $false
        }

        $output = @(& $FilePath @ArgumentList 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    }
    catch {
        $output = @([string]$_.Exception.Message)
        $exitCode = 1
    }
    finally {
        if ($nativePreferenceExists) {
            $PSNativeCommandUseErrorActionPreference = $previousNativePreference
        }
        $ErrorActionPreference = $previousErrorActionPreference
    }

    [pscustomobject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

function Format-NativeFailure {
    param(
        [Parameter(Mandatory = $true)]$Result,
        [int]$MaxLines = 4
    )

    $lines = @($Result.Output | Where-Object { $_ } | Select-Object -First $MaxLines)
    if ($lines.Count -eq 0) {
        return ''
    }

    return ($lines -join [Environment]::NewLine)
}

function Test-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 5
    )

    Add-Type -AssemblyName System.Net.Http
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    $response = $null
    try {
        $response = $client.GetAsync($Url).GetAwaiter().GetResult()
        return ($response.IsSuccessStatusCode)
    }
    catch {
        return $false
    }
    finally {
        if ($response) {
            $response.Dispose()
        }
        $client.Dispose()
        $handler.Dispose()
    }
}

function Start-BackgroundProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$StdOutPath,
        [Parameter(Mandatory = $true)][string]$StdErrPath,
        [Parameter(Mandatory = $true)][string]$PidPath
    )

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdOutPath `
        -RedirectStandardError $StdErrPath `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $PidPath -Value ([string]$process.Id) -NoNewline
    Write-Host "$Name started with PID $($process.Id)"
    return $process
}

function Wait-DockerService {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [Parameter(Mandatory = $true)][string[]]$CommandArgs,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutSeconds = 60
    )

    Wait-Command -Name $Name -TimeoutSeconds $TimeoutSeconds -Probe {
        $result = Invoke-NativeQuiet -FilePath 'docker' -ArgumentList (@('compose', '-f', $composeFile, 'exec', '-T', $Service) + $CommandArgs)
        return ($result.ExitCode -eq 0)
    }
}

Set-Location -LiteralPath $repoRoot
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Clear-StalePidFile -Path $apiPidFile
Clear-StalePidFile -Path $kioskPidFile

Write-Section 'Preflight'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'docker command not found. Start Docker Desktop and make sure Docker CLI is on PATH.'
    exit 1
}
if (-not (Test-Path -LiteralPath $composeFile)) {
    throw "Infra compose file not found: $composeFile"
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Venv python not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $modelRoot)) {
    throw "Model folder not found: $modelRoot"
}
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Local API env file not found: $envFile"
}

$dockerInfo = Invoke-NativeQuiet -FilePath 'docker' -ArgumentList @('info')
if ($dockerInfo.ExitCode -ne 0) {
    $details = Format-NativeFailure -Result $dockerInfo
    Write-Host 'Docker Desktop is not reachable.'
    Write-Host 'Start Docker Desktop, wait until it says "Docker Desktop is running", then retry this script.'
    if ($details) {
        Write-Host ''
        Write-Host 'Docker said:'
        Write-Host $details
    }
    Write-Host ''
    Write-Host 'Docker infra was not started because Docker Desktop is not reachable.'
    exit 1
}
$composeVersion = Invoke-NativeQuiet -FilePath 'docker' -ArgumentList @('compose', 'version')
if ($composeVersion.ExitCode -ne 0) {
    $details = Format-NativeFailure -Result $composeVersion
    if ($details) {
        Write-Host $details
    }
    Write-Host 'docker compose is not available.'
    exit 1
}
Write-Host 'Docker Desktop reachable'
Write-Host "Venv Python: $pythonExe"
Write-Host "Model folder: $modelRoot"

Write-Section 'Docker Infra'
$composeUp = Invoke-NativeQuiet -FilePath 'docker' -ArgumentList @('compose', '-f', $composeFile, 'up', '-d')
foreach ($line in $composeUp.Output) {
    Write-Host $line
}
if ($composeUp.ExitCode -ne 0) {
    throw 'Failed to start Docker infra.'
}
Wait-DockerService -Service 'postgres' -CommandArgs @('pg_isready', '-U', 'attendance', '-d', 'attendance') -Name 'Postgres'
Wait-DockerService -Service 'redis' -CommandArgs @('redis-cli', 'ping') -Name 'Redis'
$composePs = Invoke-NativeQuiet -FilePath 'docker' -ArgumentList @('compose', '-f', $composeFile, 'ps')
foreach ($line in $composePs.Output) {
    Write-Host $line
}

if ($RunMigrations) {
    Write-Section 'Migrations'
    $migrationScript = Join-Path $repoRoot 'scripts\run-migrations-local.ps1'
    & powershell -NoProfile -ExecutionPolicy Bypass -File $migrationScript
    if ($LASTEXITCODE -ne 0) {
        throw 'Migration script failed. API and kiosk were not started.'
    }
}

Import-EnvFile -Path $envFile
$apiPath = Join-Path $repoRoot 'apps\api-python'
$existingPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
if ($existingPythonPath) {
    $env:PYTHONPATH = "$repoRoot;$apiPath;$existingPythonPath"
}
else {
    $env:PYTHONPATH = "$repoRoot;$apiPath"
}

Write-Section 'API'
$apiPortProcesses = @(Get-ListeningPortProcesses -Port 8000)
if ($apiPortProcesses.Count -gt 0) {
    foreach ($portProcess in $apiPortProcesses) {
        Write-Host "Port 8000 already listening: PID $($portProcess.PID) $($portProcess.Name)"
    }
    $expectedApi = @($apiPortProcesses | Where-Object { Test-ExpectedApiProcess $_ } | Select-Object -First 1)
    if ($expectedApi.Count -gt 0) {
        Sync-PidFileFromPort -Name 'API' -Port 8000 -PidPath $apiPidFile | Out-Null
    }
    else {
        Write-Warning 'Port 8000 is in use by a process that does not look like this local API. Not starting a duplicate.'
    }
}
else {
    Start-BackgroundProcess `
        -Name 'API' `
        -FilePath $pythonExe `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'apps/api-python', '--host', '0.0.0.0', '--port', '8000') `
        -WorkingDirectory $repoRoot `
        -StdOutPath $apiOutLog `
        -StdErrPath $apiErrLog `
        -PidPath $apiPidFile | Out-Null
}

Write-Section 'Kiosk'
$kioskPortProcesses = @(Get-ListeningPortProcesses -Port 8080)
if ($kioskPortProcesses.Count -gt 0) {
    foreach ($portProcess in $kioskPortProcesses) {
        Write-Host "Port 8080 already listening: PID $($portProcess.PID) $($portProcess.Name)"
    }
    $expectedKiosk = @($kioskPortProcesses | Where-Object { Test-ExpectedKioskProcess $_ } | Select-Object -First 1)
    if ($expectedKiosk.Count -gt 0) {
        Sync-PidFileFromPort -Name 'Kiosk' -Port 8080 -PidPath $kioskPidFile | Out-Null
    }
    else {
        Write-Warning 'Port 8080 is in use by a process that does not look like this local kiosk. Not starting a duplicate.'
    }
}
else {
    Start-BackgroundProcess `
        -Name 'Kiosk' `
        -FilePath $pythonExe `
        -ArgumentList @('-m', 'http.server', '8080', '--directory', 'apps/kiosk-ui/src') `
        -WorkingDirectory $repoRoot `
        -StdOutPath $kioskOutLog `
        -StdErrPath $kioskErrLog `
        -PidPath $kioskPidFile | Out-Null
}

Write-Section 'Health Checks'
Wait-Command -Name 'API health' -TimeoutSeconds 180 -Probe { Test-HttpOk -Url 'http://127.0.0.1:8000/health' }
Sync-PidFileFromPort -Name 'API' -Port 8000 -PidPath $apiPidFile | Out-Null
Wait-Command -Name 'Kiosk HTTP' -TimeoutSeconds 30 -Probe { Test-HttpOk -Url 'http://localhost:8080' }
Sync-PidFileFromPort -Name 'Kiosk' -Port 8080 -PidPath $kioskPidFile | Out-Null

Write-Section 'Ready'
Write-Host 'Docker infra: Postgres + Redis started with docker/docker-compose.infra.yml'
Write-Host 'API: http://localhost:8000'
Write-Host 'Kiosk: http://localhost:8080'
Write-Host "API logs: $apiOutLog ; $apiErrLog"
Write-Host "Kiosk logs: $kioskOutLog ; $kioskErrLog"
Write-Host "API PID file: $apiPidFile"
Write-Host "Kiosk PID file: $kioskPidFile"
Write-Host ''
Write-Host 'Use scripts/status-project-local.ps1 to inspect status.'
Write-Host 'Use scripts/stop-project-local.ps1 to stop local API, kiosk, and Docker infra safely.'
