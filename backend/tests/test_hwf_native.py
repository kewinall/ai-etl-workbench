"""Real HWF -> generated HPL with test-only Dummy sink; no database connection."""
import json
import os
from pathlib import Path
import re
import subprocess
from xml.etree import ElementTree as ET
import pytest
from app.hwf_compiler import compile_hwf
from app.hop_metadata import local_metadata
from app.workflow_log_evidence import workflow_log_evidence
from test_etl_specification import design
from test_source_staging_hop import linux_path

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_STAGING_TEST') != '1', reason='Opt-in native Hop')


@pytest.mark.parametrize('missing_source', [False, True])
def test_workflow_relative_pipeline_parameters_and_failure(tmp_path, missing_source):
    spec, run, naming = design(); compiled = compile_hwf(spec, run, naming)
    root = ET.fromstring(compiled['hpl'])
    target = next(n for n in root.findall('transform') if n.findtext('type') == 'TableOutput')
    for child in list(target):
        if child.tag not in ('name', 'type', 'copies', 'distribute', 'GUI'): target.remove(child)
    target.find('type').text = 'Dummy'
    (tmp_path/'pipeline.hpl').write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
    (tmp_path/'workflow.hwf').write_text(compiled['hwf'], encoding='utf-8')
    metadata = local_metadata()
    metadata['workflow-run-configuration'] = [{'name':'local','defaultSelection':False,'engineRunConfiguration':{'Local':{'safe_mode':False}}}]
    (tmp_path/'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    if not missing_source:
        fixture = Path(__file__).resolve().parents[2]/'scripts/hop/fixtures/compiler-input.csv'
        (tmp_path/'source.csv').write_bytes(fixture.read_bytes())
    mount = '/candidate with space,comma'
    result = subprocess.run(['wsl','-d','RockyLinux9','-u','root','--exec','docker','run','--rm','--pull','never',
        '--network','none','--hostname','hop-validation','--add-host','hop-validation:127.0.0.1',
        '--entrypoint','/opt/hop/hop-run.sh','-w','/opt/hop','-v',linux_path(tmp_path)+':'+mount+':ro',
        'apache/hop:2.12.0','--file='+mount+'/workflow.hwf','--metadata-export='+mount+'/metadata.json',
        '--runconfig=local','--level=BASIC','--parameters-separator=;',
        '--parameters=SOURCE_CSV='+mount+'/source.csv'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    log = result.stdout + result.stderr
    print(json.dumps({'case':'missing_source' if missing_source else 'success',
        'exit_code':result.returncode,
        'workflow_events':[line for line in log.splitlines() if any(marker in line for marker in
            ('Finished action','Workflow execution','Execution finished','Starting action'))]},ensure_ascii=False))
    proof=workflow_log_evidence(dict(started=True,reason='EXITED',exit_code=result.returncode,output=log.encode()),
        [node.findtext('name') for node in root.findall('transform')],ET.fromstring(compiled['hwf']).findtext('name'))
    if missing_source:
        assert not proof['workflow_completed']
        assert result.returncode != 0, log
        assert re.search(r'source\.0[^\n]*ERROR', log), log
    else:
        assert proof['workflow_completed'] and proof['result']['status']=='COMPLETED'
        assert result.returncode == 0, log
        assert re.search(r'target\.0[^\n]*\bR=3\b[^\n]*\bE=0\b', log), log
