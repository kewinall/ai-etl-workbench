param([switch]$NoBrowser)
$ErrorActionPreference='Stop'; $Root=Split-Path -Parent $PSScriptRoot
$Utf8NoBom=New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding=$Utf8NoBom; [Console]::OutputEncoding=$Utf8NoBom
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; $env:PGCLIENTENCODING='UTF8'
$Runtime='C:\Users\kewin\.cache\codex-runtimes\codex-primary-runtime\dependencies'; $Pnpm="$Runtime\bin\fallback\pnpm.cmd"
$env:PATH="$Runtime\node\bin;$env:PATH"
& "$Root\.venv\Scripts\python.exe" "$Root\backend\app\demo_fixtures.py"
$api=Start-Process "$Root\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8765' -WorkingDirectory "$Root\backend" -WindowStyle Hidden -PassThru
$worker=Start-Process "$Root\.venv\Scripts\python.exe" -ArgumentList '-m','app.worker' -WorkingDirectory "$Root\backend" -WindowStyle Hidden -PassThru
$ui=Start-Process $Pnpm -ArgumentList 'dev','--','--host','127.0.0.1','--port','5173' -WorkingDirectory "$Root\frontend" -WindowStyle Hidden -PassThru
@{api=$api.Id;worker=$worker.Id;frontend=$ui.Id}|ConvertTo-Json|Set-Content "$Root\runtime-temp\processes.json"
Start-Sleep -Seconds 3
Write-Host 'UI: http://127.0.0.1:5173   API: http://127.0.0.1:8765/docs' -ForegroundColor Cyan
if(!$NoBrowser){Start-Process 'http://127.0.0.1:5173'}
