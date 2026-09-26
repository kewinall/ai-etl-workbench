"""Actual compiler CSVInput semantics; network-disabled, Dummy sink, no DB."""
import os
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.platform_harness import checksum
from test_join_semantics import join_design
from test_join_native import wsl_path

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_JOIN_TEST')!='1',
    reason='Explicit network-disabled native CSV runtime probe required')


@pytest.mark.parametrize('case',['empty_and_spaces','overlength_not_truncated','invalid_integer'])
def test_compiled_csv_value_behavior(tmp_path,case):
    spec,run,naming=join_design()
    run['input_snapshot']['source_config']['csv_input_contracts_v1']['sources']['source.1']['delimiter']=','
    if case=='invalid_integer':
        run['input_snapshot']['source_config']['sources'][0]['fields'][1]['type']='BIGINT'
        naming['contract_json']['columns'][1]['vertica_type']='BIGINT'
        naming['checksum']=checksum(naming['contract_json']['columns'])
        spec['naming']['checksum']=naming['checksum']
    compiled=compile_hpl(spec,run,naming)
    assert compiled['status']=='VALIDATED_NOT_APPROVED',compiled
    root=ET.fromstring(compiled['hpl'])
    for i,side in enumerate(('left','right')):
        root.find(f"./transform[name='source_{i}']/filename").text=f'/candidate/{side}.csv'
    target=root.find("./transform[name='target']")
    for child in list(target):
        if child.tag not in ('name','type','copies','distribute','GUI'):target.remove(child)
    target.find('type').text='Dummy'
    (tmp_path/'candidate.hpl').write_bytes(ET.tostring(root,encoding='utf-8'))
    left={'empty_and_spaces':'A,\nB,  keep  \n',
          'overlength_not_truncated':'A,'+'x'*33+'\n',
          'invalid_integer':'A,not_an_integer\n'}[case]
    (tmp_path/'left.csv').write_text('key,value\n'+left,encoding='utf-8')
    (tmp_path/'right.csv').write_text('key,value\nA,right_a\nB,right_b\n',encoding='utf-8')
    repo=Path(__file__).resolve().parents[2]
    result=subprocess.run(['wsl','-d','RockyLinux9','-u','root','--','docker','run','--rm','--pull','never',
        '--network','none','--hostname','hop-validation','--add-host','hop-validation:127.0.0.1',
        '--entrypoint','java','-w','/opt/hop','-v',wsl_path(repo/'scripts'/'hop')+':/validation:ro',
        '-v',wsl_path(tmp_path)+':/candidate:ro','ai-etl-workbench-worker:dev',
        '-cp','lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*','/validation/ExecuteJoinProbe.java'],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=75)
    if case=='invalid_integer':
        assert result.returncode!=0
        assert 'Hop execution failed' in result.stderr
        assert 'not_an_integer' in result.stdout+result.stderr
        assert 'NATIVE_JOIN_COLLECTED' not in result.stdout
    else:
        assert result.returncode==0,result.stdout+result.stderr
        actual=[line.split('=',1)[1] for line in result.stdout.splitlines() if line.startswith('SYNTHETIC_JOIN_RESULT=')]
        expected=['A|<NULL>|A|right_a','B|  keep  |B|right_b'] if case=='empty_and_spaces' else ['A|'+'x'*33+'|A|right_a']
        assert sorted(actual)==sorted(expected)
