$ErrorActionPreference = "Stop"

$vsDevCmd = Get-ChildItem "C:\Program Files\Microsoft Visual Studio" -Filter VsDevCmd.bat -File -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\Common7\\Tools\\VsDevCmd\.bat$" } |
    Select-Object -First 1
if (-not $vsDevCmd) {
    throw "Visual Studio VsDevCmd.bat was not found. Install the C++ desktop workload."
}

$sourcePath = Join-Path $PSScriptRoot "fast_input_kernel.cpp"
$binaryPath = Join-Path $PSScriptRoot "fast_input_kernel.dll"
$compile = '"{0}" -arch=x64 && cl /nologo /LD /O2 /EHsc /std:c++17 "{1}" /link /OUT:"{2}"' -f $vsDevCmd.FullName, $sourcePath, $binaryPath
cmd.exe /d /s /c $compile
if ($LASTEXITCODE -ne 0) {
    throw "Native kernel build failed with exit code $LASTEXITCODE"
}
