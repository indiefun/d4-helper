param([string]$Binary = '', [string]$Config = '')
$ErrorActionPreference = 'Stop'
$prototypeRoot = Split-Path -Parent $PSScriptRoot
if (-not $Binary) { $Binary = Join-Path $prototypeRoot 'build\D4Helper.exe' }
$report = Join-Path $prototypeRoot ('build\smoke-' + [guid]::NewGuid().ToString('N') + '.json')
$arguments=@('-self-test',('"' + $report + '"'))
if($Config){$arguments=@('-config',('"' + $Config + '"'))+$arguments}
$process = Start-Process -FilePath $Binary -ArgumentList $arguments -WorkingDirectory $prototypeRoot -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(30000)) { Stop-Process -Id $process.Id; throw 'Desktop smoke test did not exit within 30 seconds.' }
if (-not (Test-Path -LiteralPath $report)) { throw 'Desktop did not produce a renderer report; check for another running D4Helper instance.' }
$result = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
if ($result.error -or -not $result.dry_run -or $result.frontend_macros -ne $result.backend_macros -or -not $result.engine.armed -or $result.engine.pending_releases -ne 0) { throw "Desktop smoke test failed: $(ConvertTo-Json $result -Depth 6)" }
Write-Output "Desktop renderer/Go bridge smoke test passed ($($result.frontend_macros) macros): $report"
