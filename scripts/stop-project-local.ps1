param(
    [switch]$ForceDetectedPorts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot 'docker\docker-compose.infra.yml'
$runtimeDir = Join-Path $repoRoot '.runtime'
$apiPidFile = Join-Path $runtimeDir 'api.pid'
$kioskPidFile = Join-Path $runtimeDir 'kiosk.pid'

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)
    Write-Host ''
    Write-Host "== $Title =="
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

function Test-ProcessOwnsPort {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -eq $ProcessId } |
        Select-Object -First 1
    return ($null -ne $connection)
}

function Stop-ProcessById {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host "$Name PID $ProcessId is not running"
        return $true
    }

    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped $Name PID $ProcessId"
        return $true
    }
    catch {
        Write-Warning "Could not stop $Name PID ${ProcessId}: $($_.Exception.Message)"
        return $false
    }
}

function Stop-FromPidFile {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$PidPath,
        [Parameter(Mandatory = $true)][int]$Port
    )

    if (-not (Test-Path -LiteralPath $PidPath)) {
        return $false
    }

    $rawPid = (Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    $processId = 0
    if (-not [int]::TryParse([string]$rawPid, [ref]$processId)) {
        Write-Warning "Invalid PID file for ${Name}: $PidPath"
        Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
        return $false
    }

    if (-not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Write-Host "$Name PID file points to a stopped process: $processId"
        Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
        return $false
    }

    if (-not (Test-ProcessOwnsPort -ProcessId $processId -Port $Port)) {
        Write-Warning "$Name PID $processId is running but does not own port $Port. Removing stale PID file."
        Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
        return $false
    }

    if (Stop-ProcessById -ProcessId $processId -Name $Name) {
        Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
    }
    return $true
}

function Stop-DetectedPort {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][scriptblock]$ExpectedProcess
    )

    $portProcesses = @(Get-ListeningPortProcesses -Port $Port)
    if ($portProcesses.Count -eq 0) {
        Write-Host "$Name port $Port is not listening"
        return
    }

    foreach ($portProcess in $portProcesses) {
        $looksExpected = & $ExpectedProcess $portProcess
        Write-Host "$Name candidate on port ${Port}: PID $($portProcess.PID) $($portProcess.Name)"
        if (-not $looksExpected) {
            Write-Warning "PID $($portProcess.PID) does not look like the local $Name command. Leaving it alone."
            continue
        }

        $shouldStop = $ForceDetectedPorts
        if (-not $shouldStop) {
            $answer = Read-Host "Stop $Name PID $($portProcess.PID)? [y/N]"
            $shouldStop = ($answer -match '^(y|yes)$')
        }

        if ($shouldStop) {
            Stop-ProcessById -ProcessId $portProcess.PID -Name $Name | Out-Null
        }
        else {
            Write-Host "Skipped $Name PID $($portProcess.PID)"
        }
    }
}

Set-Location -LiteralPath $repoRoot

Write-Section 'Local Processes'
$apiHandled = Stop-FromPidFile -Name 'API' -PidPath $apiPidFile -Port 8000
if (-not $apiHandled) {
    Stop-DetectedPort -Name 'API' -Port 8000 -ExpectedProcess { param($portProcess) Test-ExpectedApiProcess $portProcess }
}

$kioskHandled = Stop-FromPidFile -Name 'Kiosk' -PidPath $kioskPidFile -Port 8080
if (-not $kioskHandled) {
    Stop-DetectedPort -Name 'Kiosk' -Port 8080 -ExpectedProcess { param($portProcess) Test-ExpectedKioskProcess $portProcess }
}

Write-Section 'Docker Infra'
if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker compose -f $composeFile stop
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'docker compose stop reported a failure.'
    }
}
else {
    Write-Warning 'docker command not found. Docker infra was not stopped.'
}

Write-Section 'Final Status'
foreach ($port in @(5432, 6379, 8000, 8080)) {
    $portProcesses = @(Get-ListeningPortProcesses -Port $port)
    if ($portProcesses.Count -eq 0) {
        Write-Host "Port ${port}: not listening"
    }
    else {
        foreach ($portProcess in $portProcesses) {
            Write-Host "Port ${port}: PID $($portProcess.PID) $($portProcess.Name)"
        }
    }
}
