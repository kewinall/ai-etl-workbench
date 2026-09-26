from copy import deepcopy
import pytest
from app.etl_specification import EtlSpecificationV2, validate_specification
from app.hpl_compiler import compile_hpl
from app.join_semantics import validate_join_semantics
from app.specification_store import save
from test_etl_specification import design
from test_join_contract import snapshot, contract
from test_multi_csv import contracts
from app.platform_harness import checksum


def join_design():
    spec, run, naming = design()
    spec.pop('source_ref')
    spec.update(version=2, source_refs=['source.0', 'source.1'], joins=contract()['joins'])
    run['input_snapshot'] = snapshot()
    for source in run['input_snapshot']['source_config']['sources']:
        source['fields'] = [{'name': '客戶編號', 'type': 'VARCHAR(32)'}, {'name': '名稱', 'type': 'VARCHAR(32)'}]
    run['input_snapshot']['source_config']['csv_input_contracts_v1'] = contracts()
    columns = [{'source_name': f'source.{index}.{original}', 'english_name': f'{side}_{suffix}', 'vertica_type': 'VARCHAR(32)'}
               for index,side in enumerate(('left', 'right')) for original,suffix in [('客戶編號','key'), ('名稱','value')]]
    naming['contract_json']['columns'] = columns
    naming['checksum'] = checksum(columns)
    spec['naming']['checksum'] = naming['checksum']
    spec.update(target_table='joined', filters=[], aggregation=None,
                output_columns=['left_key','left_value','right_key','right_value'])
    return spec, run, naming


def test_inner_left_mismatch_pinpoints_contract_field_and_node_before_compilation():
    spec, run, naming = join_design()
    spec['joins'][0]['join_type'] = 'INNER'
    before = deepcopy((spec, run, naming))
    result = compile_hpl(spec, run, naming)
    assert result['status'] == 'INVALID' and not result['execution_authorized']
    mismatch = next(i for i in result['issues'] if i['code'] == 'SPEC_JOIN_SEMANTICS_MISMATCH')
    assert mismatch['node_id'] == 'join_customers'
    assert mismatch['field_path'] == 'joins.0.join_type'
    assert mismatch['requirement_path'] == 'join_contract_v1.joins.0.join_type'
    assert (mismatch['expected'], mismatch['actual']) == ('LEFT', 'INNER')
    assert not any(key in result for key in ('hpl', 'plan', 'specification_checksum'))
    # Existing save path rejects the design without opening or writing a DB.
    assert save(None, None, 'task', 'run', result) == result
    assert (spec, run, naming) == before


@pytest.mark.parametrize('field,value', [('id', 'join_changed'),
    ('keys', [{'left_column': 'wrong', 'right_column': '客戶編號'}])])
def test_other_semantic_changes_cannot_hide_behind_valid_join_type(field, value):
    proposed = contract()['joins']
    proposed[0][field] = value
    issues = validate_join_semantics(proposed, snapshot())
    assert len(issues) == 1 and issues[0]['field_path'] == 'joins.0.' + field
    assert issues[0]['expected'] != issues[0]['actual']


def test_missing_or_invalid_operator_intent_is_not_replaced_by_proposal():
    value = snapshot()
    del value['target_config']['join_contract_v1']
    assert validate_join_semantics(contract()['joins'], value)[0]['code'] == 'SPEC_JOIN_REQUIREMENT_INVALID'


def test_exact_join_match_compiles_but_does_not_grant_execution():
    spec, run, naming = join_design()
    assert validate_join_semantics(spec['joins'], run['input_snapshot']) == []
    result = validate_specification(spec, run, naming)
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    assert result['execution_authorized'] is False
    compiled = compile_hpl(spec, run, naming)
    assert compiled['compiler_status'] == 'HPL_CANDIDATE_NOT_EXECUTABLE'
    assert compiled['plan']['version'] == 2
    assert [s['component'] for s in compiled['plan']['stages']].count('CSVInput') == 2
    assert 'SOURCE_CSV_0' in compiled['hpl'] and 'SOURCE_CSV_1' in compiled['hpl']


def test_runtime_authorization_requires_verified_multisource_before_oracle_or_writes(monkeypatch):
    from app import execution_authorization
    _, run, _ = join_design()
    monkeypatch.setattr(execution_authorization, 'load_approved_candidate', lambda *a,**k: {
        'run':run,'compiled':{'specification':{'version':2}}})
    with pytest.raises(ValueError, match='VERIFIED_UPLOADED_CSV_REQUIRED'):
        execution_authorization.offer(None, None, 'task', 'run', 'spec')


@pytest.mark.parametrize('change,code', [('key_type','SPEC_JOIN_KEY_TYPE_MISMATCH'),
    ('unqualified','SPEC_JOIN_KEY_NAMING_MISSING'), ('reserved','SPEC_JOIN_NODE_ID_RESERVED')])
def test_join_compiler_rejects_unsafe_mapping(change, code):
    spec, run, naming = join_design()
    if change == 'key_type':
        naming['contract_json']['columns'][2]['vertica_type'] = 'BIGINT'
    elif change == 'unqualified':
        naming['contract_json']['columns'][2]['source_name'] = '客戶編號'
    else:
        spec['joins'][0]['id'] = 'target'
        run['input_snapshot']['target_config']['join_contract_v1']['joins'][0]['id'] = 'target'
    naming['checksum'] = checksum(naming['contract_json']['columns'])
    spec['naming']['checksum'] = naming['checksum']
    assert code in {i['code'] for i in compile_hpl(spec,run,naming)['issues']}


@pytest.mark.parametrize('change', [dict(version=True), dict(version=2.0),
    dict(source_refs=['source.0', 'source.0']), dict(source_refs=['source.1', 'source.0']),
    dict(source_refs=['source.0']), dict(sql='private arbitrary SQL')])
def test_v2_schema_does_not_coerce_or_drop_sources(change):
    spec, _, _ = join_design()
    with pytest.raises(ValueError):
        EtlSpecificationV2.model_validate({**spec, **change})


def test_arbitrary_join_fields_never_appear_in_evidence():
    proposed = contract()['joins']
    proposed[0]['sql'] = 'private arbitrary SQL'
    result = validate_join_semantics(proposed, snapshot())
    assert result[0]['code'] == 'SPEC_JOIN_SCHEMA_INVALID'
    assert 'private' not in str(result)


def test_stale_run_cannot_be_hidden_by_matching_join_semantics():
    spec, run, naming = join_design()
    spec['input_checksum'] = 'c'*64
    result = validate_specification(spec, run, naming)
    assert 'SPEC_VERSION_MISMATCH' in {i['code'] for i in result['issues']}


def test_missing_source_metadata_is_not_silently_dropped():
    spec, run, naming = join_design()
    run['input_snapshot']['source_config']['sources'][1]['fields'].append({'type':'VARCHAR(32)'})
    result = validate_specification(spec,run,naming)
    assert 'SPEC_SOURCE_FIELDS_INVALID' in {i['code'] for i in result['issues']}


@pytest.mark.parametrize('change,code', [('unapproved','SPEC_INPUT_NOT_APPROVED'),
    ('stale_naming','SPEC_NAMING_VERSION_MISMATCH'), ('extra_source','SPEC_SOURCE_UNSUPPORTED'),
    ('target','SPEC_TARGET_MISMATCH'), ('output','SPEC_OUTPUT_COLUMNS_INVALID')])
def test_v2_keeps_common_version_naming_and_output_guards(change, code):
    spec,run,naming = join_design()
    if change == 'unapproved': run['approval'] = None
    elif change == 'stale_naming': naming['version'] += 1
    elif change == 'extra_source': run['input_snapshot']['source_config']['sources'].append(deepcopy(run['input_snapshot']['source_config']['sources'][0]))
    elif change == 'target': spec['target_table'] = 'unapproved'
    else: spec['output_columns'] = ['unknown']
    result = compile_hpl(spec,run,naming)
    assert code in {i['code'] for i in result['issues']}
    assert 'hpl' not in result and result['execution_authorized'] is False
