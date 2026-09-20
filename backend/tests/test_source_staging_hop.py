"""Opt-in real Hop, fixed synthetic compiler probe, no DB or model calls."""
import os
import json
from hashlib import sha256
from decimal import Decimal
from pathlib import Path
import subprocess
import pytest

from app import task_uploads
from app.hpl_compiler import compile_hpl
from app.source_staging import stage_csv_source
from app.expected_result import ResultColumn, compare_expected_result
from app.result_oracle import compare_oracle_document
from app.platform_harness import checksum
from test_etl_specification import design

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_STAGING_TEST') != '1',
                                reason='Explicit local WSL Hop test required')


def linux_path(path):
    result = subprocess.run(['wsl','-d','RockyLinux9','-u','root','--','wslpath','-a',Path(path).as_posix()],
                            capture_output=True,text=True,check=True,timeout=15)
    value = result.stdout.strip()
    assert value.startswith('/') and '\n' not in value and ':' not in value
    return value


def test_real_hop_reads_verified_attempt_not_changed_upload(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    java = repo / 'scripts' / 'hop'
    fixture = (java / 'fixtures' / 'compiler-input.csv').read_bytes()
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    uploaded = task_uploads.save_and_profile('synthetic.csv', fixture)
    spec, run, naming = design()
    source = {**uploaded, 'type':'CSV', 'fields':run['input_snapshot']['source_config']['sources'][0]['fields']}
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    compiled = compile_hpl(spec, run, naming)
    (candidate / 'candidate.hpl').write_text(compiled['hpl'], encoding='utf-8')
    contract = run['input_snapshot']['source_config']['csv_input_contract_v1']
    with stage_csv_source(run['run_id'], source, contract) as staged:
        # Only the test's upload is changed, never the repository fixture.
        Path(uploaded['path']).write_bytes(b'changed after preflight\n')
        assert staged['path'].read_bytes() == fixture
        command = ['wsl','-d','RockyLinux9','-u','root','--','docker','run','--rm','--pull','never',
                   '--network','none','--hostname','hop-validation','--add-host','hop-validation:127.0.0.1',
                   '--entrypoint','java','-w','/opt/hop',
                   '-v',linux_path(java)+':/validation:ro',
                   '-v',linux_path(candidate)+':/candidate:ro',
                   '-v',linux_path(staged['path'])+':/validation/fixtures/compiler-input.csv:ro',
                   'apache/hop:2.12.0','-DHOP_AUTO_CREATE_CONFIG=Y','-cp',
                   'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*','/validation/ExecuteCompilerProbe.java']
        result = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'HOP_ROW_PROBE_PASSED rows=3 errors=0 target=TEST_COLLECTOR vertica=false release=false' in result.stdout
        metadata_lines=[line.removeprefix('SYNTHETIC_HOP_COLUMNS=') for line in result.stdout.splitlines()
                        if line.startswith('SYNTHETIC_HOP_COLUMNS=')]
        assert len(metadata_lines)==1
        actual_columns=metadata_lines[0].split('|')
        assert actual_columns==spec['output_columns']
        actual=[]
        for line in result.stdout.splitlines():
            if line.startswith('SYNTHETIC_HOP_RESULT='):
                category,total,count=line.removeprefix('SYNTHETIC_HOP_RESULT=').split('|')
                actual.append(dict(zip(actual_columns,[category,Decimal(total),int(count)])))
        columns=[ResultColumn(name,kind) for name,kind in zip(spec['output_columns'],['TEXT','DECIMAL','INTEGER'])]
        expected=[{'category':'A','total_amount':Decimal('301.35'),'row_count':2},
                  {'category':'B','total_amount':Decimal('300'),'row_count':1},
                  {'category':'a','total_amount':Decimal('110'),'row_count':1}]
        comparison=compare_expected_result(columns,expected,actual)
        assert comparison['status']=='MATCH'
        assert comparison['actual_count']==3
        assert comparison['qa_passed'] is comparison['release_ready'] is False
        # Same row count with a planted wrong total must be rejected by the shared comparator.
        wrong=[{**row,'total_amount':row['total_amount']+1} if row['category']=='A' else row for row in actual]
        assert compare_expected_result(columns,expected,wrong)['status']=='MISMATCH'
        oracle={'version':1,'specification_checksum':checksum(spec),'naming_checksum':naming['checksum'],
                'columns':[{'name':c.name,'kind':c.kind,'nullable':c.nullable} for c in columns],
                'rows':[{**row,'total_amount':str(row['total_amount'])} for row in expected]}
        content=json.dumps(oracle,sort_keys=True,separators=(',',':')).encode()
        pins={'document_checksum':sha256(content).hexdigest(),'specification_checksum':checksum(spec),'naming_checksum':naming['checksum']}
        bound=compare_oracle_document(content,actual,**pins)
        assert bound['status']=='MATCH'
        assert bound['qa_passed'] is False
        with pytest.raises(ValueError,match='ORACLE_BINDING_MISMATCH'):
            compare_oracle_document(content,actual,**{**pins,'specification_checksum':'f'*64})
        assert staged['path'].read_bytes() == fixture
        directory = staged['directory']
        print('HOP_STAGING_PASSED original_changed=true output_rows=3 network=none target=TEST_COLLECTOR')
    assert not directory.exists()
    assert Path(uploaded['path']).read_bytes() == b'changed after preflight\n'
