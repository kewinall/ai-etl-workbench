"""Run the real PowerShell stop entrypoint with isolated command doubles."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'stop-pilot.ps1'


@pytest.mark.parametrize('scenario', [
    'idle', 'check', 'native_worker', 'opaque_process', 'other_container',
    'pending_runs', 'pending_hop', 'pending_ai', 'pending_release',
    'post_pending', 'identity', 'paused', 'db_error', 'stop_error',
])
def test_safe_stop(scenario):
    pwsh = shutil.which('pwsh')
    if not pwsh or not SCRIPT.exists():
        pytest.skip('PowerShell and source checkout required')
    wrapper = r'''
$global:stops=@(); $global:queries=0
function global:Get-CimInstance {
    if ($scenario -eq 'native_worker') { return @{CommandLine='python -m app.local_sa_worker --serve'} }
    if ($scenario -eq 'opaque_process') { return @{CommandLine=$null} }
    return @()
}
function global:wsl.exe {
    $global:LASTEXITCODE=0
    $name=$args[-1]
    if ($args -contains 'inspect') {
        $service=$name.Replace('ai-etl-workbench-','').Replace('-1','')
        if ($args -contains '{{json .Config.Labels}}') {
            $project=if ($scenario -eq 'identity' -and $service -eq 'control-worker') {'other'} else {'ai-etl-workbench'}
            return (@{'com.docker.compose.project'=$project;'com.docker.compose.service'=$service} | ConvertTo-Json -Compress)
        }
        if ($scenario -eq 'paused') { return 'paused' }
        if ($name -in $global:stops) { return 'exited' }
        return 'running'
    }
    if ($args -contains 'ps') {
        if ($scenario -eq 'other_container') { return 'ai-etl-portable-api-test' }
        return 'ai-etl-workbench-postgres-1'
    }
    if ($args -contains 'psql') {
        if ($scenario -eq 'db_error') { $global:LASTEXITCODE=1; return }
        $global:queries++
        $counts=@{runs=0;hop=0;ai=0;release=0}
        if ($scenario.StartsWith('pending_')) { $counts[$scenario.Replace('pending_','')]=1 }
        if ($scenario -eq 'post_pending' -and $global:queries -gt 1) { $counts.hop=1 }
        return ($counts | ConvertTo-Json -Compress)
    }
    if ($args -contains 'stop') {
        if ($args -notcontains '--timeout' -or $args -notcontains '-1') { throw 'Forced timeout is forbidden' }
        if ($scenario -eq 'stop_error') { $global:LASTEXITCODE=1; return }
        $global:stops += $name
        return $name
    }
    throw 'Unexpected command'
}
$failed=$false
try { & $scriptPath -CheckOnly:($scenario -eq 'check') | Out-Null } catch { $failed=$true }
@{failed=$failed;stops=@($global:stops);queries=$global:queries} | ConvertTo-Json -Compress
'''
    prefix = f"$scenario='{scenario}';$scriptPath='{str(SCRIPT).replace(chr(39), chr(39)*2)}';\n"
    result = subprocess.run([pwsh, '-NoProfile', '-Command', prefix + wrapper], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['failed'] == (scenario not in {'idle', 'check'})
    expected = [f'ai-etl-workbench-{s}-1' for s in ('control-worker', 'web', 'api')]
    assert payload['stops'] == (expected if scenario in {'idle', 'post_pending'} else [])
    if scenario in {'idle', 'post_pending'}:
        assert payload['queries'] == 2
