import json
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'backup-pilot.ps1'


@pytest.mark.parametrize('scenario', ['valid', 'volume', 'image', 'stopped'])
def test_backup_preflight_is_readonly(scenario):
    pwsh = shutil.which('pwsh')
    if not pwsh or not SCRIPT.exists():
        pytest.skip('PowerShell and source checkout required')
    wrapper = r'''
$global:mutations=0
function global:Get-CimInstance { return @() }
function global:wsl.exe {
    $global:LASTEXITCODE=0
    if ($args -contains 'ps') { return 'ai-etl-workbench-postgres-1' }
    if ($args -contains 'psql') { return '{"runs":0,"hop":0,"ai":0,"release":0}' }
    if ($args -contains 'inspect') {
        $service=$args[-1].Replace('ai-etl-workbench-','').Replace('-1','')
        if ($args -contains '{{json .Config.Labels}}') {
            return (@{'com.docker.compose.project'='ai-etl-workbench';'com.docker.compose.service'=$service}|ConvertTo-Json -Compress)
        }
        if ($args -contains '{{.State.Status}}') {
            if ($scenario -eq 'stopped' -and $service -eq 'web') {return 'exited'}
            return 'running'
        }
        if ($args -contains '{{.Image}}') {
            if ($scenario -eq 'image') {return 'mutable-tag'}
            return ('sha256:' + ('a'*64))
        }
        if ($args -contains '{{json .Mounts}}') {
            $paths=@{secrets='/run/workbench-secrets';uploads='/app/runtime-temp';artifacts='/app/hop-project';outputs='/app/outputs'}
            $mounts=@()
            foreach ($key in $paths.Keys) {
                $volume=if ($scenario -eq 'volume' -and $key -eq 'outputs') {'other-project'} else {'ai-etl-workbench_'+$key}
                $mounts+=@{Type='volume';Name=$volume;Destination=$paths[$key]}
            }
            return ($mounts|ConvertTo-Json -Compress)
        }
    }
    $global:mutations++
    throw 'Unexpected non-readonly operation'
}
$failed=$false
try { & $scriptPath -CheckOnly | Out-Null } catch {$failed=$true}
@{failed=$failed;mutations=$global:mutations}|ConvertTo-Json -Compress
'''
    prefix = f"$scenario='{scenario}';$scriptPath='{str(SCRIPT).replace(chr(39), chr(39)*2)}';\n"
    result = subprocess.run([pwsh, '-NoProfile', '-Command', prefix + wrapper], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    result = json.loads(result.stdout)
    assert result == {'failed': scenario != 'valid', 'mutations': 0}
