"""Actual hop-run + generated local metadata. Test sink, not Vertica QA."""
import os
import re
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.hop_command import hop_command
from app.hop_metadata import local_metadata_json
from app.hop_log_evidence import hop_log_evidence
from test_etl_specification import design
from test_source_staging_hop import linux_path

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_STAGING_TEST')!='1',reason='Explicit native Hop verification required')


@pytest.mark.parametrize('missing_source',[False,True])
def test_real_cli_parameter_and_metadata_binding(tmp_path,missing_source):
    spec,run,naming=design()
    compiled=compile_hpl(spec,run,naming)
    root=ET.fromstring(compiled['hpl'])
    targets=[node for node in root.findall('transform') if node.findtext('type')=='TableOutput']
    assert len(targets)==1
    target=targets[0]
    for child in list(target):
        if child.tag not in ('name','type','copies','distribute','GUI'):target.remove(child)
    target.find('type').text='Dummy'
    assert all(n.findtext('type') in {'CSVInput','FilterRows','SortRows','GroupBy','SelectValues','Dummy'} for n in root.findall('transform'))
    (tmp_path/'candidate.hpl').write_text(ET.tostring(root,encoding='unicode'),encoding='utf-8')
    (tmp_path/'metadata.json').write_text(local_metadata_json(),encoding='utf-8')
    fixture=Path(__file__).resolve().parents[2]/'scripts'/'hop'/'fixtures'/'compiler-input.csv'
    if not missing_source:
        (tmp_path/'source.csv').write_bytes(fixture.read_bytes())
    # Comma and space deliberately exercise literal argv and parameter separator.
    mount='/candidate with space,comma'
    args=hop_command(mount)
    result=subprocess.run(['wsl','-d','RockyLinux9','-u','root','--exec','docker','run','--rm','--pull','never',
        '--network','none','--hostname','hop-validation','--add-host','hop-validation:127.0.0.1',
        '--entrypoint',args[0],'-w','/opt/hop','-v',linux_path(tmp_path)+':'+mount+':ro',
        'apache/hop:2.12.0',*args[1:]],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    evidence=hop_log_evidence({'started':True,'reason':'EXITED','exit_code':result.returncode,
        'output':(result.stdout+result.stderr).encode('utf-8')},[node.findtext('name') for node in root.findall('transform')])
    assert evidence['result']['status']==('FAILED' if missing_source else 'COMPLETED'),evidence
    if missing_source:
        assert result.returncode!=0,result.stdout+result.stderr
        assert re.search(r'source\.0[^\n]*ERROR',result.stdout+result.stderr),result.stdout+result.stderr
        assert re.search(r'source\.0[^\n]*\bE=1\b',result.stdout),result.stdout
    else:
        assert result.returncode==0,result.stdout+result.stderr
        assert re.search(r'target\.0[^\n]*\bR=3\b[^\n]*\bE=0\b',result.stdout),result.stdout
