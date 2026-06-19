Set-Location -LiteralPath $PSScriptRoot
python -m PyInstaller --noconfirm --clean --onefile --windowed --name GameMouseTool .\right_hold_toggle.py
Copy-Item -LiteralPath .\config.json -Destination .\dist\config.json -Force
