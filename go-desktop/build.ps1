param([string]$Go = 'go')
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    New-Item -ItemType Directory -Path '.\build' -Force | Out-Null
    $buildBinary = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'build\D4Helper.exe'))
    $runningBuilds = @(Get-Process -Name D4Helper -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $buildBinary })
    foreach ($runningBuild in $runningBuilds) {
        Write-Host "Closing running build before replacement: $buildBinary (PID $($runningBuild.Id))"
        Stop-Process -Id $runningBuild.Id -Force -ErrorAction Stop
        if (-not $runningBuild.WaitForExit(5000)) { throw "Could not close running build: $buildBinary" }
    }
    $version = (Get-Content -LiteralPath '..\VERSION' -Raw).Trim()
    & $Go run github.com/akavel/rsrc@v0.10.2 -arch amd64 -manifest '.\resources\app.manifest' -ico '..\assets\app-icon.ico' -o '.\rsrc_windows_amd64.syso'
    if ($LASTEXITCODE -ne 0) { throw 'Windows resources build failed.' }
    & $Go build -trimpath -o '.\build\timingbench.exe' '.\cmd\timingbench'
    if ($LASTEXITCODE -ne 0) { throw 'Timing benchmark build failed.' }
    & $Go build -trimpath -tags 'desktop,production' -ldflags "-H windowsgui -s -w -X main.appVersion=$version" -o '.\build\D4Helper.exe' .
    if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    & $Go run '.\tools\default-workspace.go' '.\build\default-workspace.timeline.json'
    if ($LASTEXITCODE -ne 0) { throw 'Default timeline workspace generation failed.' }
} finally { Pop-Location }
