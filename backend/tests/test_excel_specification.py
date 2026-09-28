from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from uuid import uuid4
from xml.etree.ElementTree import fromstring
import pytest
from openpyxl import Workbook
from app.excel_profile import selected_profile
from app.excel_contract_binding import validated_excel_contract, excel_contract_issues
from app.etl_specification import validate_specification
from app.hpl_compiler import compile_hpl
from app.hwf_compiler import compile_hwf
from app.platform_harness import checksum
from app.sa_contract import build_sa_context, validate_sa_review
from app.developer_contract import build_context, validate_proposal
from test_etl_specification import design, codes
from test_excel_input_contract import policy


def excel_design(*, rows=None, capture=None):
    spec, run, naming = design()
    book = Workbook()
    sheet = book.active
    sheet.title = '明細'
    sheet.append(['說明'])
    sheet.append(['類別', '金額'])
    for row in rows if rows is not None else [['A', '150.25']]:
        sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    book.close()
    content = stream.getvalue()
    if capture is not None:
        capture.append(content)
    profile = selected_profile(str(uuid4()), sha256(content).hexdigest(), len(content), '明細', 2, content=content)
    selection = profile['excel_selection_v1']
    source = {'type': 'EXCEL', 'has_actual_data': True, 'upload_id': selection['upload_id'],
              'checksum': selection['content_checksum'], 'size': len(content), **profile}
    config = {'sources': [source], 'excel_input_contract_v1': policy()}
    run['input_snapshot'].update(source_type='EXCEL', source_config=config)
    naming['contract_json']['columns'][1]['vertica_type'] = 'NUMERIC(18,4)'
    naming['contract_json']['columns'][2]['vertica_type'] = 'NUMERIC(24,4)'
    naming['checksum'] = checksum(naming['contract_json']['columns'])
    spec['naming']['checksum'] = naming['checksum']
    spec.update(version=4, excel_source=validated_excel_contract(config)['reference'])
    return spec, run, naming


def test_excel_compiles_bound_native_reader_and_preserves_input():
    spec, run, naming = excel_design()
    before = deepcopy((spec, run, naming))
    result = compile_hpl(spec, run, naming)
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    assert not result['execution_authorized']
    assert result == compile_hpl(spec, run, naming)
    assert (spec, run, naming) == before
    root = fromstring(result['hpl'])
    assert root.findtext('info/parameters/parameter/name') == 'SOURCE_XLSX'
    source = root.find("transform[name='source']")
    assert source.findtext('type') == 'ExcelInput'
    assert source.findtext('file/name') == '${SOURCE_XLSX}'
    assert source.findtext('sheets/sheet/startrow') == '1'
    assert 'SOURCE_CSV' not in result['hpl']
    assert [s['component'] for s in result['plan']['stages']] == ['ExcelInput', 'FilterRows', 'SortRows', 'GroupBy', 'SelectValues', 'TableOutput']


@pytest.mark.parametrize('key', ['content_checksum', 'profile_checksum', 'contract_checksum'])
def test_model_cannot_change_excel_binding(key):
    spec, run, naming = excel_design()
    spec['excel_source'][key] = 'f' * 64
    assert 'SPEC_EXCEL_BINDING_MISMATCH' in codes(validate_specification(spec, run, naming))


def test_policy_change_invalidates_prior_spec():
    spec, run, naming = excel_design()
    run['input_snapshot']['source_config']['excel_input_contract_v1']['blank_rows'] = 'PRESERVE'
    assert 'SPEC_EXCEL_BINDING_MISMATCH' in codes(validate_specification(spec, run, naming))


@pytest.mark.parametrize('mutation', ['missing', 'sheet', 'fields', 'checksum', 'csv'])
def test_gate_rejects_missing_conflicting_or_tampered_binding(mutation):
    spec, run, naming = excel_design()
    config = run['input_snapshot']['source_config']
    if mutation == 'missing':
        config.pop('excel_input_contract_v1')
    elif mutation == 'sheet':
        config['sources'][0]['worksheet'] = 'different'
    elif mutation == 'fields':
        config['sources'][0]['fields'][0]['name'] = 'changed'
    elif mutation == 'checksum':
        config['sources'][0]['checksum'] = 'f' * 64
    else:
        config['csv_input_contract_v1'] = {}
    assert excel_contract_issues(run['input_snapshot'])
    assert 'SPEC_GATE_BLOCKED' in codes(validate_specification(spec, run, naming))


def test_old_spec_cannot_execute_excel_and_excel_cannot_use_csv():
    spec, run, naming = excel_design()
    spec.pop('excel_source')
    spec['version'] = 1
    assert 'SPEC_SOURCE_UNSUPPORTED' in codes(validate_specification(spec, run, naming))
    spec, run, naming = excel_design()
    run['input_snapshot']['source_config']['sources'][0]['type'] = 'CSV'
    assert 'SPEC_SOURCE_UNSUPPORTED' in codes(validate_specification(spec, run, naming))


def test_sa_and_developer_require_excel_evidence_and_no_upload_metadata():
    spec, run, naming = excel_design()
    sa = build_sa_context(run)
    assert sa['version'] == 5
    assert sa['deterministic_gate']['status'] == 'CHECKED'
    assert 'upload_id' not in str(sa) and 'sample_rows' not in str(sa)
    review = {'version': 1, 'run_id': str(run['run_id']), 'input_checksum': run['input_checksum'],
              'context_checksum': sa['context_checksum'], 'status': 'READY_FOR_REVIEW',
              'summary': 'synthetic review', 'evidence_ids': ['requirement'], 'issues': []}
    with pytest.raises(ValueError, match='SA_EXCEL_INPUT_EVIDENCE_REQUIRED'):
        validate_sa_review(review, sa)
    review['evidence_ids'].append('source.0.excel_input')
    validate_sa_review(review, sa)
    context = build_context(run, naming, {'approval_id': uuid4(), 'binding_checksum': 'c' * 64}, review)
    assert context['version'] == 4
    from app.developer_gateway import developer_material
    material = developer_material(context)
    assert material['prompt_version'] == 7
    assert 'EtlSpecificationV4' in material['prompt']
    assert 'EtlSpecificationV1' not in material['prompt']
    assert material['schema']['properties']['version']['const'] == 4
    payload = {'version': 4, 'context_checksum': context['context_checksum'], 'summary': 'synthetic proposal',
               'evidence_ids': ['requirement'], 'specification': spec}
    captured = {'context': context, 'run': run, 'naming': naming}
    with pytest.raises(ValueError, match='DEVELOPER_EXCEL_INPUT_EVIDENCE_REQUIRED'):
        validate_proposal(payload, captured)
    payload['evidence_ids'].append('source.0.excel_input')
    assert validate_proposal(payload, captured)['status'] == 'VALIDATED_NOT_APPROVED'


def test_invalid_version_list_is_schema_error():
    spec, run, naming = excel_design()
    spec['version'] = []
    assert codes(validate_specification(spec, run, naming)) == {'SPEC_SCHEMA_INVALID'}


def test_excel_workflow_parameter_matches_pipeline():
    compiled = compile_hwf(*excel_design())
    assert compiled['status'] == 'VALIDATED_NOT_APPROVED'
    workflow = fromstring(compiled['hwf'])
    assert workflow.findtext('parameters/parameter/name') == 'SOURCE_XLSX'
    assert 'SOURCE_CSV' not in compiled['hwf']
    assert workflow.findtext("actions/action[type='PIPELINE']/parameters/pass_all_parameters") == 'Y'
    assert not compiled['execution_authorized']
