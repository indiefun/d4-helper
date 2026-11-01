$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$nativeBuild = Join-Path $PSScriptRoot "native\build.ps1"
& $nativeBuild
if ($LASTEXITCODE -ne 0) {
    throw "Native kernel build failed with exit code $LASTEXITCODE"
}
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
python -m PyInstaller --noconfirm --clean --onefile --windowed --name D4Helper --icon ".\assets\app-icon.ico" --add-binary ".\native\fast_input_kernel.dll;." --add-data ".\assets\donate.jpg;assets" --add-data ".\assets\app-icon.png;assets" --add-data ".\VERSION;." .\right_hold_toggle.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}
$distConfigPath = Join-Path $PSScriptRoot "dist\config.json"
if (-not (Test-Path -LiteralPath $distConfigPath)) {
    Copy-Item -LiteralPath .\config.json -Destination $distConfigPath
} else {
    Write-Host "Preserving existing dist config: $distConfigPath"
}
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'dist\VERSION'), "$version`n", [System.Text.UTF8Encoding]::new($false))
$portableArchive = Join-Path $PSScriptRoot "dist\D4Helper-portable-v$version.zip"
Compress-Archive -LiteralPath .\dist\D4Helper.exe, $distConfigPath, .\dist\VERSION -DestinationPath $portableArchive -CompressionLevel Optimal -Force
Copy-Item -LiteralPath $portableArchive -Destination .\dist\D4Helper-windows-latest.zip -Force
