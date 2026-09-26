from copy import deepcopy
import pytest
from app.join_contract import JoinContractV1, join_condition_issues, join_evidence
from app.requirement_contract import condition_issues
from app.run_api import ReviseRun, public_run
from app.sa_contract import build_sa_context


def contract(kind='LEFT'):
    return {'version': 1, 'joins': [{'id': 'join_customers', 'left_source': 'source.0',
        'right_source': 'source.1', 'join_type': kind,
        'keys': [{'left_column': '客戶編號', 'right_column': '客戶編號'}],
        'null_key_policy': 'NEVER_MATCH', 'duplicate_key_policy': 'EXPAND',
        'string_comparison': 'CASE_SENSITIVE_NO_TRIM'}]}


def snapshot():
    return {'requirement_text': '保留所有訂單，依客戶編號 LEFT JOIN 客戶',
        'target_config': {'schema': 'ai_sample', 'table': 'joined',
            'requirements_v1': {'write_mode': 'APPEND', 'date_scope': 'ALL'},
            'join_contract_v1': contract()},
        'source_config': {'sources': [
            {'type': 'CSV', 'has_actual_data': False, 'fields': [{'name': '客戶編號', 'type': 'BIGINT'}]},
            {'type': 'CSV', 'has_actual_data': False, 'fields': [{'name': '客戶編號', 'type': 'BIGINT'}]}]}}


@pytest.mark.parametrize('kind', ['INNER', 'LEFT'])
def test_explicit_join_contract_only_not_runtime_permission(kind):
    value = snapshot()
    value['target_config']['join_contract_v1'] = contract(kind)
    assert join_condition_issues(value) == []
    assert join_evidence(value)['contract_status'] == 'INPUT_ONLY_NOT_EXECUTION'
    assert condition_issues(value) == []  # Intent validation is not execution consent.


@pytest.mark.parametrize('field', ['join_type', 'keys', 'null_key_policy', 'duplicate_key_policy', 'string_comparison'])
def test_semantics_have_no_inferred_defaults(field):
    value = contract()
    del value['joins'][0][field]
    with pytest.raises(ValueError):
        JoinContractV1.model_validate(value)


@pytest.mark.parametrize('field,value', [('join_type', 'RIGHT'), ('join_type', 'FULL'),
    ('left_source', 'source.1'), ('right_source', 'source.0'),
    ('null_key_policy', 'MATCH_NULLS'), ('duplicate_key_policy', 'FIRST'),
    ('string_comparison', 'IGNORE_CASE'), ('sql', 'SELECT sensitive'), ('keys', [])])
def test_unsupported_choices_are_not_downgraded(field, value):
    raw = contract()
    raw['joins'][0][field] = value
    with pytest.raises(ValueError):
        JoinContractV1.model_validate(raw)


@pytest.mark.parametrize('version', [True, '1', 1.0, 2])
def test_version_is_exact_integer(version):
    with pytest.raises(ValueError):
        JoinContractV1.model_validate({**contract(), 'version': version})


def test_source_qualified_keys_do_not_resolve_from_other_side():
    value = snapshot()
    value['source_config']['sources'][1]['fields'][0]['name'] = '另一個欄位'
    issues = join_condition_issues(value)
    assert len(issues) == 1
    assert issues[0]['field_path'] == 'join_contract_v1.joins.0.keys.0.right_column'


def test_missing_and_duplicate_metadata_are_not_accepted():
    value = snapshot()
    value['source_config']['sources'][0]['fields'] *= 2
    assert join_condition_issues(value)[0]['issue_type'] == 'CONFLICT'
    value = snapshot()
    value['target_config']['join_contract_v1']['joins'][0]['keys'] *= 2
    assert len(join_condition_issues(value)) == 2


@pytest.mark.parametrize('count', [0, 1, 3])
def test_no_source_silently_ignored(count):
    value = snapshot()
    value['source_config']['sources'] = [deepcopy(value['source_config']['sources'][0]) for _ in range(count)]
    assert join_condition_issues(value)[0]['issue_type'] == 'UNSUPPORTED'


def test_absent_join_is_missing_for_multiple_sources_but_unchanged_for_single():
    value = snapshot()
    del value['target_config']['join_contract_v1']
    assert join_condition_issues(value)[0]['issue_type'] == 'MISSING'
    value['source_config']['sources'].pop()
    assert join_condition_issues(value) == [] and join_evidence(value) is None


def test_context_records_join_semantics_not_paths_and_checksum_changes():
    value = snapshot()
    value['target_config']['host'] = 'private-host'
    value['source_config']['sources'][0]['path'] = '/private/source.csv'
    run = {'run_id': 'test', 'input_checksum': 'a'*64, 'settings_snapshot': {'checksum': 'b'*64}, 'input_snapshot': value}
    before = build_sa_context(run)
    assert 'private' not in str(before)
    evidence = next(item for item in before['evidence'] if item['id'] == 'join.conditions')
    assert evidence['value']['joins'][0]['join_type'] == 'LEFT'
    value['target_config']['join_contract_v1']['joins'][0]['join_type'] = 'INNER'
    assert before['context_checksum'] != build_sa_context(run)['context_checksum']
    value['target_config']['join_contract_v1']['sql'] = 'private secret'
    assert join_evidence(value) == {'contract_status': 'INVALID'}
    assert 'private' not in str(public_run(run))


def test_revision_accepts_only_typed_join_contract():
    body = dict(request_key='join-child-01', input_checksum='a'*64, requirement_text='LEFT join',
        target_schema='ai_sample', target_table='joined', join_contract_v1=contract())
    assert ReviseRun.model_validate(body).join_contract_v1.joins[0].join_type == 'LEFT'
    body['join_contract_v1']['password'] = 'private'
    with pytest.raises(ValueError):
        ReviseRun.model_validate(body)
