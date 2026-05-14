Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$cookieJar = Join-Path $runtimeDir 'admin-cookies.txt'
$loginJson = Join-Path $runtimeDir 'login-payload.json'
$tempOutput = Join-Path $runtimeDir 'curl-output.txt'
$baseUrl = 'http://localhost:8000'

$loginPayload = '{"username":"admin","password":"admin-local-1234"}'
Set-Content -LiteralPath $loginJson -Value $loginPayload -NoNewline -ErrorAction Stop

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)
    Write-Host ''
    Write-Host "== $Title =="
}

function Get-HttpCodeOnly {
    param([Parameter(Mandatory = $true)][string]$Url)

    Remove-Item -LiteralPath $tempOutput -Force -ErrorAction SilentlyContinue
    $result = & curl.exe -s -o $tempOutput -w "%{http_code}" -b $cookieJar -c $cookieJar $Url 2>&1
    $statusCode = 0
    if ($result -match '^\d+$') {
        $statusCode = [int]$result
    }
    $body = ''
    if (Test-Path -LiteralPath $tempOutput) {
        $body = Get-Content -Raw -LiteralPath $tempOutput -ErrorAction SilentlyContinue
        if (-not $body) { $body = '' }
    }
    return @{ HTTPCode = $statusCode; Body = $body }
}

function Get-HttpCodePost {
    param([Parameter(Mandatory = $true)][string]$Url)

    Remove-Item -LiteralPath $tempOutput -Force -ErrorAction SilentlyContinue
    $result = & curl.exe -s -o $tempOutput -w "%{http_code}" -b $cookieJar -c $cookieJar -X POST -H "Content-Type: application/json" -d "@$loginJson" $Url 2>&1
    $statusCode = 0
    if ($result -match '^\d+$') {
        $statusCode = [int]$result
    }
    $body = ''
    if (Test-Path -LiteralPath $tempOutput) {
        $body = Get-Content -Raw -LiteralPath $tempOutput -ErrorAction SilentlyContinue
        if (-not $body) { $body = '' }
    }
    return @{ HTTPCode = $statusCode; Body = $body }
}

function Show-Response {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [string]$Label = 'Body',
        [int]$TruncateAt = 300
    )
    Write-Host "HTTP $($Response.HTTPCode)"
    if ($Response.Body) {
        $display = $Response.Body.Trim()
        if ($display.Length -gt $TruncateAt) {
            $display = $display.Substring(0, $TruncateAt) + '...'
        }
        Write-Host "${Label}: $display"
    }
}

Write-Section '1. Unauthenticated /auth/me'
$resp = Get-HttpCodeOnly -Url "$baseUrl/auth/me"
Show-Response -Response $resp
if ($resp.HTTPCode -eq 401) { Write-Host 'PASS: Unauthenticated returns 401 as expected' }
else { Write-Host "FAIL: Expected 401, got $($resp.HTTPCode)"; exit 1 }

Write-Section '2. Unauthenticated /admin/attendance-logs'
$resp = Get-HttpCodeOnly -Url "$baseUrl/admin/attendance-logs"
Show-Response -Response $resp
if ($resp.HTTPCode -eq 401) { Write-Host 'PASS: Unauthenticated returns 401 as expected' }
else { Write-Host "FAIL: Expected 401, got $($resp.HTTPCode)"; exit 1 }

Write-Section '3. Login as admin'
$resp = Get-HttpCodePost -Url "$baseUrl/auth/login"
Show-Response -Response $resp -TruncateAt 400
if ($resp.HTTPCode -eq 200) { Write-Host 'PASS: Login successful' }
else { Write-Host "FAIL: Login returned $($resp.HTTPCode)"; exit 1 }

Write-Section '4. Authenticated /auth/me'
$resp = Get-HttpCodeOnly -Url "$baseUrl/auth/me"
Show-Response -Response $resp -TruncateAt 400
if ($resp.HTTPCode -eq 200) { Write-Host 'PASS: Authenticated /auth/me returns 200' }
else { Write-Host "FAIL: Expected 200, got $($resp.HTTPCode)"; exit 1 }

Write-Section '5. Authenticated /admin/attendance-logs'
$resp = Get-HttpCodeOnly -Url "$baseUrl/admin/attendance-logs"
Show-Response -Response $resp -TruncateAt 400
if ($resp.HTTPCode -eq 200) {
    Write-Host 'PASS: Authenticated /admin/attendance-logs returns 200'
    if ($resp.Body -match 'PydanticValidationError|ValidationError') {
        Write-Host 'FAIL: Pydantic ValidationError detected in response body'
        exit 1
    }
}
else {
    Write-Host "FAIL: Expected 200, got $($resp.HTTPCode)"
    if ($resp.HTTPCode -eq 500) { Write-Host 'FAIL: 500 Internal Server Error detected' }
    exit 1
}

Write-Section '6. Authenticated /admin/attendance-sessions?include_deleted=true'
$resp = Get-HttpCodeOnly -Url "$baseUrl/admin/attendance-sessions?include_deleted=true"
Show-Response -Response $resp -TruncateAt 400
if ($resp.HTTPCode -eq 200) {
    Write-Host 'PASS: Authenticated /admin/attendance-sessions returns 200'
    if ($resp.Body -match 'PydanticValidationError|ValidationError') {
        Write-Host 'FAIL: Pydantic ValidationError detected in response body'
        exit 1
    }
}
else {
    Write-Host "FAIL: Expected 200, got $($resp.HTTPCode)"
    if ($resp.HTTPCode -eq 500) { Write-Host 'FAIL: 500 Internal Server Error detected' }
    exit 1
}

Write-Section '7. Authenticated /admin/metrics'
$resp = Get-HttpCodeOnly -Url "$baseUrl/admin/metrics"
Show-Response -Response $resp -TruncateAt 400
if ($resp.HTTPCode -eq 200) { Write-Host 'PASS: Authenticated /admin/metrics returns 200' }
else { Write-Host "FAIL: Expected 200, got $($resp.HTTPCode)"; exit 1 }

Write-Section 'Summary'
Write-Host 'All admin auth validation checks passed.'
Write-Host ''
Write-Host 'Admin credentials used:'
Write-Host '  username: admin'
Write-Host '  password: admin-local-1234'
Write-Host ''
Write-Host 'Endpoints validated:'
Write-Host '  GET  /auth/me                         200 (authenticated), 401 (unauthenticated)'
Write-Host '  GET  /admin/attendance-logs           200 (authenticated), 401 (unauthenticated)'
Write-Host '  GET  /admin/attendance-sessions       200 (authenticated)'
Write-Host '  GET  /admin/metrics                   200 (authenticated)'
Write-Host ''
Write-Host 'No Pydantic ValidationError detected in any response.'
