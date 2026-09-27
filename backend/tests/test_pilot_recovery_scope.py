from copy import deepcopy
from hashlib import sha256

import pytest

from app.pilot_fixture_catalog import corpus
from app.pilot_recovery_scope import check_scope


CASES = [c for c in corpus() if c['definition']['scenario'] == 'EXECUTION_RECOVERY']


def current(case):
    return {'binding_checksum': 'bound',
            'run': {'write_started': False, 'parent_run_id': None, 'input_snapshot': {
                'source_config': {'sources': [
                    {'type': 'CSV', 'checksum': sha256(s['content'].encode()).hexdigest(),
                     'fields': [{'name': n, 'type': t} for n, t in s['fields']]}
                    for s in case['fixture']['sources']]}}},
            'specification': {'target_schema': 'ai_sample', 'target_table': 'pilot_' + 'a' * 32,
                              'write_mode': 'APPEND',
                              'output_columns': [c[0] for c in case['oracle']['columns']]}}


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['definition']['case_key'])
def test_frozen_cases_only(case):
    result = check_scope(current(case), 'bound', case['definition'])
    assert result['column'] == case['fixture']['initial_change']['column']


@pytest.mark.parametrize('mutation', ['written', 'unknown', 'child', 'schema', 'table',
                                    'mode', 'columns', 'source', 'fields', 'binding', 'definition'])
def test_scope_rejects_drift(mutation):
    case = deepcopy(CASES[0]); value = current(case)
    if mutation == 'written': value['run']['write_started'] = True
    if mutation == 'unknown': value['run'].pop('write_started')
    if mutation == 'child': value['run']['parent_run_id'] = 'parent'
    if mutation == 'schema': value['specification']['target_schema'] = 'business'
    if mutation == 'table': value['specification']['target_table'] = 'accepted_table'
    if mutation == 'mode': value['specification']['write_mode'] = 'UPSERT'
    if mutation == 'columns': value['specification']['output_columns'].reverse()
    if mutation == 'source': value['run']['input_snapshot']['source_config']['sources'][0]['checksum'] = 'other'
    if mutation == 'fields': value['run']['input_snapshot']['source_config']['sources'][0]['fields'] = []
    if mutation == 'binding': value['binding_checksum'] = 'old'
    if mutation == 'definition': case['definition']['oracle_checksum'] = '0' * 64
    with pytest.raises(ValueError):
        check_scope(value, 'bound', case['definition'])
