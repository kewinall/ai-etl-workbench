import pytest
from app.requirement_contract import condition_issues, RequirementConditionsV1


def snapshot(values, text='載入資料'):
    return {'requirement_text': text, 'target_config': {'requirements_v1': values}, 'source_config': {'sources': [{'fields': [{'name': 'id'}, {'name': 'created_date'}]}]}}


def test_missing_business_choices_are_not_inferred():
    issues = condition_issues(snapshot({}, '最近客戶'))
    assert {(x['issue_type'], x['field_path']) for x in issues} == {('MISSING', 'requirements_v1.write_mode'), ('AMBIGUOUS', 'requirements_v1.date_scope')}


def test_explicit_all_append_passes_only_condition_checks():
    assert condition_issues(snapshot({'write_mode': 'APPEND', 'date_scope': 'ALL'})) == []


@pytest.mark.parametrize('start,end', [('2026-02-30', '2026-03-01'), ('2026-03-01', '2026-03-01'), ('2026-03-02', '2026-03-01'), ('20260301', '2026-03-02')])
def test_invalid_or_reversed_dates_block(start, end):
    assert condition_issues(snapshot(dict(write_mode='APPEND', date_scope='RANGE', date_column='created_date', start_date=start, end_date_exclusive=end)))


def test_exact_range_resolves_recent_ambiguity():
    assert condition_issues(snapshot(dict(write_mode='APPEND', date_scope='RANGE', date_column='created_date', start_date='2026-03-01', end_date_exclusive='2026-04-01'), '最近客戶')) == []


def test_recent_all_is_conflict():
    assert condition_issues(snapshot(dict(write_mode='APPEND', date_scope='ALL'), '最近客戶'))[0]['issue_type'] == 'CONFLICT'


@pytest.mark.parametrize('keys', [[], ['unknown'], ['id', 'id']])
def test_upsert_requires_unique_existing_keys(keys):
    assert condition_issues(snapshot(dict(write_mode='UPSERT', date_scope='ALL', key_columns=keys)))


def test_join_blocks_until_supported():
    value = snapshot(dict(write_mode='APPEND', date_scope='ALL'))
    value['source_config']['sources'] *= 2
    assert condition_issues(value)[0]['issue_type'] == 'UNSUPPORTED'


def test_contract_forbids_arbitrary_tool_or_sql_fields():
    with pytest.raises(ValueError):
        RequirementConditionsV1.model_validate({'sql': 'arbitrary'})
