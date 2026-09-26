"""Native generated two-source HWF; Dummy sink, no DB/model/authorization proof."""
import json
import os
import subprocess
from xml.etree import ElementTree as ET
import pytest
from app.hwf_compiler import compile_hwf
from app.hop_metadata import local_metadata
from app.workflow_log_evidence import workflow_log_evidence
from test_join_semantics import join_design
from test_source_staging_hop import linux_path

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_STAGING_TEST') != '1', reason='Opt-in native Hop')


@pytest.mark.parametrize('missing_right', [False,True])
def test_two_parameters_reach_pipeline_and_missing_right_fails(tmp_path, missing_right):
    spec,run,naming = join_design()
    compiled = compile_hwf(spec,run,naming)
    root = ET.fromstring(compiled['hpl'])
    target = next(n for n in root.findall('transform') if n.findtext('type') == 'TableOutput')
    for child in list(target):
        if child.tag not in ('name','type','copies','distribute','GUI'): target.remove(child)
    target.find('type').text = 'Dummy'
    (tmp_path/'pipeline.hpl').write_text(ET.tostring(root,encoding='unicode'),encoding='utf-8')
    (tmp_path/'workflow.hwf').write_text(compiled['hwf'],encoding='utf-8')
    (tmp_path/'left.csv').write_text('客戶編號,名稱\nA,alpha\nB,beta\n,empty\n',encoding='utf-8')
    if not missing_right:
        (tmp_path/'right.csv').write_text('客戶編號|名稱\nA|match\n|null-right\n',encoding='utf-8')
    metadata = local_metadata()
    metadata['workflow-run-configuration'] = [{'name':'local','defaultSelection':False,'engineRunConfiguration':{'Local':{'safe_mode':False}}}]
    (tmp_path/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
    mount = '/join candidate'
    result = subprocess.run(['wsl','-d','RockyLinux9','-u','root','--exec','docker','run','--rm','--pull','never',
        '--network','none','--hostname','hop-validation','--add-host','hop-validation:127.0.0.1',
        '--entrypoint','/opt/hop/hop-run.sh','-w','/opt/hop','-v',linux_path(tmp_path)+':'+mount+':ro',
        'apache/hop:2.12.0','--file='+mount+'/workflow.hwf','--metadata-export='+mount+'/metadata.json',
        '--runconfig=local','--level=BASIC','--parameters-separator=;',
        '--parameters=SOURCE_CSV_0='+mount+'/left.csv;SOURCE_CSV_1='+mount+'/right.csv'],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    log = (result.stdout+result.stderr).encode()
    proof = workflow_log_evidence(dict(started=True,reason='EXITED',exit_code=result.returncode,output=log),
        [n.findtext('name') for n in root.findall('transform')],ET.fromstring(compiled['hwf']).findtext('name'))
    if missing_right:
        assert result.returncode != 0 and not proof['workflow_completed'], log.decode()
    else:
        assert result.returncode == 0 and proof['workflow_completed'] and proof['result']['status'] == 'COMPLETED', log.decode()
