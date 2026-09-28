"""Real fixed JSON CLI and private metrics launcher; no network or DB sink."""
import os
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.hop_command import hop_command
from app.hop_metadata import local_metadata_json
from app.hop_log_evidence import hop_log_evidence
from test_json_specification import json_design, CONTENT
from test_source_staging_hop import linux_path

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_JSON_TEST') != '1',
                               reason='Explicit network-disabled JSON CLI probe required')


@pytest.mark.parametrize('missing', [False, True])
@pytest.mark.parametrize('private', [False, True])
def test_json_fixed_cli_preserves_null_records_and_missing_file_fails(tmp_path, missing, private):
    compiled = compile_hpl(*json_design())
    root = ET.fromstring(compiled['hpl'])
    target = root.find("transform[name='target']")
    assert target.findtext('type') == 'TableOutput'
    for child in list(target):
        if child.tag not in ('name', 'type', 'copies', 'distribute', 'GUI'): target.remove(child)
    target.find('type').text = 'Dummy'
    assert all(node.findtext('type') in {'RowGenerator', 'JsonInput', 'FilterRows', 'SortRows', 'GroupBy', 'SelectValues', 'Dummy'}
               for node in root.findall('transform'))
    (tmp_path / 'candidate.hpl').write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
    (tmp_path / 'metadata.json').write_text(local_metadata_json(), encoding='utf-8')
    if not missing: (tmp_path / 'source.json').write_bytes(CONTENT)
    mount = '/candidate with spaces,comma'
    args = hop_command(mount, source_format='JSON', credential_launcher=private)
    extra = []
    if private:
        launcher = Path(__file__).resolve().parents[2] / 'backend/app/java/WorkbenchHopRun.java'
        extra = ['-e', 'WORKBENCH_VERTICA_PASSWORD=synthetic-unused',
                 '-v', linux_path(launcher) + ':/app/backend/app/java/WorkbenchHopRun.java:ro']
    result = subprocess.run(['wsl', '-d', 'RockyLinux9', '-u', 'root', '--exec', 'docker', 'run', '--rm', '--pull', 'never',
        '--network', 'none', '--hostname', 'hop-validation', '--add-host', 'hop-validation:127.0.0.1',
        '--entrypoint', args[0], '-w', '/opt/hop', '-v', linux_path(tmp_path) + ':' + mount + ':ro',
        *extra, 'ai-etl-workbench-worker:dev' if private else 'apache/hop:2.12.0', *args[1:]],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    evidence = hop_log_evidence({'started': True, 'reason': 'EXITED', 'exit_code': result.returncode,
        'output': (result.stdout + result.stderr).encode()}, [node.findtext('name') for node in root.findall('transform')])
    assert 'synthetic-unused' not in result.stdout + result.stderr
    assert evidence['result']['status'] == ('FAILED' if missing else 'COMPLETED'), (evidence, result.stdout, result.stderr)
    if missing:
        assert result.returncode != 0
    else:
        assert result.returncode == 0
        assert evidence['complete_node_evidence']
        assert evidence['nodes']['source']['written'] == 6  # Includes the empty object, not just non-null records.
        assert evidence['nodes']['source_columns']['read'] == 6
        assert evidence['nodes']['target']['read'] == 2
        if private:
            from app.json_runtime_evidence import require_json_runtime_receipt
            receipt = require_json_runtime_receipt((result.stdout + result.stderr).encode())
            assert receipt['HOP_JSON_INPUT_INCLUDE_NULLS'] == 'Y'
            assert 'WORKBENCH_METRICS_END_V1 9' in result.stdout
            assert evidence['nodes']['discard']['read'] == 3
