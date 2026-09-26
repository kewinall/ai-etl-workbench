"""Real credential launcher final counters; synthetic Dummy sink, no network/DB."""
import os
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.hwf_compiler import compile_hwf
from app.hop_metadata import local_metadata
from app.workflow_log_evidence import workflow_log_evidence
from app.hop_command import hop_command
from app.hop_log_evidence import hop_log_evidence
from test_join_semantics import join_design
from test_join_native import wsl_path

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_JOIN_TEST')!='1',reason='Explicit native launcher test required')


@pytest.mark.parametrize('case',['zero_discard','empty_sources','missing_source'])
@pytest.mark.parametrize('workflow',[False,True])
def test_real_final_metrics(tmp_path,case,workflow):
    spec,run,naming=join_design()
    compiled=(compile_hwf if workflow else compile_hpl)(spec,run,naming)
    root=ET.fromstring(compiled['hpl'])
    target=root.find("./transform[name='target']")
    for child in list(target):
        if child.tag not in ('name','type','copies','distribute','GUI'):target.remove(child)
    target.find('type').text='Dummy'
    (tmp_path/'candidate.hpl').write_bytes(ET.tostring(root,encoding='utf-8'))
    metadata=local_metadata()
    if workflow:
        (tmp_path/'pipeline.hpl').write_bytes(ET.tostring(root,encoding='utf-8'))
        (tmp_path/'workflow.hwf').write_text(compiled['hwf'],encoding='utf-8')
        metadata['workflow-run-configuration']=[dict(name='local',defaultSelection=False,engineRunConfiguration={'Local':{'safe_mode':False}})]
    (tmp_path/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
    for i in range(2):
        folder=tmp_path/f'source-{i}';folder.mkdir()
        if case=='missing_source' and i==0:continue
        delimiter=',' if i==0 else '|'
        text=f'key{delimiter}value\n'
        if case!='empty_sources':text+=f'A{delimiter}item\n'
        (folder/'source.csv').write_text(text,encoding='utf-8')
    repo=Path(__file__).resolve().parents[2]
    args=hop_command('/candidate',credential_launcher=True,source_count=2)
    if workflow:args=['--file=/candidate/workflow.hwf' if arg.startswith('--file=') else arg for arg in args]
    result=subprocess.run(['wsl','-d','RockyLinux9','-u','root','--exec','docker','run','--rm','--pull','never',
        '--network','none','--hostname','hop-validation','--add-host','hop-validation:127.0.0.1',
        '--entrypoint',args[0],'-w','/opt/hop','-e','WORKBENCH_VERTICA_PASSWORD=synthetic-unused',
        '-v',wsl_path(tmp_path)+':/candidate:ro',
        '-v',wsl_path(repo/'backend/app/java/WorkbenchHopRun.java')+':/app/backend/app/java/WorkbenchHopRun.java:ro',
        'ai-etl-workbench-worker:dev',*args[1:]],capture_output=True,timeout=75)
    output=result.stdout+result.stderr
    evidence=hop_log_evidence(dict(output=output,started=True,reason='EXITED',exit_code=result.returncode),
                             [n.findtext('name') for n in root.findall('transform')])
    assert evidence['result']['status']==('FAILED' if case=='missing_source' else 'COMPLETED'),output.decode(errors='replace')
    if case!='missing_source':
        assert b'WORKBENCH_METRICS_END_V1 9' in output
        assert evidence['complete_node_evidence']
        assert len(evidence['nodes'])==9
        assert evidence['nodes']['target']['read']==(0 if case=='empty_sources' else 1)
        assert b'synthetic-unused' not in output
    if workflow:
        proof=workflow_log_evidence(dict(output=output,started=True,reason='EXITED',exit_code=result.returncode),
            [n.findtext('name') for n in root.findall('transform')],ET.fromstring(compiled['hwf']).findtext('name'))
        assert proof['workflow_completed']==(case!='missing_source'),output.decode(errors='replace')
