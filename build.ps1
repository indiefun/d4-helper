$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$nativeBuild = Join-Path $PSScriptRoot "native\build.ps1"
& $nativeBuild
if ($LASTEXITCODE -ne 0) {
    throw "Native kernel build failed with exit code $LASTEXITCODE"
}
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
python -m PyInstaller --noconfirm --clean --onefile --windowed --name D4Helper --icon ".\assets\app-icon.ico" --add-binary ".\native\fast_input_kernel.dll;." --add-data ".\assets\donate.jpg;assets" --add-data ".\assets\app-icon.png;assets" --add-data ".\assets\worm-routes;assets\worm-routes" --add-data ".\VERSION;." .\right_hold_toggle.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}
Copy-Item -LiteralPath .\config.json -Destination .\dist\config.json -Force
Set-Content -LiteralPath .\dist\VERSION -Value $version -Encoding UTF8
$portableDirectory = Join-Path $PSScriptRoot "dist\D4Helper-portable-v$version"
New-Item -ItemType Directory -Path $portableDirectory -Force | Out-Null
Copy-Item -LiteralPath .\dist\D4Helper.exe -Destination $portableDirectory -Force
Copy-Item -LiteralPath .\dist\config.json -Destination $portableDirectory -Force
Copy-Item -LiteralPath .\dist\VERSION -Destination $portableDirectory -Force
$portableArchive = Join-Path $PSScriptRoot "dist\D4Helper-portable-v$version.zip"
Compress-Archive -Path (Join-Path $portableDirectory "*") -DestinationPath $portableArchive -CompressionLevel Optimal -Force
