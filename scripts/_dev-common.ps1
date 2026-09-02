Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RepoRoot = Split-Path -Parent $PSScriptRoot
$script:InfraComposeFile = Join-Path $script:RepoRoot 'docker\docker-compose.infra.yml'
$script:RuntimeDir = Join-Path $script:RepoRoot '.runtime'
$script:LogDir = Join-Path $script:RepoRoot 'logs'
$script:ApiPidFile = Join-Path $script:RuntimeDir 'api.pid'
$script:KioskPidFile = Join-Path $script:RuntimeDir 'kiosk.pid'

function Get-RepoRoot {
    return $script:RepoRoot
}

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)
    Write-Host ''
    Write-Host "== $Title =="
}

function Get-Timestamp {
    return (Get-Date).ToString('yyyyMMdd_HHmmss')
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Import-EnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
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

function Import-ProjectEnv {
    Import-EnvFile -Path (Join-Path $script:RepoRoot '.env')
    Import-EnvFile -Path (Join-Path $script:RepoRoot '.env.local-api')

    if (-not $env:POSTGRES_HOST) { $env:POSTGRES_HOST = '127.0.0.1' }
    if (-not $env:POSTGRES_PORT) { $env:POSTGRES_PORT = '5432' }
    if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = 'attendance' }
    if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = 'attendance' }
    if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = 'attendance' }
    if (-not $env:REDIS_URL) { $env:REDIS_URL = 'redis://127.0.0.1:6379/0' }
}

function Resolve-ProjectPython {
    $candidates = @()
    if ($env:ATTENDANCE_PYTHON) {
        $candidates += $env:ATTENDANCE_PYTHON
    }

    $repoParent = Split-Path -Parent $script:RepoRoot
    $venvCandidates = @(
        (Join-Path $script:RepoRoot '.venv\Scripts\python.exe'),
        (Join-Path $repoParent '.venv\Scripts\python.exe'),
        (Join-Path $script:RepoRoot '.venv\bin\python'),
        (Join-Path $repoParent '.venv\bin\python'),
        'D:\PythonVenvs\attendance-api\Scripts\python.exe'
    )

    foreach ($candidate in $venvCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $candidates += $candidate
        }
    }

    $candidates += 'python'

    foreach ($candidate in $candidates) {
        if ($candidate -eq 'python') {
            $command = Get-Command python -ErrorAction SilentlyContinue
            if ($command) {
                return $command.Source
            }
            continue
        }

        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw 'Python was not found. Install Python 3.11+ or set ATTENDANCE_PYTHON to the project venv python.exe.'
}

function Test-DockerReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker CLI is not available on PATH.'
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Desktop is not reachable. Start Docker Desktop and retry.'
    }
}

function Start-Infra {
    Test-DockerReady
    Push-Location -LiteralPath $script:RepoRoot
    try {
        & docker compose -f $script:InfraComposeFile up -d
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to start Docker infra.'
        }
    }
    finally {
        Pop-Location
    }
}

function Stop-Infra {
    Test-DockerReady
    Push-Location -LiteralPath $script:RepoRoot
    try {
        & docker compose -f $script:InfraComposeFile stop
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to stop Docker infra.'
        }
    }
    finally {
        Pop-Location
    }
}

function Wait-PostgresReady {
    param([int]$TimeoutSeconds = 60)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        & docker exec docker-postgres-1 pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host 'PostgreSQL is ready.'
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "PostgreSQL was not ready within $TimeoutSeconds seconds."
}

function Wait-RedisReady {
    param([int]$TimeoutSeconds = 60)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $output = & docker exec docker-redis-1 redis-cli PING 2>$null
        if ($LASTEXITCODE -eq 0 -and (($output | Select-Object -First 1) -eq 'PONG')) {
            Write-Host 'Redis is ready.'
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "Redis was not ready within $TimeoutSeconds seconds."
}

function New-PortProcessInfo {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [int]$ReportedProcessId = 0
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    $cimProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue

    $name = if ($process) { $process.ProcessName }
    elseif ($cimProcess) { [IO.Path]::GetFileNameWithoutExtension([string]$cimProcess.Name) }
    else { '<unknown>' }

    [pscustomobject]@{
        Port        = $Port
        PID         = $ProcessId
        ReportedPID = if ($ReportedProcessId -ne 0) { $ReportedProcessId } else { $ProcessId }
        Inherited   = ($ReportedProcessId -ne 0 -and $ReportedProcessId -ne $ProcessId)
        Name        = $name
        Path        = if ($process) { $process.Path } else { $null }
        CommandLine = if ($cimProcess) { $cimProcess.CommandLine } else { $null }
        Accessible  = ($null -ne $process -or $null -ne $cimProcess)
    }
}

function Get-ChildProcesses {
    param(
        [Parameter(Mandatory = $true)][int]$ParentProcessId,
        [datetime]$CreatedAtOrAfter = [datetime]::MinValue
    )

    # Windows leaves a dead parent's PID on its orphans and recycles PIDs, so an
    # unrelated process can advertise ParentProcessId = $ParentProcessId. A real
    # child cannot predate its parent, so the timestamp filters those out.
    # conhost/WerFault are console and crash-report helpers, never socket owners.
    @(
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" -ErrorAction SilentlyContinue |
            Where-Object {
                [IO.Path]::GetFileNameWithoutExtension([string]$_.Name) -notin @('conhost', 'WerFault') -and
                $null -ne $_.CreationDate -and
                $_.CreationDate -ge $CreatedAtOrAfter
            }
    )
}

function Get-ListeningPortProcesses {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    $seen = @{}

    foreach ($group in @($connections | Group-Object -Property OwningProcess)) {
        $ownerId = [int]$group.Name
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerId" -ErrorAction SilentlyContinue

        # Windows reports the PID that CREATED the listening socket. When that
        # process exits, a child that inherited the socket handle (the uvicorn
        # --reload worker, an http.server subprocess) keeps the port open while
        # netstat still names the dead parent. Resolve to the live heirs so the
        # port owner can actually be identified and stopped.
        $candidateIds = if ($owner) { @($ownerId) }
        else {
            $socketTimes = @($group.Group | Where-Object { $null -ne $_.CreationTime } | ForEach-Object { $_.CreationTime } | Sort-Object)
            # The heir inherited this socket, so it cannot predate it. Allow a
            # small skew for the gap between socket bind and child spawn.
            $cutoff = if ($socketTimes.Count -gt 0) { $socketTimes[0].AddSeconds(-5) } else { [datetime]::MinValue }

            $heirs = @(Get-ChildProcesses -ParentProcessId $ownerId -CreatedAtOrAfter $cutoff)
            if ($heirs.Count -gt 0) { @($heirs | ForEach-Object { [int]$_.ProcessId }) } else { @($ownerId) }
        }

        foreach ($candidateId in $candidateIds) {
            if ($seen.ContainsKey($candidateId)) {
                continue
            }
            $seen[$candidateId] = $true
            New-PortProcessInfo -Port $Port -ProcessId $candidateId -ReportedProcessId $ownerId
        }
    }
}

function Test-ExpectedApiProcess {
    param(
        [Parameter(Mandatory = $true)]$PortProcess,
        [int]$Port = 8000
    )
    $commandLine = [string]$PortProcess.CommandLine
    if ($commandLine -like "*uvicorn*app.main:app*--port*$Port*") {
        return $true
    }

    # Some Windows Python Store processes hide CommandLine. Port is reserved
    # for this project's local API workflow, so a Python listener there is treated
    # as restartable by the dev scripts.
    return ($PortProcess.Name -like 'python*' -and [string]::IsNullOrWhiteSpace($commandLine))
}

function Test-ExpectedKioskProcess {
    param([Parameter(Mandatory = $true)]$PortProcess)
    $commandLine = [string]$PortProcess.CommandLine
    if (
        $commandLine -like '*http.server*8080*apps/kiosk-ui/src*' -or
        $commandLine -like '*http.server*8080*apps\kiosk-ui\src*'
    ) {
        return $true
    }

    # Same Windows CommandLine caveat as the API guard. Port 8080 is reserved for
    # the static kiosk server in the local dev workflow.
    return ($PortProcess.Name -like 'python*' -and [string]::IsNullOrWhiteSpace($commandLine))
}

function Stop-ProcessTree {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    $self = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $self) {
        return
    }

    $selfCreated = if ($null -ne $self.CreationDate) { $self.CreationDate } else { [datetime]::MinValue }
    foreach ($child in @(Get-ChildProcesses -ParentProcessId $ProcessId -CreatedAtOrAfter $selfCreated)) {
        Stop-ProcessTree -ProcessId ([int]$child.ProcessId)
    }

    if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        return
    }

    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    }
    catch {
        Write-Warning "Could not stop PID ${ProcessId}: $($_.Exception.Message)"
    }

    $deadline = (Get-Date).AddSeconds(8)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
            return
        }
        Start-Sleep -Milliseconds 200
    }

    try {
        taskkill /F /PID $ProcessId *> $null
    }
    catch {
        Write-Warning "taskkill fallback failed for PID $ProcessId."
    }

    $deadline = (Get-Date).AddSeconds(3)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
            return
        }
        Start-Sleep -Milliseconds 200
    }

    Write-Warning "PID $ProcessId is still alive after a force stop."
}

function Stop-ProcessByPidFile {
    param(
        [Parameter(Mandatory = $true)][string]$PidPath,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if (-not (Test-Path -LiteralPath $PidPath)) {
        return
    }

    $pidValue = (Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($pidValue -and $pidValue -match '^\d+$') {
        $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Stopping $Name process $pidValue (and descendants)."
            Stop-ProcessTree -ProcessId ([int]$pidValue)
        }
    }
    Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
}

function Stop-ExpectedPortProcess {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][ValidateSet('api', 'kiosk')][string]$Kind
    )

    $portProcesses = @(Get-ListeningPortProcesses -Port $Port)
    foreach ($portProcess in $portProcesses) {
        $isExpected = if ($Kind -eq 'api') {
            Test-ExpectedApiProcess -PortProcess $portProcess -Port $Port
        }
        else {
            Test-ExpectedKioskProcess -PortProcess $portProcess
        }

        if ($isExpected) {
            $origin = if ($portProcess.Inherited) { " (inherited socket from exited PID $($portProcess.ReportedPID))" } else { '' }
            Write-Host "Stopping existing $Kind process $($portProcess.PID)$origin on port $Port."
            Stop-ProcessTree -ProcessId $portProcess.PID
        }
    }

    $remaining = @(Get-ListeningPortProcesses -Port $Port)
    if ($remaining.Count -gt 0) {
        foreach ($remainingProcess in $remaining) {
            Write-Warning "Port $Port is still held by PID $($remainingProcess.PID) after stop attempt."
        }
    }
}

function Assert-PortAvailable {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    $portProcesses = @(Get-ListeningPortProcesses -Port $Port)
    if ($portProcesses.Count -eq 0) {
        return
    }

    $hasStalePort = $false
    foreach ($pp in $portProcesses) {
        if (-not $pp.Accessible) {
            $hasStalePort = $true
            break
        }
    }

    $details = $portProcesses | ForEach-Object {
        $origin = if ($_.Inherited) { " (inherited socket from exited PID $($_.ReportedPID))" } else { '' }
        "PID=$($_.PID)$origin Name=$($_.Name) CommandLine=$($_.CommandLine)"
    }

    if ($hasStalePort) {
        Write-Host ''
        Write-Host "WARNING: Port $Port appears to be held by a stale Windows socket, Docker/WSL backend, or an inaccessible process." -ForegroundColor Yellow
        Write-Host ''
        Write-Host 'Recommended steps to resolve:' -ForegroundColor Yellow
        Write-Host "  1. netstat -aon | findstr `":$Port`""
        Write-Host '  2. wsl --shutdown'
        Write-Host '  3. Restart Docker Desktop'
        Write-Host "  4. docker start docker-postgres-1 docker-redis-1"
        Write-Host '  5. Restart the computer if the port remains stuck'
        Write-Host ''
        Write-Host 'Or use a different port with -ApiPort (for API) or -KioskPort (for kiosk UI).' -ForegroundColor Yellow
        Write-Host ''
    }

    throw "Port $Port is already used by a non-project process for $Purpose.`n$($details -join "`n")"
}

function Start-BackgroundCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$OutLog,
        [Parameter(Mandatory = $true)][string]$ErrLog,
        [Parameter(Mandatory = $true)][string]$PidPath
    )

    Ensure-Directory -Path $script:RuntimeDir
    Ensure-Directory -Path $script:LogDir

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $PidPath -Value ([string]$process.Id) -Encoding ASCII
    return $process
}

function Get-HttpStatusCode {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 5
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
        return [int]$response.StatusCode
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            return [int]$_.Exception.Response.StatusCode
        }
        return $null
    }
}

function Wait-HttpNot404 {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastStatus = $null
    while ((Get-Date) -lt $deadline) {
        $lastStatus = Get-HttpStatusCode -Url $Url -TimeoutSeconds 5
        if ($null -ne $lastStatus -and $lastStatus -ne 404) {
            Write-Host "$Url returned HTTP $lastStatus."
            return $lastStatus
        }
        Start-Sleep -Seconds 2
    }

    throw "$Url did not return a non-404 response within $TimeoutSeconds seconds. Last status: $lastStatus"
}

function Initialize-LocalEnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    $example = Join-Path $script:RepoRoot '.env.example'
    if (Test-Path -LiteralPath $Path) {
        Write-Host "Environment file already exists: $Path"
        return
    }
    if (-not (Test-Path -LiteralPath $example)) {
        throw "Cannot create $Path because .env.example is missing."
    }

    $content = Get-Content -LiteralPath $example -Raw
    $content = $content.Replace('POSTGRES_PASSWORD=CHANGE_ME_POSTGRES', 'POSTGRES_PASSWORD=attendance')
    $content = $content.Replace('AUTH_SECRET_KEY=CHANGE_ME_SECRET_KEY_MIN_32_CHARS', 'AUTH_SECRET_KEY=attendance-local-dev-change-this-minimum-32')
    $content = $content.Replace('DEFAULT_ADMIN_PASSWORD=CHANGE_ME_ADMIN_PASSWORD', 'DEFAULT_ADMIN_PASSWORD=admin-local-1234')
    Set-Content -LiteralPath $Path -Value $content -Encoding ASCII
    Write-Host "Created environment file: $Path"
}
