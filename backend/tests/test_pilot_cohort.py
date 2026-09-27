import pytest
from hashlib import sha256
from pydantic import ValidationError
from app.pilot_cohort import PilotCohortPlan, fingerprint


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
