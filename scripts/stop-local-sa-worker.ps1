$ErrorActionPreference = 'Stop'
$workerRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workerRuntime = [IO.Path]::GetFullPath((Join-Path $workerRoot 'runtime-temp\local-sa-worker'))
$workerStateFile = Join-Path $workerRuntime 'service.json'
if (-not (Test-Path -LiteralPath $workerStateFile)) { Write-Output 'No managed worker state'; exit 0 }
$workerState = Get-Content -LiteralPath $workerStateFile -Raw | ConvertFrom-Json
$workerStop = [IO.Path]::GetFullPath([string]$workerState.stop_file)
if ([IO.Path]::GetDirectoryName($workerStop) -ne $workerRuntime -or [IO.Path]::GetFileName($workerStop) -notmatch '^[a-f0-9-]{36}\.stop$') { throw 'Worker stop path is outside the expected runtime directory' }
$workerPid = [int]$workerState.process_id
$workerProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$workerPid"
if (-not $workerProcess) { Write-Output 'Worker process is not running'; exit 0 }
$workerPython = Join-Path $workerRoot '.venv\Scripts\python.exe'
if (-not $workerProcess.CommandLine -or -not $workerProcess.CommandLine.Contains($workerPython) -or -not $workerProcess.CommandLine.Contains('app.local_sa_worker') -or -not $workerProcess.CommandLine.Contains($workerStop)) { throw 'Process identity does not match; refusing stop request' }
New-Item -ItemType File -Force -Path $workerStop | Out-Null
Write-Output 'Stop requested. An in-flight call may finish; no process is forcibly killed.'
for ($attempt=0; $attempt -lt 30; $attempt++) {
    if (-not (Get-Process -Id $workerPid -ErrorAction SilentlyContinue)) { Write-Output 'Worker stopped'; exit 0 }
    Start-Sleep -Seconds 1
}
Write-Output 'Worker is still finishing. Check its actual process and /api/runtime/workers before restarting.'
