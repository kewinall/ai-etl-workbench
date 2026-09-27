import pytest
from app.pilot_effort_coverage import coverage


def report(rows):
    return coverage([f'case-{i}' for i in range(20)],dict(completed=rows,
        excluded_nonhuman_sessions=2,abandoned_sessions=1,open_session='open'))


def test_partial_and_nonhuman_do_not_become_complete_cohort_time():
    rows=[dict(case_key='case-0',mode='WORKBENCH',actor='HUMAN_SELF_REPORTED',seconds=5),
          dict(case_key='case-0',mode='WORKBENCH',actor='HUMAN_SELF_REPORTED',seconds=3),
          dict(case_key='case-1',mode='WORKBENCH',actor='FUNCTIONAL_TEST',seconds=100)]
    result=report(rows);work=result['modes']['WORKBENCH']
    assert work['recorded_seconds']==8 and work['cases_with_recorded_intervals']==1
    assert work['cases_without_recorded_intervals']==19 and work['case_seconds']['case-1'] is None
    assert result['modes']['MANUAL_BASELINE']['recorded_seconds'] is None
    assert result['complete_case_count']==0 and not result['comparison_ready']
    assert result['improvement_rate'] is None and result['has_open_session']


def test_empty_is_not_zero_and_fixed_population_is_required():
    assert report([])['modes']['WORKBENCH']['recorded_seconds'] is None
    with pytest.raises(ValueError): coverage([], {})
    with pytest.raises(ValueError): report([dict(case_key='other',mode='WORKBENCH',actor='HUMAN_SELF_REPORTED',seconds=1)])
