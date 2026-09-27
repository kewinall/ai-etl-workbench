from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

import pytest

from app.pilot_case_preparation import build_task_payload, registered_case
from app.pilot_fixture_catalog import corpus
from app.requirement_contract import condition_issues
from app.csv_contract import csv_contract_issues


def receipts(case):
    return [{'source_type': 'CSV', 'upload_id': str(uuid4()),
             'original_name': source['filename'], 'path': '/test-only/source.csv',
             'checksum': sha256(source['content'].encode()).hexdigest(),
             'size': len(source['content'].encode()),
             'fields': [{'name': name, 'type': 'INFERRED_TYPE'} for name, _ in source['fields']]}
            for source in case['fixture']['sources']]


@pytest.mark.parametrize('case', corpus(), ids=lambda c: c['definition']['case_key'])
def test_all_twenty_prepare_declared_types_and_preserve_only_registered_gaps(case):
    uploads = receipts(case)
    original = deepcopy(uploads)
    args = (uuid4(), uuid4(), case['definition'], uploads)
    result = build_task_payload(*args)
    assert result == build_task_payload(*args)
    assert uploads == original
    assert result['target_schema'] == 'ai_sample'
    assert result['error_test_config'] == {}  # Preparation never injects or executes a fault.
    assert 'oracle' not in result and 'rows' not in result['target_config']
    for source, expected in zip(result['source_config']['sources'], case['fixture']['sources']):
        assert source['fields'] == [{'name': n, 'type': t} for n, t in expected['fields']]
    snapshot = {**result, 'requirement_text': result['requirement']}
    issues = condition_issues(snapshot) + csv_contract_issues(snapshot)
    assert bool(issues) == (case['definition']['scenario'] == 'REQUIREMENT_GAP')
    if issues:
        assert len(issues) == 1


@pytest.mark.parametrize('field', ['fixture_checksum', 'oracle_checksum', 'acceptance', 'fixture_reference', 'scenario'])
def test_rejects_changed_registration_even_if_case_key_matches(field):
    definition = deepcopy(corpus()[0]['definition'])
    definition[field] = 'changed'
    with pytest.raises(ValueError, match='REGISTERED_DEFINITION_MISMATCH'):
        registered_case(definition)


@pytest.mark.parametrize('field,value', [('checksum', '0'*64), ('size', True), ('size', 1),
                                      ('source_type', 'JSON'), ('original_name', 'other.csv'),
                                      ('fields', []), ('upload_id', 'bad'), ('path', '')])
def test_rejects_unmatched_upload_receipt(field, value):
    case = corpus()[0]
    uploads = receipts(case)
    uploads[0][field] = value
    with pytest.raises(ValueError, match='PILOT_UPLOAD_'):
        build_task_payload(uuid4(), uuid4(), case['definition'], uploads)


def test_exact_upload_coverage_order_and_project_cohort_identity():
    case = corpus()[2]
    uploads = receipts(case)
    project, cohort = uuid4(), uuid4()
    for invalid in ([], uploads[:1], uploads + uploads, list(reversed(uploads))):
        with pytest.raises(ValueError, match='PILOT_UPLOAD_'):
            build_task_payload(project, cohort, case['definition'], invalid)
    first = build_task_payload(project, cohort, case['definition'], uploads)
    for other_project, other_cohort in ((uuid4(), cohort), (project, uuid4())):
        other = build_task_payload(other_project, other_cohort, case['definition'], uploads)
        assert other['creation_request_key'] != first['creation_request_key']
        assert other['target_table'] != first['target_table']
