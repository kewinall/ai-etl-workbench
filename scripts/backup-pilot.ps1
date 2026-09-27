param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
function Invoke-BackupDocker {
    param([string[]]$DockerArguments)
    $result = & wsl.exe -d RockyLinux9 -u root -- docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw 'Backup Docker operation failed. Retain partial files and inspect service state.' }
    return $result
}
function Convert-ToWslPath([string]$WindowsPath) {
    $result = & wsl.exe -d RockyLinux9 -u root --exec wslpath -a $WindowsPath
    if ($LASTEXITCODE -ne 0 -or -not $result) { throw 'Cannot resolve backup path in WSL' }
    return ([string]$result).Trim()
}
function Assert-BackupWritersStopped {
    foreach ($service in @('api', 'web', 'control-worker')) {
        $state = (Invoke-BackupDocker @('inspect', '--format', '{{.State.Status}}', "ai-etl-workbench-$service-1")).Trim()
        if ($state -ne 'exited') { throw 'Application writer restarted during backup' }
    }
    $ids = @(Invoke-BackupDocker @('ps', '-q'))
    foreach ($id in $ids) {
        if (-not $id) { continue }
        $mounts = (Invoke-BackupDocker @('inspect', '--format', '{{json .Mounts}}', $id)) | ConvertFrom-Json
        foreach ($mount in $mounts) {
            if ($mount.RW -and $mount.Name -in $script:sourceVolumes.Values) {
                throw 'A running container has writable access to backup source files'
            }
        }
    }
    # Do not infer quiescence from a task status while an external DB client remains.
    $sessions = Invoke-BackupDocker @('exec','ai-etl-workbench-postgres-1','psql','-X','-U','workbench','-d','workbench','-At','-v','ON_ERROR_STOP=1','-c',
        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend';")
    if ([string]$sessions -notmatch '^0$') { throw 'External database client remains; backup cannot certify application quiescence' }
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'stop-pilot.ps1') -CheckOnly
foreach ($service in @('api', 'web', 'control-worker')) {
    $state = (Invoke-BackupDocker @('inspect', '--format', '{{.State.Status}}', "ai-etl-workbench-$service-1")).Trim()
    if ($state -ne 'running') { throw 'Backup requires a running installation so its original service state is unambiguous' }
}
$image = (Invoke-BackupDocker @('inspect','--format','{{.Image}}','ai-etl-workbench-api-1')).Trim()
if ($image -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Cannot pin backup runtime image' }
$mounts = (Invoke-BackupDocker @('inspect','--format','{{json .Mounts}}','ai-etl-workbench-api-1')) | ConvertFrom-Json
$destinations = @{secrets='/run/workbench-secrets';uploads='/app/runtime-temp';artifacts='/app/hop-project';outputs='/app/outputs'}
$script:sourceVolumes = @{}
foreach ($name in $destinations.Keys) {
    $volumeMatches = @($mounts | Where-Object {$_.Destination -eq $destinations[$name] -and $_.Type -eq 'volume'})
    if ($volumeMatches.Count -ne 1 -or $volumeMatches[0].Name -ne "ai-etl-workbench_$name") { throw 'Unexpected backup source volume; no automatic substitution' }
    $script:sourceVolumes[$name] = $volumeMatches[0].Name
}
if ($CheckOnly) { Write-Output 'Backup preflight passed. No services stopped or files copied.'; return }
# Keep unencrypted secrets on the Linux filesystem with enforceable 0700,
# rather than assuming DrvFS chmod implements a private Windows ACL.
$backupBase = '/root/ai-etl-workbench-backups'
& wsl.exe -d RockyLinux9 -u root --exec mkdir -p --mode=700 $backupBase
if ($LASTEXITCODE -ne 0) { throw 'Cannot create private backup root' }
$mode = & wsl.exe -d RockyLinux9 -u root --exec stat -c '%a:%u:%F' $backupBase
if ($LASTEXITCODE -ne 0 -or $mode -ne '700:0:directory') { throw 'Backup root must be a root-owned 0700 directory, not a symlink' }
$linuxBatch = $backupBase + '/batch-' + [guid]::NewGuid().ToString()
& wsl.exe -d RockyLinux9 -u root --exec mkdir --mode=700 $linuxBatch
if ($LASTEXITCODE -ne 0) { throw 'Cannot create unique private backup directory' }
$linuxSource = Convert-ToWslPath (Join-Path $root 'backend')
& wsl.exe -d RockyLinux9 -u root --exec test -d $linuxBatch
if ($LASTEXITCODE -ne 0) { throw 'Private destination is not accessible from WSL; services were not stopped' }
& (Join-Path $PSScriptRoot 'stop-pilot.ps1')
try {
    Assert-BackupWritersStopped
    $dumpName = 'workbench-backup-' + [guid]::NewGuid().ToString() + '.dump'
    Invoke-BackupDocker @('exec','ai-etl-workbench-postgres-1','pg_dump','-U','workbench','-d','workbench','-Fc','-f',"/tmp/$dumpName") | Out-Null
    Invoke-BackupDocker @('cp',"ai-etl-workbench-postgres-1:/tmp/$dumpName","$linuxBatch/database-input.dump") | Out-Null
    $digest = & wsl.exe -d RockyLinux9 -u root --exec sha256sum ($linuxBatch + '/database-input.dump')
    if ($LASTEXITCODE -ne 0 -or $digest -notmatch '^([a-f0-9]{64})\s') { throw 'Cannot checksum private database dump' }
    $checksum = $Matches[1]
    Assert-BackupWritersStopped
    $arguments = @('run','--rm','--network','none','--read-only','--user','0:0','--entrypoint','python',
        '-e','WORKBENCH_RECOVERY_EXPORT=private-copies-v1',
        '--mount',"type=bind,src=$linuxSource,dst=/app/backend,readonly",
        '--mount',"type=bind,src=$linuxBatch,dst=/backup",
        '--mount',"type=bind,src=$linuxBatch/database-input.dump,dst=/snapshot.dump,readonly")
    foreach ($name in @('secrets','uploads','artifacts','outputs')) {
        $arguments += @('--mount',"type=volume,src=$($script:sourceVolumes[$name]),dst=/copies/$name,readonly")
    }
    $arguments += @($image,'-m','app.recovery_export','--dump-checksum',$checksum)
    $result = (Invoke-BackupDocker $arguments) | ConvertFrom-Json
    if ($result.status -ne 'PASS' -or $result.directory -notmatch '^recovery-[a-f0-9-]{36}$') { throw 'Private package export did not pass' }
    Assert-BackupWritersStopped
    # Distinguish a complete file package from an accepted coordinated backup.
    # No marker is written if postchecks fail, even if manifest.json exists.
    $marker = @{format='workbench-quiesced-backup-v1';status='PASS';package=$result.directory;dump_checksum=$checksum;
      application_writers_stopped=$true;persistent_admission_fence=$false;restore_verified=$false;
      contains_secrets=$true;scope='SINGLE_OPERATOR_MAINTENANCE_NO_EXTERNAL_WRITERS';created_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json -Compress
    $writer = 'import json,pathlib,sys; data=json.loads(sys.argv[1]); stream=(pathlib.Path("/backup")/"coordination.json").open("x"); json.dump(data,stream); stream.close()'
    Invoke-BackupDocker @('run','--rm','--network','none','--read-only','--user','0:0','--entrypoint','python',
        '--mount',"type=bind,src=$linuxBatch,dst=/backup",$image,'-c',$writer,$marker) | Out-Null
} catch {
    Write-Warning 'Backup failed. Application services remain stopped; PostgreSQL and partial files are retained. Inspect before manually resuming.'
    throw
}
& (Join-Path $PSScriptRoot 'start-pilot.ps1')
Invoke-BackupDocker @('start','ai-etl-workbench-control-worker-1') | Out-Null
Write-Output "Private backup created in RockyLinux9: $linuxBatch. Contains unencrypted credentials and master key; do not upload. This is same-host storage, not an offsite backup. Restore verification is still required."
