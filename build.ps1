param([string]$Go = 'go')
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'go-desktop\tools\release-build.ps1') -Go $Go
