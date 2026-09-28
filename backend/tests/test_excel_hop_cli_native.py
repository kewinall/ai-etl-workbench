"""Real fixed CLI parameters and ExcelInput; Dummy sink, no Vertica/QA claim."""
import os
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.hop_command import hop_command
from app.hop_metadata import local_metadata_json
from app.hop_log_evidence import hop_log_evidence
from test_excel_specification import excel_design
from test_source_staging_hop import linux_path

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_STAGING_TEST') != '1',
                               reason='Explicit native Hop verification required')


@pytest.mark.parametrize('missing_source', [False, True])
@pytest.mark.parametrize('private_launcher', [False, True])
def test_excel_real_cli_binds_required_xlsx_and_fails_when_missing(tmp_path, missing_source, private_launcher):
    content = []
    compiled = compile_hpl(*excel_design(capture=content, rows=[['A', '150.25'], ['A', '20'], ['B', '200.25']]))
    root = ET.fromstring(compiled['hpl'])
    target = root.find("transform[name='target']")
    assert target.findtext('type') == 'TableOutput'
    for child in list(target):
        if child.tag not in ('name', 'type', 'copies', 'distribute', 'GUI'):
            target.remove(child)
    target.find('type').text = 'Dummy'
    assert all(n.findtext('type') in {'ExcelInput', 'FilterRows', 'SortRows', 'GroupBy', 'SelectValues', 'Dummy'}
               for n in root.findall('transform'))
    (tmp_path / 'candidate.hpl').write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
    (tmp_path / 'metadata.json').write_text(local_metadata_json(), encoding='utf-8')
    if not missing_source:
        (tmp_path / 'source.xlsx').write_bytes(content[0])
    mount = '/candidate with space,comma'
    args = hop_command(mount, source_format='XLSX', credential_launcher=private_launcher)
    extra = []
    if private_launcher:
        launcher = Path(__file__).resolve().parents[2] / 'backend/app/java/WorkbenchHopRun.java'
        extra = ['-e', 'WORKBENCH_VERTICA_PASSWORD=synthetic-unused',
                 '-v', linux_path(launcher) + ':/app/backend/app/java/WorkbenchHopRun.java:ro']
    result = subprocess.run(['wsl', '-d', 'RockyLinux9', '-u', 'root', '--exec', 'docker', 'run', '--rm', '--pull', 'never',
        '--network', 'none', '--hostname', 'hop-validation', '--add-host', 'hop-validation:127.0.0.1',
        '--entrypoint', args[0], '-w', '/opt/hop', '-v', linux_path(tmp_path) + ':' + mount + ':ro',
        *extra, 'ai-etl-workbench-worker:dev' if private_launcher else 'apache/hop:2.12.0', *args[1:]],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    evidence = hop_log_evidence({'started': True, 'reason': 'EXITED', 'exit_code': result.returncode,
        'output': (result.stdout + result.stderr).encode()}, [node.findtext('name') for node in root.findall('transform')])
    assert evidence['result']['status'] == ('FAILED' if missing_source else 'COMPLETED'), evidence
    if missing_source:
        assert result.returncode != 0, result.stdout + result.stderr
        assert re.search(r'source\.0[^\n]*ERROR', result.stdout + result.stderr), result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert re.search(r'target\.0[^\n]*\bR=2\b[^\n]*\bE=0\b', result.stdout), result.stdout
        assert evidence['complete_node_evidence']
        if private_launcher:
            assert len(root.findall('transform')) == 7  # Six plan stages plus the required filter discard sink.
            assert 'WORKBENCH_METRICS_END_V1 7' in result.stdout, result.stdout
            assert len(evidence['nodes']) == 7
            assert evidence['nodes']['discard']['read'] == 1
            assert evidence['nodes']['target']['read'] == 2
    assert 'synthetic-unused' not in result.stdout + result.stderr
