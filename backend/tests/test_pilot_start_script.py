"""Execute the PowerShell entrypoint with fake external commands, not real Docker."""
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'start-pilot.ps1'


@pytest.mark.parametrize('scenario', ['running', 'stopped', 'running_control', 'stopped_control', 'wrong_identity', 'paused', 'inspect_error', 'check'])
def test_pilot_resume_boundaries(scenario):
    pwsh = shutil.which('pwsh')
    if not pwsh or not SCRIPT.exists():
        pytest.skip('PowerShell and source checkout required')
    wrapper = r'''
$global:starts = @()
function global:wsl.exe {
    $global:LASTEXITCODE = 0
    $name = $args[-1]
    $service = $name.Replace('ai-etl-workbench-', '').Replace('-1', '')
    if ($args -contains 'inspect') {
        if ($scenario -eq 'inspect_error') { $global:LASTEXITCODE=1; return }
        if ($args -contains '{{json .Config.Labels}}') {
            $project = if ($scenario -eq 'wrong_identity' -and $service -eq 'web') {'other'} else {'ai-etl-workbench'}
            return (@{'com.docker.compose.project'=$project; 'com.docker.compose.service'=$service} | ConvertTo-Json -Compress)
        }
        if ($scenario -eq 'paused') { return 'paused' }
        if ($scenario -in @('stopped','stopped_control','check')) { return 'exited' }
        return 'running'
    }
    if ($args -contains 'start') { $global:starts += $name; return $name }
    throw 'Unexpected Docker mutation'
}
function global:Invoke-RestMethod { return @{status='ready'} }
$failed=$false
try { & $scriptPath -CheckOnly:($scenario -eq 'check') -IncludeControlWorker:($scenario.EndsWith('_control')) | Out-Null } catch { $failed=$true }
@{failed=$failed; starts=@($global:starts)} | ConvertTo-Json -Compress
'''
    import json
    prefix = f"$scenario='{scenario}'; $scriptPath='{str(SCRIPT).replace(chr(39), chr(39)*2)}';\n"
    result = subprocess.run([pwsh, '-NoProfile', '-Command', prefix + wrapper], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['failed'] == (scenario in {'wrong_identity', 'paused', 'inspect_error'})
    services = ('postgres', 'api', 'web', 'control-worker') if scenario.endswith('_control') else ('postgres', 'api', 'web')
    assert payload['starts'] == ([f'ai-etl-workbench-{s}-1' for s in services] if scenario.startswith('stopped') else [])
