Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$composeFile = 'docker/docker-compose.infra.yml'

function Invoke-DockerQuiet {
    param([Parameter(Mandatory = $true)][string[]]$ArgumentList)

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

        $output = @(& docker @ArgumentList 2>&1 | ForEach-Object { [string]$_ })
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

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'docker command not found. Start Docker Desktop and make sure Docker CLI is on PATH.'
    exit 1
}

$dockerInfo = Invoke-DockerQuiet -ArgumentList @('info')
if ($dockerInfo.ExitCode -ne 0) {
    Write-Host 'Docker Desktop is not reachable.'
    Write-Host 'Start Docker Desktop, wait until it says "Docker Desktop is running", then retry this script.'
    $details = @($dockerInfo.Output | Where-Object { $_ } | Select-Object -First 4)
    if ($details.Count -gt 0) {
        Write-Host ''
        Write-Host 'Docker said:'
        foreach ($line in $details) {
            Write-Host $line
        }
    }
    Write-Host ''
    Write-Host 'Docker infra was not started because Docker Desktop is not reachable.'
    exit 1
}

$composeUp = Invoke-DockerQuiet -ArgumentList @('compose', '-f', $composeFile, 'up', '-d')
foreach ($line in $composeUp.Output) {
    Write-Host $line
}
if ($composeUp.ExitCode -ne 0) {
    throw 'Failed to start Docker infra.'
}

$composePs = Invoke-DockerQuiet -ArgumentList @('compose', '-f', $composeFile, 'ps')
foreach ($line in $composePs.Output) {
    Write-Host $line
}
if ($composePs.ExitCode -ne 0) {
    throw 'Failed to read Docker infra status.'
}
