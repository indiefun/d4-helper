param([switch]$DryRun, [string]$Go = 'go')
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $binary = Join-Path $PSScriptRoot 'go-desktop\build\D4Helper.exe'
    if (-not (Test-Path -LiteralPath $binary)) { & '.\go-desktop\build.ps1' -Go $Go }
    if ($DryRun) { & $binary -dry-run } else { & $binary }
} finally { Pop-Location }
