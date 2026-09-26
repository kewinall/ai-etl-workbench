"""Real Hop range boundaries without DB/network; not full Vertica acceptance."""
import os
from hashlib import sha256
from threading import Event
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.hop_cli import run_hop_cli
from app.hop_metadata import local_metadata_json
from app.platform_harness import checksum
from test_date_range_specification import date_design

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_ADAPTER_TEST') != '1',
                                reason='Explicit network-disabled native Hop runner required')


@pytest.mark.parametrize('kind', ['DATE', 'TIMESTAMP'])
def test_inclusive_start_exclusive_end_and_null_in_real_hop(tmp_path, monkeypatch, kind):
    spec, run, naming = date_design(kind)
    spec['aggregation'] = None
    spec['output_columns'] = ['category', 'amount', 'event_date']
    naming['contract_json']['columns'] = [c for c in naming['contract_json']['columns'] if not c['source_name'].startswith('$metric.')]
    naming['checksum'] = checksum(naming['contract_json']['columns'])
    spec['naming']['checksum'] = naming['checksum']
    result = compile_hpl(spec, run, naming)
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    root = ET.fromstring(result['hpl'])
    target = root.find("./transform[type='TableOutput']")
    for child in list(target):
        if child.tag not in ('name', 'type', 'copies', 'distribute', 'GUI'):
            target.remove(child)
    target.find('type').text = 'Dummy'
    dates = ['2026-08-31', '2026-09-01', '2026-09-30', '2026-10-01', '']
    if kind == 'TIMESTAMP':
        dates = ['2026-08-31 23:59:59', '2026-09-01 00:00:00', '2026-09-30 23:59:59', '2026-10-01 00:00:00', '']
    source = ('category,amount,event_date\n' + ''.join(f'row{i},200.50,{d}\n' for i,d in enumerate(dates))).encode()
    prepared = {'directory': tmp_path, 'source_path': tmp_path/'source.csv', 'hpl_path': tmp_path/'candidate.hpl', 'binding': {}}
    for key, name, data in [('source_path', 'source_checksum', source), ('hpl_path', 'hpl_checksum', ET.tostring(root))]:
        prepared[key].write_bytes(data)
        prepared['binding'][name] = sha256(data).hexdigest()
    metadata = local_metadata_json().encode()
    (tmp_path/'metadata.json').write_bytes(metadata)
    saved = []
    def sink(data):
        saved.append(data)
        return {'checksum': sha256(data).hexdigest(), 'size': len(data)}
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
    evidence = run_hop_cli(prepared, Event(), metadata_checksum=sha256(metadata).hexdigest(),
                           expected_nodes=[n.findtext('name') for n in root.findall('transform')],
                           environment=dict(os.environ), log_sink=sink)
    assert evidence['result']['status'] == 'COMPLETED', evidence
    assert evidence['nodes']['target']['read'] == 2, evidence
    assert evidence['nodes']['discard']['read'] == 3, evidence
    assert len(saved) == 1 and evidence['qa_passed'] is False
