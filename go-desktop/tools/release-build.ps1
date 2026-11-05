param([string]$Go = 'go')
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location -LiteralPath $repositoryRoot
try {
    & '.\go-desktop\build.ps1' -Go $Go
    $version = (Get-Content -LiteralPath '.\VERSION' -Raw).Trim()
    $destination = Join-Path $repositoryRoot 'dist\studio'
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -LiteralPath '.\go-desktop\build\D4Helper.exe' -Destination $destination -Force
    $configPath = Join-Path $destination 'workspace.timeline.json'
    if (-not (Test-Path -LiteralPath $configPath)) { Copy-Item -LiteralPath '.\go-desktop\build\default-workspace.timeline.json' -Destination $configPath }
    Set-Content -LiteralPath (Join-Path $destination 'VERSION') -Value $version -Encoding UTF8
    $portable = Join-Path $repositoryRoot "dist\D4Helper-Studio-v$version"
    New-Item -ItemType Directory -Path $portable -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $destination 'D4Helper.exe') -Destination $portable -Force
    Copy-Item -LiteralPath (Join-Path $destination 'VERSION') -Destination $portable -Force
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'workspace.timeline.json'))) { Copy-Item -LiteralPath $configPath -Destination $portable }
    # Archives use checked-in defaults, never local saved configurations.
    $releaseStage = Join-Path $repositoryRoot 'dist\studio-release-stage'
    New-Item -ItemType Directory -Path $releaseStage -Force | Out-Null
    Copy-Item -LiteralPath '.\go-desktop\build\D4Helper.exe' -Destination $releaseStage -Force
    Copy-Item -LiteralPath '.\go-desktop\build\default-workspace.timeline.json' -Destination (Join-Path $releaseStage 'workspace.timeline.json') -Force
    Copy-Item -LiteralPath (Join-Path $destination 'VERSION') -Destination $releaseStage -Force
    $archive = Join-Path $repositoryRoot "dist\D4Helper-Studio-v$version.zip"
    Compress-Archive -LiteralPath @((Join-Path $releaseStage 'D4Helper.exe'),(Join-Path $releaseStage 'workspace.timeline.json'),(Join-Path $releaseStage 'VERSION')) -DestinationPath $archive -CompressionLevel Optimal -Force
    Write-Host "Built Go release: $archive"
} finally { Pop-Location }
