Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = 'D:\PythonVenvs\attendance-api'
$activateScript = Join-Path $venvRoot 'Scripts\Activate.ps1'
$pythonExe = Join-Path $venvRoot 'Scripts\python.exe'
$envFile = Join-Path $repoRoot '.env.local-api'

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

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Venv python not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $activateScript)) {
    throw "Venv activation script not found: $activateScript"
}

Set-Location -LiteralPath $repoRoot
. $activateScript
Import-EnvFile -Path $envFile

# ---- Port availability check ----
$apiPortProcesses = @(Get-ListeningPortProcesses -Port 8000)
if ($apiPortProcesses.Count -gt 0) {
    foreach ($portProcess in $apiPortProcesses) {
        Write-Host "Port 8000 already listening: PID $($portProcess.PID) $($portProcess.Name)"
    }
    $expectedApi = @($apiPortProcesses | Where-Object { Test-ExpectedApiProcess $_ } | Select-Object -First 1)
    if ($expectedApi.Count -gt 0) {
        Write-Host ""
        Write-Host "Validating existing API..."
        if (Test-HttpOk -Url 'http://127.0.0.1:8000/health') {
            Write-Host "API already running on port 8000"
            exit 0
        }
        else {
            Write-Host "Stopping stale API PID $($expectedApi.PID)..."
            Stop-Process -Id $expectedApi.PID -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
    }
    else {
        Write-Warning 'Port 8000 is in use by a process that does not look like this local API. Not starting a duplicate.'
        exit 1
    }
}

Write-Host "Starting API..."
$apiPath = Join-Path $repoRoot 'apps\api-python'
$existingPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
if ($existingPythonPath) {
    $env:PYTHONPATH = "$repoRoot;$apiPath;$existingPythonPath"
}
else {
    $env:PYTHONPATH = "$repoRoot;$apiPath"
}

& $pythonExe -m uvicorn app.main:app --app-dir apps/api-python --host 0.0.0.0 --port 8000
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
