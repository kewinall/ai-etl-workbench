param([switch]$EnableModelDispatch)
$ErrorActionPreference = 'Stop'
$workerRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workerPython = Join-Path $workerRoot '.venv\Scripts\python.exe'
$workerRuntime = Join-Path $workerRoot 'runtime-temp\local-sa-worker'
if (-not (Test-Path -LiteralPath $workerPython)) { throw 'Workspace Python environment is missing' }
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains($workerPython) -and
    $_.CommandLine.Contains('app.local_sa_worker') -and $_.CommandLine.Contains('--serve')
}
if ($running) { throw 'A workspace local SA worker is already running. Stop it before changing mode.' }
New-Item -ItemType Directory -Force -Path $workerRuntime | Out-Null
$workerId = [guid]::NewGuid().ToString()
$workerStop = Join-Path $workerRuntime ($workerId+'.stop')
$workerOut = Join-Path $workerRuntime ($workerId+'.stdout.log')
$workerErr = Join-Path $workerRuntime ($workerId+'.stderr.log')
$workerArguments = @('-u','-m','app.local_sa_worker','--serve','--stop-file',('"'+$workerStop+'"'))
if ($EnableModelDispatch) { $workerArguments += '--allow-model-dispatch' }
$workerProcess = Start-Process -FilePath $workerPython -ArgumentList $workerArguments -WorkingDirectory (Join-Path $workerRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput $workerOut -RedirectStandardError $workerErr -PassThru
$workerState = @{process_id=$workerProcess.Id; stop_file=$workerStop; stdout_log=$workerOut; stderr_log=$workerErr; mode=$(if ($EnableModelDispatch) {'EXECUTE'} else {'OBSERVE'})}
$workerState | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workerRuntime 'service.json') -Encoding UTF8
Write-Output ('Started PID '+$workerProcess.Id+' in '+$workerState.mode+' mode. Verify /api/runtime/workers; process start is not readiness.')
