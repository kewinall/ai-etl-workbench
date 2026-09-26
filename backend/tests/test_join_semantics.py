from copy import deepcopy
import pytest
from app.etl_specification import EtlSpecificationV2, validate_specification
from app.hpl_compiler import compile_hpl
from app.join_semantics import validate_join_semantics
from app.specification_store import save
from test_etl_specification import design
from test_join_contract import snapshot, contract


def join_design():
    spec, run, naming = design()
    spec.pop('source_ref')
    spec.update(version=2, source_refs=['source.0', 'source.1'], joins=contract()['joins'])
    run['input_snapshot'] = snapshot()
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


def test_exact_join_match_does_not_pretend_compilation_is_complete():
    spec, run, naming = join_design()
    assert validate_join_semantics(spec['joins'], run['input_snapshot']) == []
    result = validate_specification(spec, run, naming)
    assert result['status'] == 'INVALID'
    assert {i['code'] for i in result['issues']} == {'SPEC_JOIN_COMPILATION_NOT_READY'}


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
