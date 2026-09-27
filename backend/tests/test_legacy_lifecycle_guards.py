"""Legacy entry points must stop before demo writes, process kills or cleanup."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('name,offset', [('start.ps1',1),('stop.ps1',0)])
def test_legacy_entrypoint_fails_before_side_effects(name,offset):
    path = ROOT/'scripts'/name
    if not path.exists():
        pytest.skip('Source checkout required for PowerShell entrypoint check')
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    assert lines[offset].startswith("throw 'Legacy ")
    assert 'docs/pilot-service-lifecycle.md' in lines[offset]
