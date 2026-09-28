from copy import deepcopy
from hashlib import sha256
from uuid import uuid4
from xml.etree.ElementTree import fromstring
import pytest
from app.json_source_profile import confirmed_json_profile
from app.json_contract_binding import validated_json_contract
from app.etl_specification import validate_specification
from app.hpl_compiler import compile_hpl
from app.hwf_compiler import compile_hwf
from app.platform_harness import checksum
from app.source_binding import execution_sources
from test_etl_specification import design, codes
from test_json_input_contract import policy


CONTENT = '[{"類別":"A","金額":150.25},{"類別":"A","金額":101.50},{"類別":"B","金額":99.50},{"類別":"C","金額":201.00},{"類別":"D","金額":null},{}]'.encode()


def json_design(content=CONTENT):
    spec, run, naming = design()
    upload_id = str(uuid4())
    profile = confirmed_json_profile(upload_id, sha256(content).hexdigest(), len(content), content=content)
    source = {**profile, 'type': 'JSON', 'has_actual_data': True, 'upload_id': upload_id, 'size': len(content)}
    config = {'sources': [source], 'json_input_contract_v1': policy()}
    run['input_snapshot'].update(source_type='JSON', source_config=config)
    naming['contract_json']['columns'][1]['vertica_type'] = 'NUMERIC(18,4)'
    naming['contract_json']['columns'][2]['vertica_type'] = 'NUMERIC(24,4)'
    naming['checksum'] = checksum(naming['contract_json']['columns'])
    spec['naming']['checksum'] = naming['checksum']
    spec.update(version=5, json_source=validated_json_contract(config)['reference'])
    return spec, run, naming


def test_json_compiler_binds_source_nodes_without_mutation_or_execution():
    args = json_design()
    before = deepcopy(args)
    result = compile_hwf(*args)
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    assert not result['execution_authorized']
    assert result == compile_hwf(*args) and args == before
    root = fromstring(result['hpl'])
    assert root.findtext('info/parameters/parameter/name') == 'SOURCE_JSON'
    assert root.findtext("transform[name='source_file']/fields/field/nullif") == '${SOURCE_JSON}'
    assert root.findtext("transform[name='source']/type") == 'JsonInput'
    assert root.findtext("transform[name='source']/doNotFailIfNoFile") == 'N'
    assert root.findtext("transform[name='source_columns']/fields/select_unspecified") == 'N'
    assert [stage['component'] for stage in result['plan']['stages']] == [
        'RowGenerator', 'JsonInput', 'SelectValues', 'FilterRows', 'SortRows', 'GroupBy', 'SelectValues', 'TableOutput']
    assert len(root.findall('transform')) == 9  # includes the explicit discard branch
    assert result['plan']['edges'][2] == {'from': 'source_columns', 'to': 'filter'}
    assert fromstring(result['hwf']).findtext('parameters/parameter/name') == 'SOURCE_JSON'
    assert 'SOURCE_CSV' not in result['hpl'] + result['hwf']
    with pytest.raises(ValueError, match='JSON_EXECUTION_NOT_READY'):
        execution_sources(args[1]['input_snapshot']['source_config'], 5)


def test_existing_excel_output_matches_pre_json_commit():
    from test_excel_csv_compatibility import baseline_module
    from test_excel_specification import excel_design
    from pathlib import Path
    import sys
    if not (Path(__file__).resolve().parents[2] / '.git').exists():
        pytest.skip('Git checkout required for immutable Excel baseline')
    revision = '42eaccb41bd45dbb0af7ba6b817074d65c440b7b'
    old_spec = baseline_module('etl_specification', revision)
    old_hpl = baseline_module('hpl_compiler', revision)
    old_hwf = baseline_module('hwf_compiler', revision)
    old_hpl.compilation_plan = old_spec.compilation_plan
    old_hwf.compile_hpl = old_hpl.compile_hpl
    try:
        args = excel_design()
        assert compile_hwf(*args) == old_hwf.compile_hwf(*args)
    finally:
        for module in (old_spec, old_hpl, old_hwf):
            sys.modules.pop(module.__name__, None)


@pytest.mark.parametrize('key', ['content_checksum', 'profile_checksum', 'contract_checksum'])
def test_json_fingerprints_cannot_be_changed(key):
    spec, run, naming = json_design()
    spec['json_source'][key] = 'f' * 64
    result = compile_hpl(spec, run, naming)
    assert 'SPEC_JSON_BINDING_MISMATCH' in codes(result)
    assert 'hpl' not in result


@pytest.mark.parametrize('mutation', ['missing', 'root', 'fields', 'csv', 'type'])
def test_json_unconfirmed_or_mixed_source_cannot_compile(mutation):
    spec, run, naming = json_design()
    config = run['input_snapshot']['source_config']
    if mutation == 'missing':
        config.pop('json_input_contract_v1')
    elif mutation == 'root':
        config['json_input_contract_v1']['root_shape'] = 'OBJECT'
    elif mutation == 'fields':
        config['sources'][0]['fields'][0]['name'] = 'changed'
    elif mutation == 'csv':
        config['csv_input_contract_v1'] = {}
    else:
        config['sources'][0]['type'] = 'CSV'
    result = compile_hpl(spec, run, naming)
    assert 'SPEC_JSON_INPUT_UNCONFIRMED' in codes(result)
    assert 'hpl' not in result


def test_prior_version_cannot_misinterpret_json_as_csv():
    spec, run, naming = json_design()
    spec.pop('json_source'); spec['version'] = 1
    assert 'SPEC_SOURCE_UNSUPPORTED' in codes(validate_specification(spec, run, naming))


def test_internal_filename_column_is_reserved():
    spec, run, naming = json_design()
    naming['contract_json']['columns'][0]['english_name'] = 'json_source_file'
    naming['checksum'] = checksum(naming['contract_json']['columns'])
    spec['naming']['checksum'] = naming['checksum']
    assert 'SPEC_JSON_INTERNAL_COLUMN_RESERVED' in codes(validate_specification(spec, run, naming))
