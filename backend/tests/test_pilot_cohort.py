import pytest
from hashlib import sha256
from pydantic import ValidationError
from app.pilot_cohort import PilotCohortPlan, fingerprint
from app.pilot_cohort import annotate_order_scope


def test_order_scope_keeps_changed_success_out_of_frozen_acceptance():
    runs = [{'state': 'FAILED', 'source_order_contract': None},
            {'state': 'RELEASE_READY', 'source_order_contract': {'ordinal_column': 'source_position'}}]
    annotate_order_scope(runs, True)
    assert len(runs) == 2 and runs[0]['state'] == 'FAILED'
    assert runs[0]['source_order_scope'] == 'UNCHANGED_NOT_ACCEPTANCE_PROOF'
    assert runs[1]['source_order_scope'] == 'CHANGED_REQUIRES_PROTOCOL_REVIEW'
    assert all(not r['cohort_acceptance_verified'] for r in runs)
    assert all('source_order_contract' not in r for r in runs)


@pytest.mark.parametrize('verified', [True, False])
def test_order_scope_does_not_call_initial_order_contract_an_extension(verified):
    runs = [{'source_order_contract': {'ordinal_column': 'position'}},
            {'source_order_contract': {'ordinal_column': 'position'}}]
    annotate_order_scope(runs, verified)
    expected = 'UNCHANGED_NOT_ACCEPTANCE_PROOF' if verified else 'UNVERIFIED_ATTEMPT_ORDER'
    assert all(r['source_order_scope'] == expected for r in runs)


def test_removing_order_contract_also_requires_review():
    runs = [{'source_order_contract': {'ordinal_column': 'position'}}, {'source_order_contract': None}]
    annotate_order_scope(runs, True)
    assert runs[1]['source_order_scope'] == 'CHANGED_REQUIRES_PROTOCOL_REVIEW'
    annotate_order_scope([], False)


def plan_payload():
    scenarios = ['SUCCESS', 'REQUIREMENT_GAP', 'SEMANTIC_DEFECT', 'EXECUTION_RECOVERY']
    return {'name': 'Synthetic protocol', 'cases': [
        {'case_key': f'case-{n:02}', 'title': f'Case {n}', 'scenario': scenarios[n % 4],
         'acceptance': 'Explicit predetermined acceptance criteria',
         'fixture_reference': f'fixture-{n}', 'oracle_reference': f'oracle-{n}',
         'fixture_checksum': sha256(f'fixture-{n}'.encode()).hexdigest(),
         'oracle_checksum': sha256(f'oracle-{n}'.encode()).hexdigest()}
        for n in range(20)]}


def test_fingerprint_stable_but_changes_with_acceptance():
    payload = plan_payload()
    first = fingerprint(PilotCohortPlan(**payload))
    assert first == fingerprint(PilotCohortPlan(**payload))
    payload['cases'][0]['acceptance'] += ' changed'
    assert first != fingerprint(PilotCohortPlan(**payload))


@pytest.mark.parametrize('fault', ['short', 'duplicate', 'scenario', 'success_claim', 'blank', 'checksum'])
def test_rejects_invalid_population_or_unmeasured_claims(fault):
    payload = plan_payload()
    if fault == 'short': payload['cases'].pop()
    if fault == 'duplicate': payload['cases'][1]['case_key'] = payload['cases'][0]['case_key']
    if fault == 'scenario':
        for row in payload['cases']: row['scenario'] = 'SUCCESS'
    if fault == 'success_claim': payload['cases'][0]['passed'] = True
    if fault == 'blank': payload['cases'][0]['fixture_reference'] = '  '
    if fault == 'checksum': payload['cases'][0]['oracle_checksum'] = 'unverified'
    with pytest.raises(ValidationError): PilotCohortPlan(**payload)
