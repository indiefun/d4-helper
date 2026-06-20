Set-Location -LiteralPath $PSScriptRoot
$version = (Get-Content -LiteralPath .\VERSION -Raw).Trim()
python -m PyInstaller --noconfirm --clean --onefile --windowed --name D4Helper .\right_hold_toggle.py
Copy-Item -LiteralPath .\config.json -Destination .\dist\config.json -Force
Set-Content -LiteralPath .\dist\VERSION -Value $version -Encoding UTF8
