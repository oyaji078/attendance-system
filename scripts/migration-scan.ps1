param(
    [string]$ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$TargetRoot = 'E:\Projects',
    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'

function Write-Section {
    param([System.Text.StringBuilder]$Builder, [string]$Title)
    [void]$Builder.AppendLine("")
    [void]$Builder.AppendLine("## $Title")
    [void]$Builder.AppendLine("")
}

function Get-RelativePathSafe {
    param([string]$Base, [string]$Path)
    try {
        $baseFull = [System.IO.Path]::GetFullPath($Base).TrimEnd('\') + '\'
        $pathFull = [System.IO.Path]::GetFullPath($Path)
        $baseUri = [Uri]$baseFull
        $pathUri = [Uri]$pathFull
        return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
    } catch {
        return $Path
    }
}

function Find-Files {
    param([string[]]$Names)
    Get-ChildItem -LiteralPath $ProjectPath -Force -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $Names -contains $_.Name } |
        ForEach-Object { Get-RelativePathSafe $ProjectPath $_.FullName } |
        Sort-Object
}

function Find-Extensions {
    param([string[]]$Extensions)
    Get-ChildItem -LiteralPath $ProjectPath -Force -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $Extensions -contains $_.Extension.ToLowerInvariant() } |
        Sort-Object Length -Descending |
        ForEach-Object {
            [pscustomobject]@{
                SizeMB = [math]::Round($_.Length / 1MB, 2)
                Path = Get-RelativePathSafe $ProjectPath $_.FullName
            }
        }
}

function Get-ComposeServices {
    param([string]$ComposePath)
    $services = New-Object System.Collections.Generic.List[string]
    $inServices = $false
    foreach ($line in Get-Content -LiteralPath $ComposePath) {
        if ($line -match '^services:\s*$') {
            $inServices = $true
            continue
        }
        if ($inServices -and $line -match '^[A-Za-z0-9_-]+:\s*$') {
            break
        }
        if ($inServices -and $line -match '^\s{2}([A-Za-z0-9_.-]+):\s*$') {
            $services.Add($Matches[1])
        }
    }
    return $services
}

if (-not (Test-Path -LiteralPath $ProjectPath)) {
    throw "ProjectPath does not exist: $ProjectPath"
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ReportPath) {
    $ReportPath = Join-Path $ProjectPath 'migration_report.md'
}

$projectName = Split-Path $ProjectPath -Leaf
$targetPath = Join-Path $TargetRoot $projectName
$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
$sb = [System.Text.StringBuilder]::new()

[void]$sb.AppendLine("# Migration Audit Report")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("- Generated: $now")
[void] $sb.AppendLine(("- Source: ``{0}``" -f $ProjectPath))
[void] $sb.AppendLine(("- Recommended target: ``{0}``" -f $targetPath))
[void]$sb.AppendLine("- Safety mode: copy-first, no delete")

Write-Section $sb 'Detected Project Files'
$importantNames = @(
    'requirements.txt','pyproject.toml','setup.py','Pipfile','poetry.lock','environment.yml',
    'package.json','pnpm-lock.yaml','yarn.lock','package-lock.json','Makefile','Cargo.toml','Cargo.lock',
    'Dockerfile','docker-compose.yml','docker-compose.yaml','compose.yml','compose.yaml','alembic.ini'
)
$detected = Find-Files $importantNames
if ($detected) {
    $detected | ForEach-Object { [void] $sb.AppendLine(("- ``{0}``" -f $_)) }
} else {
    [void]$sb.AppendLine("- None found")
}

Write-Section $sb 'Python'
$pyproject = Join-Path $ProjectPath 'pyproject.toml'
if (Test-Path -LiteralPath $pyproject) {
    $py = Get-Content -Raw -LiteralPath $pyproject
    $requires = if ($py -match 'requires-python\s*=\s*"([^"]+)"') { $Matches[1] } else { 'not declared' }
    [void] $sb.AppendLine("- ``pyproject.toml``: present")
    [void] $sb.AppendLine(("- Requires Python: ``{0}``" -f $requires))
    $mlHits = Select-String -LiteralPath $pyproject -Pattern 'torch|tensorflow|onnxruntime|insightface|opencv|cv2|cuda|cudnn|numpy|scipy|scikit|xgboost|lightgbm|dlib|face-recognition' -AllMatches -ErrorAction SilentlyContinue
    if ($mlHits) {
        [void]$sb.AppendLine("- ML/CV dependencies detected:")
        $mlHits.Matches.Value | Sort-Object -Unique | ForEach-Object { [void] $sb.AppendLine(("  - ``{0}``" -f $_)) }
    }
}

Write-Section $sb 'Node.js'
$packageFiles = Find-Files @('package.json','pnpm-lock.yaml','yarn.lock','package-lock.json')
if ($packageFiles) {
    $packageFiles | ForEach-Object { [void] $sb.AppendLine(("- ``{0}``" -f $_)) }
} else {
    [void]$sb.AppendLine("- No Node package manifest or lockfile found")
}

Write-Section $sb 'Docker'
$composeFiles = Find-Files @('docker-compose.yml','docker-compose.yaml','compose.yml','compose.yaml')
if ($composeFiles) {
    foreach ($rel in $composeFiles) {
        $full = if ([System.IO.Path]::IsPathRooted($rel)) { $rel } else { Join-Path $ProjectPath $rel }
        [void] $sb.AppendLine(("- Compose: ``{0}``" -f $rel))
        $services = @(Get-ComposeServices $full)
        if ($services.Count -gt 0) {
            [void]$sb.AppendLine("  - Services: " + ($services -join ', '))
        }
        $content = Get-Content -Raw -LiteralPath $full
        if ($content -match 'pgvector|postgres') { [void]$sb.AppendLine("  - PostgreSQL/pgvector detected") }
        if ($content -match 'redis') { [void]$sb.AppendLine("  - Redis detected") }
        if ($content -match '(?s)volumes:\s*.*postgres-data') { [void]$sb.AppendLine("  - Named database volume: ``postgres-data``") }
    }
} else {
    [void]$sb.AppendLine("- No Docker Compose files found")
}
$dockerfiles = Get-ChildItem -LiteralPath $ProjectPath -Force -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq 'Dockerfile' -or $_.Name -like '*.Dockerfile' } |
    ForEach-Object { Get-RelativePathSafe $ProjectPath $_.FullName } | Sort-Object
if ($dockerfiles) {
    [void]$sb.AppendLine("- Dockerfiles:")
    $dockerfiles | ForEach-Object { [void] $sb.AppendLine(("  - ``{0}``" -f $_)) }
}

Write-Section $sb 'Environment Files'
$envFiles = Get-ChildItem -LiteralPath $ProjectPath -Force -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '.env' -or $_.Name -like '.env.*' -or $_.Name -like '*.env' } |
    Sort-Object FullName
foreach ($file in $envFiles) {
    [void] $sb.AppendLine(("- ``{0}``" -f (Get-RelativePathSafe $ProjectPath $file.FullName)))
    $keys = Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*[^#][A-Za-z_][A-Za-z0-9_]*\s*=' } |
        ForEach-Object { ($_ -split '=', 2)[0].Trim() } |
        Sort-Object -Unique
    if ($keys) { [void]$sb.AppendLine("  - Keys: " + ($keys -join ', ')) }
}

Write-Section $sb 'Important Data And Generated Folders'
$folderNames = 'data','datasets','dataset','models','checkpoints','uploads','media','logs','notebooks','migrations','scripts','config','.runtime','.venv','venv','env','node_modules','target','dist','build','.next'
Get-ChildItem -LiteralPath $ProjectPath -Force -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $folderNames -contains $_.Name -and $_.FullName -notmatch '\\.git\\|\\node_modules\\|\\.venv\\|\\venv\\|\\.runtime\\' } |
    Sort-Object FullName |
    ForEach-Object { [void] $sb.AppendLine(("- ``{0}``" -f (Get-RelativePathSafe $ProjectPath $_.FullName))) }

Write-Section $sb 'Model, Dataset, Archive, And Database-Like Files'
$largeData = Find-Extensions @('.pt','.pth','.h5','.keras','.onnx','.pkl','.joblib','.safetensors','.bin','.gguf','.zip','.parquet','.csv','.db','.sqlite','.sqlite3')
if ($largeData) {
    $largeData | Select-Object -First 80 | ForEach-Object {
        [void] $sb.AppendLine(("- {0} MB ``{1}``" -f $_.SizeMB, $_.Path))
    }
} else {
    [void]$sb.AppendLine("- None found")
}

Write-Section $sb 'Hardcoded Paths That May Break'
$searchFiles = Get-ChildItem -LiteralPath $ProjectPath -Force -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notmatch '\\.git\\|\\node_modules\\|\\.venv\\|\\venv\\|\\.runtime\\|\\__pycache__\\' -and
        $_.Name -ne 'migration_report.md' -and
        $_.Extension.ToLowerInvariant() -notin @('.pyc','.pyo','.jpg','.jpeg','.png','.gif','.webp','.onnx','.zip','.db','.sqlite','.sqlite3','.dump')
    }
$pathHits = $searchFiles | Select-String -Pattern 'D:\\cnn|D:\\PythonVenvs|E:\\|/app/models|/app/data' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -notmatch '\\.git\\|\\node_modules\\|\\.venv\\|\\venv\\|\\.runtime\\' } |
    Select-Object -First 120
if ($pathHits) {
    foreach ($hit in $pathHits) {
        [void] $sb.AppendLine(("- ``{0}:{1}``: {2}" -f (Get-RelativePathSafe $ProjectPath $hit.Path), $hit.LineNumber, $hit.Line.Trim()))
    }
} else {
    [void]$sb.AppendLine("- None found")
}

Write-Section $sb 'Docker Runtime Inspection'
try {
    $dockerPs = docker ps --format '{{.Names}} | {{.Image}} | {{.Status}}' 2>&1
    if ($LASTEXITCODE -eq 0) {
        [void]$sb.AppendLine("- Running containers:")
        if ($dockerPs) { $dockerPs | ForEach-Object { [void] $sb.AppendLine(("  - ``{0}``" -f $_)) } } else { [void]$sb.AppendLine("  - none") }
        $volumes = docker volume ls --format '{{.Name}}' 2>&1
        [void]$sb.AppendLine("- Docker volumes:")
        if ($volumes) { $volumes | ForEach-Object { [void] $sb.AppendLine(("  - ``{0}``" -f $_)) } } else { [void]$sb.AppendLine("  - none") }
    } else {
        [void]$sb.AppendLine("- Docker engine not reachable: $dockerPs")
    }
} catch {
    [void]$sb.AppendLine("- Docker runtime inspection failed: $($_.Exception.Message)")
}

Write-Section $sb 'Recommended Exclusions'
@('.venv','venv','env','node_modules','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.cache','build','dist','.next','.runtime','target') |
    ForEach-Object { [void] $sb.AppendLine(("- ``{0}``" -f $_)) }

Set-Content -LiteralPath $ReportPath -Value $sb.ToString() -Encoding UTF8
Write-Host "Wrote migration report: $ReportPath"
