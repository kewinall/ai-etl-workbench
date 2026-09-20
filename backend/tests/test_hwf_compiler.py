from hashlib import sha256
from xml.etree import ElementTree as ET
from app.hwf_compiler import compile_hwf
from test_etl_specification import design


def test_fixed_single_pipeline_workflow_and_binding():
    spec, run, naming = design()
    result = compile_hwf(spec, run, naming)
    assert result == compile_hwf(spec, run, naming)
    assert not result['execution_authorized']
    assert result['hwf_checksum'] == sha256(result['hwf'].encode()).hexdigest()
    root = ET.fromstring(result['hwf'])
    assert result['hpl_checksum'] in root.findtext('description')
    assert [a.findtext('type') for a in root.findall('actions/action')] == ['SPECIAL', 'PIPELINE']
    action = root.findall('actions/action')[1]
    assert action.findtext('filename') == '${Internal.Workflow.Filename.Folder}/pipeline.hpl'
    assert action.findtext('wait_until_finished') == 'Y'
    assert action.findtext('exec_per_row') == 'N'
    assert action.findtext('run_configuration') == 'local'
    assert root.findtext('parameters/parameter/name') == 'SOURCE_CSV'
    assert len(root.findall('hops/hop')) == 1


def test_invalid_spec_cannot_generate_workflow():
    spec, run, naming = design(); spec['write_mode'] = 'TRUNCATE'
    assert 'hwf' not in compile_hwf(spec, run, naming)
