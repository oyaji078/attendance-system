. "$PSScriptRoot\_dev-common.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Test-DockerReady

& docker exec -it docker-redis-1 redis-cli

