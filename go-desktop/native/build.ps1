$ErrorActionPreference = 'Stop'
$prototypeRoot = Split-Path -Parent $PSScriptRoot
$outputDirectory = Join-Path $prototypeRoot 'build'
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$vsDevCmd = Get-ChildItem 'C:\Program Files\Microsoft Visual Studio' -Filter VsDevCmd.bat -File -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\Common7\\Tools\\VsDevCmd\.bat$' } | Select-Object -First 1
if (-not $vsDevCmd) { throw 'Visual Studio C++ desktop workload is required.' }
$sourcePath = Join-Path $PSScriptRoot 'timingbench.cpp'
$binaryPath = Join-Path $outputDirectory 'native-timingbench.exe'
$objectPath = Join-Path $outputDirectory 'native-timingbench.obj'
$compile = '"{0}" -arch=x64 && cl /nologo /O2 /EHsc /std:c++17 /Fo"{1}" "{2}" /link /OUT:"{3}"' -f $vsDevCmd.FullName, $objectPath, $sourcePath, $binaryPath
& cmd.exe /d /s /c $compile
if ($LASTEXITCODE -ne 0) { throw 'Native timing benchmark build failed.' }
