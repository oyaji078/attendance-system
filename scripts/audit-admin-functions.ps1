param(
  [string] $ApiBaseUrl = "http://localhost:8000",
  [string] $UiBaseUrl = "http://localhost:8080",
  [string] $Username = $env:ATTENDANCE_ADMIN_USERNAME,
  [string] $Password = $env:ATTENDANCE_ADMIN_PASSWORD,
  [switch] $WriteTestData
)

$ErrorActionPreference = "Stop"

function Add-Result {
  param([string] $Name, [string] $Status, [string] $Detail = "")
  [pscustomobject]@{ Name = $Name; Status = $Status; Detail = $Detail }
}

function Invoke-Json {
  param(
    [string] $Method = "GET",
    [string] $Path,
    [object] $Body = $null,
    [Microsoft.PowerShell.Commands.WebRequestSession] $Session = $null,
    [int[]] $OkStatus = @(200, 201, 204)
  )
  $params = @{
    Method = $Method
    Uri = "$ApiBaseUrl$Path"
  }
  if ($Session) { $params.WebSession = $Session }
  if ($null -ne $Body) {
    $params.ContentType = "application/json"
    $params.Body = ($Body | ConvertTo-Json -Depth 8)
  }
  try {
    $response = Invoke-WebRequest @params
  } catch {
    if ($_.Exception.Response) {
      $response = $_.Exception.Response
      $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
      $content = $reader.ReadToEnd()
      $response = [pscustomobject]@{ StatusCode = [int]$response.StatusCode; Content = $content }
    } else {
      throw
    }
  }
  $statusCode = [int]$response.StatusCode
  if ($OkStatus -notcontains $statusCode) {
    throw "HTTP $statusCode $Method $Path $($response.Content)"
  }
  if ([string]::IsNullOrWhiteSpace($response.Content)) { return $null }
  return $response.Content | ConvertFrom-Json
}

$results = New-Object System.Collections.Generic.List[object]
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

try {
  $healthResponse = Invoke-WebRequest -Uri "$ApiBaseUrl/health" -UseBasicParsing
  $results.Add((Add-Result "API health" "PASS" "HTTP $($healthResponse.StatusCode) $($healthResponse.Content)"))
} catch {
  $results.Add((Add-Result "API health" "FAIL" $_.Exception.Message))
}

try {
  Invoke-Json -Path "/admin/persons" -OkStatus @(401, 403) | Out-Null
  $results.Add((Add-Result "Protected admin rejects unauthenticated" "PASS"))
} catch {
  $results.Add((Add-Result "Protected admin rejects unauthenticated" "FAIL" $_.Exception.Message))
}

$authenticated = $false
if ($Username -and $Password) {
  try {
    Invoke-Json -Method "POST" -Path "/auth/login" -Body @{ username = $Username; password = $Password } -Session $session | Out-Null
    Invoke-Json -Path "/auth/me" -Session $session | Out-Null
    $authenticated = $true
    $results.Add((Add-Result "Auth login" "PASS" "Authenticated as $Username"))
  } catch {
    $results.Add((Add-Result "Auth login" "FAIL" $_.Exception.Message))
  }
} else {
  $results.Add((Add-Result "Auth login" "SKIP" "Set ATTENDANCE_ADMIN_USERNAME and ATTENDANCE_ADMIN_PASSWORD, or pass -Username/-Password."))
}

if ($authenticated) {
  foreach ($check in @(
    @{ Name = "Students list"; Path = "/admin/persons" },
    @{ Name = "Lecturers list"; Path = "/admin/lecturers" },
    @{ Name = "Classes list"; Path = "/admin/classes" },
    @{ Name = "Sessions list"; Path = "/admin/attendance-sessions" },
    @{ Name = "Attendance logs list"; Path = "/admin/attendance-logs" },
    @{ Name = "Device configs list"; Path = "/admin/devices/configs" }
  )) {
    try {
      $payload = Invoke-Json -Path $check.Path -Session $session
      $count = if ($payload.items) { $payload.items.Count } elseif ($payload.Count) { $payload.Count } else { 0 }
      $results.Add((Add-Result $check.Name "PASS" "items=$count"))
    } catch {
      $results.Add((Add-Result $check.Name "FAIL" $_.Exception.Message))
    }
  }

  if ($WriteTestData) {
    $stamp = Get-Date -Format "yyyyMMddHHmmss"
    $studentId = "TEST-AUDIT-$stamp"
    try {
      $student = Invoke-Json -Method "POST" -Path "/admin/persons" -Session $session -Body @{
        student_id = $studentId
        full_name = "TEST Audit Student"
        email = "test.audit.$stamp@example.invalid"
        class_id = $null
        is_active = $false
      }
      $results.Add((Add-Result "Student create TEST" "PASS" $student.person_id))

      $deactivated = Invoke-Json -Method "PATCH" -Path "/admin/persons/$($student.person_id)/deactivate" -Session $session
      $results.Add((Add-Result "Student deactivate" ($(if (-not $deactivated.is_active) { "PASS" } else { "FAIL" })) "is_active=$($deactivated.is_active)"))

      $reactivated = Invoke-Json -Method "PATCH" -Path "/admin/persons/$($student.person_id)/reactivate" -Session $session
      $results.Add((Add-Result "Student reactivate" ($(if ($reactivated.is_active) { "PASS" } else { "FAIL" })) "is_active=$($reactivated.is_active)"))

      $faceRevoke = Invoke-Json -Method "DELETE" -Path "/admin/persons/$($student.person_id)/face-data" -Session $session
      $results.Add((Add-Result "Enrollment face revoke" "PASS" $faceRevoke.detail))

      $deleted = Invoke-Json -Method "DELETE" -Path "/admin/persons/$($student.person_id)" -Session $session
      $listAfterDelete = Invoke-Json -Path "/admin/persons" -Session $session
      $stillVisible = @($listAfterDelete.items | Where-Object { $_.student_id -eq $studentId }).Count -gt 0
      $results.Add((Add-Result "Student soft-delete hidden from active list" ($(if (-not $stillVisible) { "PASS" } else { "FAIL" })) $deleted.detail))
    } catch {
      $results.Add((Add-Result "Writable student CRUD audit" "FAIL" $_.Exception.Message))
    }
  } else {
    $results.Add((Add-Result "Writable CRUD audit" "SKIP" "Pass -WriteTestData to create and clean only TEST-AUDIT records via soft delete."))
  }
}

try {
  $ui = ""
  foreach ($path in @("apps/kiosk-ui/src/index.html", "apps/kiosk-ui/src/main.js", "apps/kiosk-ui/src/styles.css")) {
    if (Test-Path $path) { $ui += "`n" + (Get-Content $path -Raw) }
  }
  $requiredUiTokens = @("Pilih kamera", "Gunakan kamera ini", "status-dot", "Mulai Pendaftaran Wajah", "Tambah mahasiswa baru dilakukan melalui menu Enrollment")
  $missing = @($requiredUiTokens | Where-Object { $ui -notmatch [regex]::Escape($_) })
  if ($missing.Count -eq 0) {
    $results.Add((Add-Result "Camera/enrollment UI tokens" "PASS"))
  } else {
    $results.Add((Add-Result "Camera/enrollment UI tokens" "WARN" "Missing source token(s): $($missing -join ', ')"))
  }
} catch {
  $results.Add((Add-Result "Camera/enrollment UI tokens" "WARN" $_.Exception.Message))
}

$results | Format-Table -AutoSize
if (($results | Where-Object Status -eq "FAIL").Count -gt 0) {
  exit 1
}
