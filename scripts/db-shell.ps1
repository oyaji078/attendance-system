. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-ProjectEnv
Test-DockerReady

& docker exec -it docker-postgres-1 psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB

