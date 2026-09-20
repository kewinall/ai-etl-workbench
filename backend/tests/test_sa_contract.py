from copy import deepcopy
import pytest
from app.sa_contract import build_sa_context, validate_sa_review


def run():
    return dict(run_id='run-1', input_checksum='a'*64, settings_snapshot={'checksum': 'b'*64, 'password': 'private-secret'}, input_snapshot={
        'requirement_text': 'Load confirmed data', 'source_config': {'sources': [{'fields': [{'name': 'id', 'type': 'BIGINT', 'sample': 'private-data'}], 'file_path': '/private/input.csv'}]},
        'target_config': {'schema': 'ai_sample', 'table': 'test', 'host': 'private-host', 'requirements_v1': {'write_mode': 'APPEND', 'date_scope': 'ALL'}}})


def response(context):
    return dict(version=1, run_id=context['run_id'], input_checksum=context['input_checksum'], context_checksum=context['context_checksum'], status='READY_FOR_REVIEW', summary='Review the specification', evidence_ids=['requirement', 'conditions'], issues=[])


def test_minimum_context_is_deterministic_and_excludes_connection_and_samples():
    context = build_sa_context(run())
    assert context == build_sa_context(run())
    assert 'private' not in str(context)
    assert validate_sa_review(response(context), context)['status'] == 'READY_FOR_REVIEW'


@pytest.mark.parametrize('field,value', [('run_id', 'other'), ('input_checksum', 'c'*64), ('context_checksum', 'd'*64)])
def test_wrong_version_is_rejected(field, value):
    context = build_sa_context(run())
    payload = response(context)
    payload[field] = value
    with pytest.raises(ValueError, match='SA_VERSION_MISMATCH'):
        validate_sa_review(payload, context)


def test_fake_evidence_rejected():
    context = build_sa_context(run())
    payload = response(context)
    payload['evidence_ids'].append('invented-source')
    with pytest.raises(ValueError, match='SA_UNKNOWN_EVIDENCE'):
        validate_sa_review(payload, context)


def test_cannot_override_deterministic_failure():
    value = run()
    value['input_snapshot']['target_config']['requirements_v1'] = {}
    context = build_sa_context(value)
    with pytest.raises(ValueError, match='SA_CANNOT_OVERRIDE_GATE'):
        validate_sa_review(response(context), context)


def test_missing_input_requires_issue_evidence():
    context = build_sa_context(run())
    payload = {**response(context), 'status': 'NEEDS_INPUT'}
    with pytest.raises(ValueError, match='SA_MISSING_ISSUE_DETAILS'):
        validate_sa_review(payload, context)
    payload['issues'] = [dict(issue_type='AMBIGUOUS', message='Please clarify', evidence_ids=['requirement'])]
    assert validate_sa_review(payload, context)['status'] == 'NEEDS_INPUT'


def test_no_sql_or_execution_fields_accepted():
    context = build_sa_context(run())
    with pytest.raises(ValueError):
        validate_sa_review({**response(context), 'sql': 'arbitrary'}, context)


def test_evidence_changes_change_context_checksum_without_mutating_input():
    value = run()
    old = deepcopy(value)
    before = build_sa_context(value)
    assert value == old
    value['input_snapshot']['source_config']['sources'][0]['fields'][0]['type'] = 'DATE'
    assert before['context_checksum'] != build_sa_context(value)['context_checksum']
