"""Actual Python adapter -> hop-run in worker image, no DB/model/network."""
import os
from pathlib import Path
from hashlib import sha256
from threading import Event
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.hop_metadata import local_metadata_json
from app.hop_cli import run_hop_cli
from test_etl_specification import design

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_ADAPTER_TEST')!='1',reason='Isolated native worker image required')

@pytest.mark.parametrize('invalid_number',[False,True])
def test_adapter_runs_real_hop_and_returns_saved_evidence(tmp_path,monkeypatch,invalid_number):
    spec,run,naming=design()
    root=ET.fromstring(compile_hpl(spec,run,naming)['hpl'])
    targets=[n for n in root.findall('transform') if n.findtext('type')=='TableOutput']
    assert len(targets)==1
    target=targets[0]
    for child in list(target):
        if child.tag not in ('name','type','copies','distribute','GUI'):target.remove(child)
    target.find('type').text='Dummy'
    assert all(n.findtext('type') in {'CSVInput','FilterRows','SortRows','GroupBy','SelectValues','Dummy'} for n in root.findall('transform'))
    source=Path('/validation/fixtures/compiler-input.csv').read_bytes()
    if invalid_number:
        # Retain the fixture header but supply an invalid numeric source value.
        source=source.split(b'\n',1)[0]+b'\nA,not-a-number\n'
    prepared={'directory':tmp_path,'source_path':tmp_path/'source.csv','hpl_path':tmp_path/'candidate.hpl','binding':{}}
    for key,checksum,data in [('source_path','source_checksum',source),('hpl_path','hpl_checksum',ET.tostring(root))]:
        prepared[key].write_bytes(data);prepared['binding'][checksum]=sha256(data).hexdigest()
    metadata=local_metadata_json().encode()
    (tmp_path/'metadata.json').write_bytes(metadata)
    saved=[]
    def sink(data):
        saved.append(data)
        return {'checksum':sha256(data).hexdigest(),'size':len(data)}
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    evidence=run_hop_cli(prepared,Event(),metadata_checksum=sha256(metadata).hexdigest(),
        expected_nodes=[n.findtext('name') for n in root.findall('transform')],environment=dict(os.environ),log_sink=sink)
    assert len(saved)==1
    assert evidence['result']['status']==('FAILED' if invalid_number else 'COMPLETED'),evidence
    assert evidence['result']['log_checksum']==sha256(saved[0]).hexdigest()
    if not invalid_number:assert evidence['nodes']['target']['read']==3
    assert evidence['qa_passed'] is False
