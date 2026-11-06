param([string]$Go = 'go')
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location -LiteralPath $repositoryRoot
try {
    & '.\go-desktop\build.ps1' -Go $Go
    $version = (Get-Content -LiteralPath '.\VERSION' -Raw).Trim()
    $destination = Join-Path $repositoryRoot 'dist\go'
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -LiteralPath '.\go-desktop\build\D4Helper.exe' -Destination $destination -Force
    $configPath = Join-Path $destination 'workspace.timeline.json'
    if (-not (Test-Path -LiteralPath $configPath)) { Copy-Item -LiteralPath '.\go-desktop\build\default-workspace.timeline.json' -Destination $configPath }
    Set-Content -LiteralPath (Join-Path $destination 'VERSION') -Value $version -Encoding UTF8
    # Keep one archive alongside the executable, with defaults rather than local macros.
    # Write directly into the zip, so packaging needs no staging or versioned folders.
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = Join-Path $destination 'D4Helper-Studio.zip'
    $archiveStream = [IO.File]::Open($archive, [IO.FileMode]::Create)
    try {
        $zip = [IO.Compression.ZipArchive]::new($archiveStream, [IO.Compression.ZipArchiveMode]::Create, $true)
        try {
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $destination 'D4Helper.exe'), 'D4Helper.exe', [IO.Compression.CompressionLevel]::Optimal) | Out-Null
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $repositoryRoot 'go-desktop\build\default-workspace.timeline.json'), 'workspace.timeline.json', [IO.Compression.CompressionLevel]::Optimal) | Out-Null
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $destination 'VERSION'), 'VERSION', [IO.Compression.CompressionLevel]::Optimal) | Out-Null
        } finally { $zip.Dispose() }
    } finally { $archiveStream.Dispose() }
    Write-Host "Built Go release: $archive"
} finally { Pop-Location }
