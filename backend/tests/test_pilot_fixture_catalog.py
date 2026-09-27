import csv
import io
from collections import Counter, defaultdict
from hashlib import sha256
import json
from zipfile import ZipFile
import pytest
from app.pilot_fixture_catalog import corpus, template, canonical_bytes, bundle


def parse(source):
    return list(csv.DictReader(io.StringIO(source['content'])))


def test_fixed_twenty_with_balanced_scenarios_and_reproducible_hashes():
    cases = corpus()
    assert len(cases) == 20 and len({c['definition']['case_key'] for c in cases}) == 20
    assert set(Counter(c['definition']['scenario'] for c in cases).values()) == {5}
    assert len(template().cases) == 20
    for case in cases:
        for part in ('fixture','oracle'):
            assert sha256(canonical_bytes(case[part])).hexdigest() == case['definition'][part+'_checksum']
    assert canonical_bytes(cases) == canonical_bytes(corpus())
    cases[0]['oracle']['rows'].clear()
    assert corpus()[0]['oracle']['rows']  # No shared mutable answer objects.


@pytest.mark.parametrize('base_index', range(5))
def test_literal_corrected_answers_against_independent_reference_calculation(base_index):
    case = corpus()[base_index]
    rows = parse(case['fixture']['sources'][0])
    if base_index == 0:
        groups = defaultdict(list)
        for row in rows:
            if int(row['amount']) >= 10: groups[row['category']].append(int(row['amount']))
        actual = [[key,sum(values),len(values)] for key,values in groups.items()]
    elif base_index == 1:
        actual = [[int(row['record_id'])] for row in rows if '2026-01-01' <= row['event_date'] < '2026-02-01']
    elif base_index == 2:
        right = parse(case['fixture']['sources'][1])
        actual = []
        for row in rows:
            matches = [item for item in right if item['customer_id'] == row['customer_id']]
            actual.extend([[int(row['customer_id']),item['order_code']] for item in matches] or [[int(row['customer_id']),None]])
    elif base_index == 3:
        actual = [[int(row['record_id'])] for row in rows if int(row['amount']) > 100]
    else:
        actual = [[key,value] for key,value in Counter(row['category'] or None for row in rows).items()]
    assert Counter(map(tuple,actual)) == Counter(map(tuple,case['oracle']['rows']))
    for variant in corpus()[base_index::5]:
        if variant['definition']['case_key'] == 'recovery-full-projection': continue
        assert variant['oracle'] == case['oracle']


def test_faults_are_descriptions_not_executable_sql_or_execution_claims():
    for case in corpus():
        assert case['fixture']['fault_scope'] == 'SYNTHETIC_MANAGED_TARGET_ONLY'
        assert 'passed' not in case and 'run_id' not in case
        if case['definition']['scenario'] == 'SUCCESS': assert case['fixture']['initial_change'] is None
        else: assert case['fixture']['initial_change'] is not None


def test_recovery_has_rows_and_zip_matches_registered_hashes():
    assert bundle() == bundle()
    cases = corpus()
    assert all(case['oracle']['rows'] for case in cases if case['definition']['scenario'] == 'EXECUTION_RECOVERY')
    projection = next(case for case in cases if case['definition']['case_key']=='recovery-full-projection')
    assert projection['oracle']['rows'] == [[int(row['record_id'])] for row in parse(projection['fixture']['sources'][0])]
    with ZipFile(io.BytesIO(bundle())) as archive:
        plan = json.loads(archive.read('plan.json'))
        assert len(plan['cases']) == 20
        for case in plan['cases']:
            for part in ('fixture','oracle'):
                assert sha256(archive.read(case[part+'_reference'])).hexdigest() == case[part+'_checksum']
        assert all(not name.startswith('/') and '..' not in name.split('/') for name in archive.namelist())
