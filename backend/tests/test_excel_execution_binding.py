from copy import deepcopy
from uuid import uuid4
import pytest
from app.source_binding import execution_sources, expected_prepared_binding
from app.delivery_compiler import compile_delivery_components
from test_excel_specification import excel_design
from test_etl_specification import design


def test_excel_source_binding_and_delivery_parameter_are_format_specific():
    spec, run, naming = excel_design()
    bound = execution_sources(run['input_snapshot']['source_config'], 4)
    assert bound == {'source_checksum': spec['excel_source']['content_checksum'], 'source_format': 'XLSX'}
    auth = {key: str(uuid4()) for key in ('run_id', 'specification_id', 'specification_approval_id')}
    auth.update({key: 'a' * 64 for key in ('specification_checksum', 'input_checksum', 'settings_checksum', 'hpl_checksum')})
    auth.update(bound)
    expected = expected_prepared_binding(auth)
    assert expected['source_format'] == 'XLSX'
    assert expected['approval_id'] == auth['specification_approval_id']
    assert 'specification_approval_id' not in expected
    compiled = compile_delivery_components(spec, run, naming)
    assert compiled['status'] == 'VALIDATED_NOT_APPROVED'
    assert 'SOURCE_XLSX=' in compiled['parameters'] and 'SOURCE_CSV' not in compiled['parameters']
    assert not compiled['release_ready'] and not compiled['execution_authorized']
    # No source content or private locator belongs in execution bindings/templates.
    for value in (bound, compiled['parameters']):
        assert 'upload_id' not in str(value) and 'sample_rows' not in str(value)


@pytest.mark.parametrize('change', ['missing_contract', 'different_sheet', 'changed_fields', 'csv', 'two_sources'])
def test_excel_binding_rejects_invalid_selection_or_contract(change):
    _, run, _ = excel_design()
    config = run['input_snapshot']['source_config']
    if change == 'missing_contract':
        config.pop('excel_input_contract_v1')
    elif change == 'different_sheet':
        config['excel_input_contract_v1']['worksheet'] = 'other'
    elif change == 'changed_fields':
        config['sources'][0]['fields'][0]['name'] = 'changed'
    elif change == 'csv':
        config['sources'][0]['type'] = 'CSV'
    else:
        config['sources'].append(deepcopy(config['sources'][0]))
    with pytest.raises(ValueError):
        execution_sources(config, 4)


@pytest.mark.parametrize('kind', [None, 'CSV', 'JSON'])
def test_unknown_explicit_format_cannot_enter_prepared_authority(kind):
    auth = dict.fromkeys(('run_id', 'specification_id', 'specification_approval_id',
        'specification_checksum', 'input_checksum', 'settings_checksum', 'hpl_checksum', 'source_checksum'), 'a' * 64)
    auth['source_format'] = kind
    with pytest.raises(ValueError, match='SOURCE_FORMAT_BINDING_INVALID'):
        expected_prepared_binding(auth)


def test_excel_is_not_an_implicit_upgrade_of_csv_specifications():
    _, run, _ = excel_design()
    for version in (1, 2, 3, True, '4'):
        with pytest.raises(ValueError, match='VERIFIED_UPLOADED_CSV_REQUIRED'):
            execution_sources(run['input_snapshot']['source_config'], version)
    _, csv_run, _ = design()
    with pytest.raises(ValueError):
        execution_sources(csv_run['input_snapshot']['source_config'], 4)
