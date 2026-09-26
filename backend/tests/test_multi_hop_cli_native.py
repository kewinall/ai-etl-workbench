"""Real staged multi-source parameters through hop-run; no database or model."""
from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
import os
from threading import Event
from uuid import uuid4
from xml.etree import ElementTree as ET
import pytest
from app import task_uploads, execution_preparation
from app.hpl_compiler import compile_hpl
from app.hop_cli import run_hop_cli
from app.hop_metadata import local_metadata_json
from test_join_semantics import join_design

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_ADAPTER_TEST') != '1',
                                reason='Explicit network-disabled native Hop adapter required')


@pytest.mark.parametrize('kind,expected', [('LEFT',3), ('INNER',1)])
def test_real_hop_cli_uses_both_staged_contracts_and_parameters(tmp_path, monkeypatch, kind, expected):
    monkeypatch.setattr(task_uploads,'ROOT',tmp_path)
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path/'uploads')
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    spec,run,naming = join_design()
    spec['joins'][0]['join_type'] = kind
    run['input_snapshot']['target_config']['join_contract_v1']['joins'][0]['join_type'] = kind
    config = run['input_snapshot']['source_config']
    # Different delimiters ensure the second input cannot silently reuse the first.
    for index,text in enumerate(('客戶編號,名稱\nA,left\nB,unmatched\n,null_left\n', '客戶編號|名稱\nA|right\n|null_right\n')):
        uploaded = task_uploads.save_and_profile(f'input{index}.csv', text.encode())
        config['sources'][index] = {**uploaded, 'type':'CSV', 'has_actual_data':True,
                                    'fields':config['sources'][index]['fields']}
    compiled = compile_hpl(spec,run,naming)
    assert compiled['status'] == 'VALIDATED_NOT_APPROVED', compiled
    root = ET.fromstring(compiled['hpl'])
    target = root.find("./transform[name='target']")
    for child in list(target):
        if child.tag not in ('name','type','copies','distribute','GUI'): target.remove(child)
    target.find('type').text = 'Dummy'
    xml = ET.tostring(root,encoding='utf-8').decode()
    candidate = {'approval_id':'synthetic-test-only', 'specification_checksum':compiled['specification_checksum'],
        'run':run, 'compiled':{**compiled,'hpl':xml,'hpl_checksum':sha256(xml.encode()).hexdigest()}}
    monkeypatch.setattr(execution_preparation,'load_approved_candidate',lambda *a,**k:deepcopy(candidate))
    class Queue:
        def conn(self): return nullcontext(None)
    with execution_preparation.prepare_approved_source(Queue(),'task',run['run_id'],uuid4()) as prepared:
        metadata = local_metadata_json().encode()
        (prepared['directory']/'metadata.json').write_bytes(metadata)
        saved = []
        def sink(data):
            saved.append(data)
            return {'checksum':sha256(data).hexdigest(),'size':len(data)}
        evidence = run_hop_cli(prepared,Event(),metadata_checksum=sha256(metadata).hexdigest(),
            expected_nodes=[node.findtext('name') for node in root.findall('transform')],
            environment=dict(os.environ),log_sink=sink)
        assert evidence['result']['status'] == 'COMPLETED', evidence
        assert evidence['nodes']['source_0']['written'] == 3
        assert evidence['nodes']['source_1']['written'] == 2
        assert evidence['nodes']['target']['read'] == expected
        assert evidence['nodes']['join_discard']['read'] == 1
        assert evidence['qa_passed'] is False and len(saved) == 1
        directory = prepared['directory']
    assert not directory.exists()
