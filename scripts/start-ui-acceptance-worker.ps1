$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$project=(Get-Content -LiteralPath (Join-Path $taskRoot 'runtime-temp/ui-accept-project-id.txt')).Trim()
[void][guid]::Parse($project)
$pidFile=Join-Path $taskRoot 'runtime-temp/ui-accept-worker.pid'
if(Test-Path -LiteralPath $pidFile){
  $savedId=0
  if([int]::TryParse((Get-Content -LiteralPath $pidFile).Trim(),[ref]$savedId)){
    $existing=Get-CimInstance Win32_Process -Filter "ProcessId=$savedId" -ErrorAction SilentlyContinue
    if($existing -and $existing.CommandLine -like '*app.local_acceptance_worker*' -and $existing.CommandLine -like "*$project*"){
      Write-Output "5197 acceptance Worker already running: $savedId"
      exit 0
    }
  }
}
$stopFile=Join-Path $taskRoot 'runtime-temp/ui-accept-worker.stop'
if(Test-Path -LiteralPath $stopFile){Remove-Item -LiteralPath $stopFile}
$env:PYTHONPATH=Join-Path $taskRoot 'backend'
$process=Start-Process -FilePath (Join-Path $taskRoot '.venv/Scripts/python.exe') -ArgumentList @('-m','app.local_acceptance_worker','--project-id',$project) -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot 'runtime-temp/ui-accept-worker.log') -RedirectStandardError (Join-Path $taskRoot 'runtime-temp/ui-accept-worker.err')
$process.Id | Set-Content -LiteralPath (Join-Path $taskRoot 'runtime-temp/ui-accept-worker.pid')
Write-Output "5197 acceptance Worker started: $($process.Id); only approved intents in Project $project"
