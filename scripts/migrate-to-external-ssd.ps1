param(
    [string]$SourcePath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$TargetPath = 'E:\Projects\attendance-system',
    [switch]$AllowExistingTarget,
    [switch]$SkipPythonInstall,
    [switch]$SkipNodeInstall,
    [switch]$SkipDocker,
    [switch]$StartDocker,
    [switch]$RunVerification
)

$ErrorActionPreference = 'Stop'

function Invoke-Checked {
    param([string]$FilePath, [string[]]$ArgumentList, [string]$WorkingDirectory = $PWD.Path)
    Write-Host ">> $FilePath $($ArgumentList -join ' ')"
    $p = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -NoNewWindow -PassThru -Wait
    if ($p.ExitCode -ne 0) {
        throw "Command failed with exit code $($p.ExitCode): $FilePath"
    }
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Path -LiteralPath $SourcePath)) { throw "SourcePath does not exist: $SourcePath" }
$SourcePath = (Resolve-Path -LiteralPath $SourcePath).Path
$targetDrive = Split-Path -Qualifier $TargetPath
if (-not (Test-Path -LiteralPath $targetDrive)) { throw "Target drive is not available: $targetDrive" }

if ((Test-Path -LiteralPath $TargetPath) -and -not $AllowExistingTarget) {
    throw "Target already exists: $TargetPath. Re-run with -AllowExistingTarget to merge-copy safely with robocopy."
}
New-Item -ItemType Directory -Force -Path $TargetPath | Out-Null

$excludeDirs = @('.git','.venv','venv','env','node_modules','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.cache','build','dist','.next','.runtime','target')
$excludeFiles = @('*.pyc','*.pyo','*.tmp')

Write-Host "Copying project from $SourcePath to $TargetPath"
$roboArgs = @($SourcePath, $TargetPath, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:2', '/W:2', '/XJ', '/NFL', '/NDL', '/NP')
foreach ($dir in $excludeDirs) { $roboArgs += @('/XD', $dir) }
foreach ($file in $excludeFiles) { $roboArgs += @('/XF', $file) }
& robocopy @roboArgs
$roboCode = $LASTEXITCODE
if ($roboCode -gt 7) { throw "Robocopy failed with exit code $roboCode" }

Write-Host "Scanning copied project"
& powershell -ExecutionPolicy Bypass -File (Join-Path $TargetPath 'scripts\migration-scan.ps1') -ProjectPath $TargetPath -TargetRoot (Split-Path $TargetPath -Parent)

if (-not $SkipPythonInstall) {
    $venvPath = Join-Path $TargetPath '.venv'
    $pythonCmd = if (Test-Command 'py') { 'py' } elseif (Test-Command 'python') { 'python' } else { throw 'Python was not found in PATH' }
    if (-not (Test-Path -LiteralPath $venvPath)) {
        if ($pythonCmd -eq 'py') {
            Invoke-Checked 'py' @('-3.11','-m','venv',$venvPath) $TargetPath
        } else {
            Invoke-Checked 'python' @('-m','venv',$venvPath) $TargetPath
        }
    }
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    Invoke-Checked $venvPython @('-m','pip','install','--upgrade','pip','setuptools','wheel') $TargetPath
    if (Test-Path (Join-Path $TargetPath 'requirements.txt')) {
        Invoke-Checked $venvPython @('-m','pip','install','-r','requirements.txt') $TargetPath
    } elseif (Test-Path (Join-Path $TargetPath 'pyproject.toml')) {
        & $venvPython -m pip install -e ".[dev]"
        if ($LASTEXITCODE -ne 0) {
            Invoke-Checked $venvPython @('-m','pip','install','-e','.') $TargetPath
        }
    } elseif (Test-Path (Join-Path $TargetPath 'setup.py')) {
        Invoke-Checked $venvPython @('-m','pip','install','-e','.') $TargetPath
    } elseif (Test-Path (Join-Path $TargetPath 'Pipfile')) {
        Invoke-Checked $venvPython @('-m','pip','install','pipenv') $TargetPath
        Invoke-Checked (Join-Path $venvPath 'Scripts\pipenv.exe') @('install','--dev') $TargetPath
    }
}

if (-not $SkipNodeInstall) {
    $packageJsons = @(Get-ChildItem -LiteralPath $TargetPath -Recurse -File -Filter package.json -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\node_modules\\' })
    foreach ($pkg in $packageJsons) {
        $dir = Split-Path $pkg.FullName -Parent
        if (Test-Path (Join-Path $dir 'pnpm-lock.yaml')) {
            if (-not (Test-Command 'pnpm')) { Invoke-Checked 'npm' @('install','-g','pnpm') $dir }
            Invoke-Checked 'pnpm' @('install','--frozen-lockfile') $dir
        } elseif (Test-Path (Join-Path $dir 'yarn.lock')) {
            Invoke-Checked 'yarn' @('install','--frozen-lockfile') $dir
        } elseif (Test-Path (Join-Path $dir 'package-lock.json')) {
            Invoke-Checked 'npm' @('ci') $dir
        } else {
            Invoke-Checked 'npm' @('install') $dir
        }
    }
}

if (-not $SkipDocker) {
    $compose = Join-Path $TargetPath 'docker\docker-compose.yml'
    if (Test-Path -LiteralPath $compose) {
        Invoke-Checked 'docker' @('compose','-f',$compose,'pull','--ignore-buildable') $TargetPath
        Invoke-Checked 'docker' @('compose','-f',$compose,'build') $TargetPath
        if ($StartDocker) {
            Invoke-Checked 'docker' @('compose','-f',$compose,'up','-d') $TargetPath
        }
    }
}

if ($RunVerification) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $TargetPath 'scripts\verify-migration.ps1') -ProjectPath $TargetPath
}

Write-Host "Migration copy/setup complete. Original folder was not changed: $SourcePath"
Write-Host "Target folder: $TargetPath"
