param([ValidateSet('Start','Stop','Status')][string]$Action='Status')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $root 'backend\app\wsl_holder.py'
$linuxSource = & wsl.exe -d RockyLinux9 -u root --exec wslpath -a $source
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate WSL holder source' }
function Invoke-Holder([string[]]$HolderArguments) {
    $raw = & wsl.exe -d RockyLinux9 -u root --exec python3 $linuxSource @HolderArguments
    if ($LASTEXITCODE -ne 0) { throw 'Holder operation failed; inspect owner state. No process was force-killed.' }
    return ($raw | ConvertFrom-Json)
}
$state = Invoke-Holder @('status')
if ($Action -eq 'Status') { $state | ConvertTo-Json; return }
if ($Action -eq 'Stop') {
    # Stop application services safely before releasing our WSL liveness owner.
    & (Join-Path $PSScriptRoot 'stop-pilot.ps1')
    if ($state.status -eq 'RUNNING') {
        Invoke-Holder @('stop','--token',$state.token) | Out-Null
        for ($attempt=0; $attempt -lt 10; $attempt++) {
            $observed = Invoke-Holder @('status')
            if ($observed.status -eq 'STOPPED' -and $observed.token -eq $state.token) {
                Write-Output 'Pilot services stopped and this holder exited. Shared Docker/WSL was not shut down.'; return
            }
            Start-Sleep -Milliseconds 200
        }
        throw 'Holder exit not verified; no forced termination was performed'
    }
    Write-Output 'Pilot services stopped; no running verified holder was released.'
    return
}
if ($state.status -notin @('RUNNING','NOT_STARTED','STOPPED','LOST')) { throw 'Holder startup is already in progress; inspect it before retrying' }
if ($state.status -ne 'RUNNING') {
    $token = [guid]::NewGuid().ToString()
    $logs = Join-Path $root 'runtime-temp\wsl-holder'
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    $arguments = @('-d','RockyLinux9','-u','root','--exec','python3',('"'+$linuxSource+'"'),'serve','--token',$token)
    Start-Process -FilePath 'wsl.exe' -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs ($token+'.out.log')) -RedirectStandardError (Join-Path $logs ($token+'.err.log')) | Out-Null
    $verified=$false
    for ($attempt=0; $attempt -lt 10; $attempt++) {
        $observed = Invoke-Holder @('status')
        if ($observed.status -eq 'RUNNING' -and $observed.token -eq $token) { $verified=$true; break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $verified) { throw 'Holder startup not verified. Inspect session logs; no automatic second launch.' }
}
& (Join-Path $PSScriptRoot 'start-pilot.ps1') -IncludeControlWorker
Write-Output 'Manual WSL holder is verified; existing control-worker is resumed. No model/Hop worker was started and no Windows login startup was configured.'
