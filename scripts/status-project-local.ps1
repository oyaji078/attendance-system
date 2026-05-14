Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot 'docker\docker-compose.infra.yml'
$runtimeDir = Join-Path $repoRoot '.runtime'
$logDir = Join-Path $repoRoot 'logs'
$modelRoot = Join-Path $repoRoot 'models'
$insightfaceModelRoot = Join-Path $modelRoot 'insightface\models\buffalo_l'
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

function Show-PidFile {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        $pidText = (Get-Content -LiteralPath $Path -ErrorAction SilentlyContinue | Select-Object -First 1)
        Write-Host "${Name}: $Path -> $pidText"
    }
    else {
        Write-Host "${Name}: $Path -> missing"
    }
}

function Show-HttpStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
        $body = ''
        if ($response.Content) {
            $body = $response.Content.Trim()
        }
        if ($body.Length -gt 160) {
            $body = $body.Substring(0, 160)
        }
        if ($body) {
            Write-Host "${Name}: HTTP $($response.StatusCode) $body"
        }
        else {
            Write-Host "${Name}: HTTP $($response.StatusCode)"
        }
    }
    catch {
        Write-Host "${Name}: unavailable - $($_.Exception.Message)"
    }
}

function Show-LogTail {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "$Path -> missing"
        return
    }

    Write-Host "$Path -> last 20 lines"
    $lines = @(Get-Content -LiteralPath $Path -Tail 20 -ErrorAction SilentlyContinue)
    if ($lines.Count -eq 0) {
        Write-Host '<empty>'
        return
    }

    foreach ($line in $lines) {
        Write-Host $line
    }
}

Set-Location -LiteralPath $repoRoot

Write-Section 'Docker Desktop'
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $dockerInfo = Invoke-NativeQuiet -FilePath 'docker' -ArgumentList @('info')
    if ($dockerInfo.ExitCode -eq 0) {
        Write-Host 'Docker Desktop reachable'
    }
    else {
        Write-Host 'Docker Desktop not reachable'
        $details = @($dockerInfo.Output | Where-Object { $_ } | Select-Object -First 3)
        foreach ($line in $details) {
            Write-Host "  $line"
        }
    }
}
else {
    Write-Host 'docker command not found'
}

Write-Section 'Docker Infra'
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $composeStatus = Invoke-NativeQuiet -FilePath 'docker' -ArgumentList @('compose', '-f', $composeFile, 'ps')
    if ($composeStatus.ExitCode -eq 0) {
        foreach ($line in $composeStatus.Output) {
            Write-Host $line
        }
    }
    else {
        Write-Host 'Docker infra status unavailable'
        $details = @($composeStatus.Output | Where-Object { $_ } | Select-Object -First 3)
        foreach ($line in $details) {
            Write-Host "  $line"
        }
    }
}
else {
    Write-Host 'docker command not found'
}

Write-Section 'Ports'
foreach ($port in @(5432, 6379, 8000, 8080)) {
    $portProcesses = @(Get-ListeningPortProcesses -Port $port)
    if ($portProcesses.Count -eq 0) {
        Write-Host "Port ${port}: not listening"
    }
    else {
        foreach ($portProcess in $portProcesses) {
            Write-Host "Port ${port}: PID $($portProcess.PID) $($portProcess.Name)"
            if ($portProcess.CommandLine) {
                Write-Host "  $($portProcess.CommandLine)"
            }
        }
    }
}

Write-Section 'HTTP'
Show-HttpStatus -Name 'API health' -Url 'http://localhost:8000/health'
Show-HttpStatus -Name 'Kiosk' -Url 'http://localhost:8080'

Write-Section 'PID Files'
Show-PidFile -Name 'API' -Path $apiPidFile
Show-PidFile -Name 'Kiosk' -Path $kioskPidFile

Write-Section 'Model Folder'
if (Test-Path -LiteralPath $modelRoot) {
    Write-Host "Models: $modelRoot -> present"
}
else {
    Write-Host "Models: $modelRoot -> missing"
}
if (Test-Path -LiteralPath $insightfaceModelRoot) {
    $modelFiles = @(Get-ChildItem -LiteralPath $insightfaceModelRoot -File -ErrorAction SilentlyContinue)
    Write-Host "InsightFace buffalo_l: $insightfaceModelRoot -> present ($($modelFiles.Count) files)"
}
else {
    Write-Host "InsightFace buffalo_l: $insightfaceModelRoot -> missing"
}

Write-Section 'Logs'
Write-Host "API stdout: $apiOutLog"
Write-Host "API stderr: $apiErrLog"
Write-Host "Kiosk stdout: $kioskOutLog"
Write-Host "Kiosk stderr: $kioskErrLog"

Write-Section 'Error Log Tails'
Show-LogTail -Path $apiErrLog
Show-LogTail -Path $kioskErrLog
