$Root=Split-Path -Parent $PSScriptRoot; $file="$Root\runtime-temp\processes.json"
if(Test-Path $file){$p=Get-Content $file|ConvertFrom-Json; $ids=@($p.api,$p.worker,$p.frontend); Get-CimInstance Win32_Process|Where-Object{$ids -contains $_.ParentProcessId}|ForEach-Object{Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}; $ids|ForEach-Object{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}; Remove-Item $file -Force}
$escapedRoot=[regex]::Escape($Root)
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and (
    $_.CommandLine -match "$escapedRoot\\frontend" -or
    $_.CommandLine -match "$escapedRoot\\\.venv\\Scripts\\python\.exe.+-m (uvicorn app\.main:app|app\.worker)"
  )
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-ChildItem "$Root\runtime-temp" -Force -ErrorAction SilentlyContinue|Where-Object{$_.Name -ne 'task-uploads'}|Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'POC services stopped; runtime-temp cleaned.'
