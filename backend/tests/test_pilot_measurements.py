from copy import deepcopy
from unittest.mock import Mock
import pytest
from app.pilot_measurements import measure,elapsed_seconds


def cohort():
    return {'cohort_id':'cohort','name':'Frozen','plan_checksum':'a'*64,'cases':[
        {'case_key':f'case-{i}','definition':{'title':f'Case {i}','scenario':'SUCCESS'},
         'task_id':f'task-{i}','attempt_order_verified':True,'runs':[
             {'run_id':f'run-{i}','parent_run_id':None,'created_at':'2026-09-27T00:00:00+00:00'}]}
        for i in range(20)]}


def ready(*_):
    return {'status':'RELEASE_READY','release_ready':True,'release':{
        'release_id':'release','checksum':'b'*64,'approved_at':'2026-09-27T00:01:00+00:00'}}


def test_full_denominator_and_unmeasured_values_preserved():
    data=cohort();original=deepcopy(data)
    result=measure(data,ready)
    assert result['denominator']==20 and result['release_ready_count']==20
    assert result['attempt_count']==20 and result['revision_count']==0
    assert result['comparison_ready'] is False
    for key in ('first_pass_rate','human_active_seconds','human_baseline_seconds','improvement_rate','cost'):
        assert result[key] is None
    assert all(r['elapsed_to_delivery_seconds']==60 and not r['scenario_acceptance_verified'] for r in result['cases'])
    assert data==original


def test_failures_unbound_unstarted_and_unknown_stay_in_denominator():
    data=cohort();data['cases'][0].update(task_id=None,runs=[])
    data['cases'][1]['runs']=[];data['cases'][2]['attempt_order_verified']=False
    def inspect(task,run):
        if task=='task-3':raise RuntimeError('private credential must not escape')
        if task=='task-4':return {'status':'PREREQUISITES_REQUIRED','release_ready':False}
        return ready()
    result=measure(data,inspect)
    assert result['denominator']==20 and len(result['cases'])==20
    assert result['release_ready_count']==15 and result['unverified_count']==2
    assert [r['status'] for r in result['cases'][:5]]==[
        'NOT_ENROLLED','NOT_STARTED','ATTEMPT_ORDER_UNVERIFIED','CHECK_UNAVAILABLE','PREREQUISITES_REQUIRED']
    assert 'credential' not in str(result)


def test_latest_only_gate_but_all_attempts_and_revisions_counted():
    data=cohort();data['cases'][0]['runs'] += [
        {'run_id':'failed-child','parent_run_id':'run-0','created_at':'2026-09-27T00:00:10+00:00'},
        {'run_id':'current-child','parent_run_id':'failed-child','created_at':'2026-09-27T00:00:30+00:00'}]
    inspect=Mock(side_effect=ready);result=measure(data,inspect)
    assert result['attempt_count']==22 and result['revision_count']==2
    assert inspect.call_args_list[0].args==('task-0','current-child')
    assert result['cases'][0]['elapsed_to_delivery_seconds']==60


@pytest.mark.parametrize('field',['release_id','checksum','approved_at'])
def test_incomplete_release_never_counts_as_ready(field):
    def inspect(*_):
        result=ready();del result['release'][field];return result
    result=measure(cohort(),inspect)
    assert result['release_ready_count']==0 and result['unverified_count']==20


@pytest.mark.parametrize('finish',['bad','2026-09-27T00:01:00','2026-09-26T23:59:00+00:00',None])
def test_missing_invalid_or_negative_time_not_zero(finish):
    assert elapsed_seconds('2026-09-27T00:00:00+00:00',finish) is None


@pytest.mark.parametrize('mutation',['missing','duplicate'])
def test_population_integrity_required(mutation):
    data=cohort()
    if mutation=='missing':data['cases'].pop()
    else:data['cases'][1]['case_key']=data['cases'][0]['case_key']
    with pytest.raises(ValueError,match='POPULATION_INVALID'):measure(data,ready)
