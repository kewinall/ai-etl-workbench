param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
# Resume an installed Pilot, never provision or silently change execution flags.
function Invoke-PilotDocker {
    param([string[]]$DockerArguments)
    $result = & wsl.exe -d RockyLinux9 -u root -- docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw 'Pilot Docker operation failed; no automatic retry.' }
    return $result
}
$services = @('postgres', 'api', 'web')
$containers = @()
# Validate all identities before starting any service. Same-project test containers
# must never be selected by a broad label filter.
foreach ($service in $services) {
    $name = 'ai-etl-workbench-' + $service + '-1'
    $format = '{{json .Config.Labels}}'
    $labels = (Invoke-PilotDocker @('inspect', '--format', $format, $name)) | ConvertFrom-Json
    if ($labels.'com.docker.compose.project' -ne 'ai-etl-workbench' -or
        $labels.'com.docker.compose.service' -ne $service) {
        throw "Container identity mismatch: $name"
    }
    $state = (Invoke-PilotDocker @('inspect', '--format', '{{.State.Status}}', $name)).Trim()
    if ($state -notin @('running', 'exited', 'created')) {
        throw "Container requires manual review: $name ($state)"
    }
    $containers += @{Name=$name; State=$state}
}
if ($CheckOnly) {
    $containers | ForEach-Object { Write-Output ($_.Name + ': ' + $_.State) }
    return
}
foreach ($container in $containers) {
    if ($container.State -ne 'running') {
        Invoke-PilotDocker @('start', $container.Name) | Out-Null
    }
}
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $response = Invoke-RestMethod -Uri 'http://127.0.0.1:5183/api/ready' -TimeoutSec 3
        if ($response.status -eq 'ready') { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    throw 'Pilot started but readiness failed. Inspect services; no rebuild, rollback or ETL retry was performed.'
}
Write-Output 'Pilot ready: http://127.0.0.1:5183. Only existing postgres/api/web were resumed. Workers and dispatch settings were not changed. This does not keep WSL alive or configure Windows startup.'
