"""Repository source visibility, not a claim that anything has been committed/pushed."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    'scripts/hop/ValidatePipeline.java',
    'scripts/hop/ExecuteCompilerProbe.java',
    'scripts/hop/InspectCompilerPlugins.java',
    'scripts/hop/fixtures/minimal.hpl',
    'scripts/hop/fixtures/missing-plugin.hpl',
    'scripts/hop/fixtures/invalid-edge.hpl',
    'scripts/hop/fixtures/doctype.hpl',
    'scripts/hop/fixtures/compiler-input.csv',
    'scripts/test-hop-compiler.ps1',
    'scripts/test-hop-metadata.ps1',
]
EXCLUDED = [
    '.env', '.env.local', 'hop/lib/runtime.jar', 'outputs/candidate.hpl',
    'frontend/test-results/evidence.json', 'scripts/hop/private.key',
    'scripts/hop/fixtures/customer-data.csv', 'scripts/hop/credentials.json',
]


def test_native_verification_sources_not_ignored_but_runtime_and_unknown_data_are():
    git = shutil.which('git')
    if not git or not (ROOT / '.git').exists():
        pytest.skip('Git checkout required for distribution visibility check')
    for name in REQUIRED:
        assert (ROOT / name).is_file(), name
    process = subprocess.run([git, '-c', f'safe.directory={ROOT.as_posix()}', 'check-ignore', '--no-index', '-z', '--stdin'],
                             cwd=ROOT, input=('\0'.join(REQUIRED + EXCLUDED)+'\0').encode(), capture_output=True, timeout=10)
    assert process.returncode in (0, 1), process.stderr
    assert set(process.stdout.decode().rstrip('\0').split('\0')) == set(EXCLUDED)
