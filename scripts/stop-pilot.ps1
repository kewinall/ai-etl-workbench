param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
function Invoke-PilotDocker {
    param([string[]]$DockerArguments)
    $result = & wsl.exe -d RockyLinux9 -u root -- docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw 'Pilot Docker operation failed; inspect current state before retrying.' }
    return $result
}
function Assert-NoExternalWorker {
    # A PID file or an expired heartbeat cannot prove a worker has stopped.
    $processes = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'")
    foreach ($process in $processes) {
        if (-not $process.CommandLine) { throw 'Cannot inspect Python process identity; refusing shutdown.' }
        if ($process.CommandLine -match 'app\.(local_sa_worker|pilot_hop_worker|sa_worker|worker)(\s|$)') {
            throw 'Native worker is present; request its graceful stop and verify exit first.'
        }
    }
    $running = @(Invoke-PilotDocker @('ps', '--filter', 'label=com.docker.compose.project=ai-etl-workbench', '--format', '{{.Names}}'))
    foreach ($name in $running) {
        if ($name -and $name -notin $script:allowedNames) {
            throw 'Additional Pilot container is running; inspect its ownership before shutdown.'
        }
    }
}
function Assert-NoPendingWork {
    $sql = @'
SELECT json_build_object(
 'runs',(SELECT count(*) FROM platform.task_run WHERE lease_token IS NOT NULL OR state IN ('QUEUED','RUNNING')),
 'hop',(SELECT count(*) FROM platform.hop_dispatch_request WHERE status IN ('QUEUED','CLAIMED')),
 'ai',(SELECT count(*) FROM platform.agent_invocation WHERE status IN ('SA_QUEUED','DISPATCH_RESERVED','DEVELOPER_RESERVED','QA_RESERVED')),
 'release',(SELECT count(*) FROM platform.release_portability_check WHERE status='RUNNING')
);
'@
    $result = (Invoke-PilotDocker @('exec', 'ai-etl-workbench-postgres-1', 'psql', '-X', '-U', 'workbench', '-d', 'workbench', '-At', '-v', 'ON_ERROR_STOP=1', '-c', $sql)) | ConvertFrom-Json
    foreach ($key in @('runs', 'hop', 'ai', 'release')) {
        if ($null -eq $result.$key -or [long]$result.$key -ne 0) {
            throw "Pending or uncertain work ($key); shutdown not certified. Preserve state and reconcile; do not replay."
        }
    }
}
$script:allowedNames = @('postgres', 'api', 'web', 'control-worker') | ForEach-Object { 'ai-etl-workbench-' + $_ + '-1' }
foreach ($service in @('postgres', 'api', 'web', 'control-worker')) {
    $name = 'ai-etl-workbench-' + $service + '-1'
    $labels = (Invoke-PilotDocker @('inspect', '--format', '{{json .Config.Labels}}', $name)) | ConvertFrom-Json
    if ($labels.'com.docker.compose.project' -ne 'ai-etl-workbench' -or $labels.'com.docker.compose.service' -ne $service) {
        throw "Container identity mismatch: $name"
    }
    $state = (Invoke-PilotDocker @('inspect', '--format', '{{.State.Status}}', $name)).Trim()
    if (($service -eq 'postgres' -and $state -ne 'running') -or $state -notin @('running', 'exited', 'created')) {
        throw "Container requires manual review: $name ($state)"
    }
}
Assert-NoExternalWorker
Assert-NoPendingWork
if ($CheckOnly) { Write-Output 'Preflight passed at this instant; no admission lock and no services stopped.'; return }
# Never use Docker's default timeout: after it expires Docker sends SIGKILL.
# An infinite graceful wait preserves in-flight work; this command may remain
# running until that work finishes. Do not replace a long wait with force kill.
foreach ($service in @('control-worker', 'web', 'api')) {
    $name = 'ai-etl-workbench-' + $service + '-1'
    Invoke-PilotDocker @('stop', '--timeout', '-1', $name) | Out-Null
    $state = (Invoke-PilotDocker @('inspect', '--format', '{{.State.Status}}', $name)).Trim()
    if ($state -notin @('exited', 'created')) { throw "Container did not stop: $name" }
}
# New work accepted between preflight and graceful shutdown is not discarded.
# If found here, retain stopped services and report an incomplete drain.
Assert-NoExternalWorker
Assert-NoPendingWork
Write-Output 'Pilot API/web/control-worker stopped gracefully. PostgreSQL and all volumes remain intact. No files deleted or work replayed. Model/Hop workers were required to be absent. No persistent admission fence is installed.'
