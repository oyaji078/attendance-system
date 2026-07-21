[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Username,
    [string]$Password
)

. "$PSScriptRoot\_dev-common.ps1"
Import-ProjectEnv
$python = Resolve-ProjectPython

$scriptArgs = @("$PSScriptRoot\reset_admin_password.py", '--username', $Username)
if ($Password) {
    $scriptArgs += @('--password', $Password)
}

& $python @scriptArgs
exit $LASTEXITCODE
