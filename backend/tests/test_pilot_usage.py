from contextlib import nullcontext
from copy import deepcopy
import pytest
from app.pilot_usage import summarize,read


def row(identity='a',**changes):
    return dict(invocation_id=identity,task_id='task',run_id='run',role='pilot_sa',
                provider='LOCAL_COPILOT',model='copilot/test',status='VALIDATED_NOT_APPROVED',
                trace_usage={'usage_type':'PARTIAL','input_tokens':None,'output_tokens':None,'ai_credits':0.1},
                trace_duration=1000,failure_usage=None,failure_duration=None,**changes)


def test_missing_tokens_not_zero_and_partial_credits_not_cost():
    rows=[row(),row('b')];before=deepcopy(rows);result=summarize(rows)
    assert result['metrics']['input_tokens']=={'reported_sum':None,'reported_invocations':0,'missing_invocations':2,'complete_sum':None}
    assert result['metrics']['ai_credits']['complete_sum']==0.2
    assert result['metrics']['duration_ms']['complete_sum']==2000
    assert result['provider_partial_records']==2 and result['cost'] is None and result['rate_version'] is None
    assert rows==before


def test_failure_usage_is_retained_and_unknown_not_dropped():
    failure=row('failure');failure.update(role='pilot_developer',status='DEVELOPER_OUTCOME_UNKNOWN',trace_usage=None,
        trace_duration=None,failure_usage={'output_tokens':5},failure_duration=800)
    unknown=row('unknown');unknown.update(status='OUTCOME_UNKNOWN_NEEDS_REVIEW',trace_usage=None,trace_duration=None)
    result=summarize([failure,unknown])
    assert result['journal_invocations']==2 and result['nonaccepted_invocations']==2
    assert result['metrics']['output_tokens']=={'reported_sum':5,'reported_invocations':1,'missing_invocations':1,'complete_sum':None}
    assert result['metrics']['duration_ms']['reported_sum']==800


@pytest.mark.parametrize('value',[-1,True,float('nan'),float('inf'),'12'])
def test_invalid_usage_rejected_without_raw_values(value):
    source=row();source['trace_usage']={'ai_credits':value}
    result=summarize([source])
    assert all(m['reported_sum'] is None for m in result['metrics'].values())


def test_empty_is_unavailable_not_zero():
    result=summarize([])
    assert result['journal_invocations']==0
    assert all(m['complete_sum'] is None and m['reported_sum'] is None for m in result['metrics'].values())


def test_real_zero_is_preserved():
    source=row();source['trace_usage']={'output_tokens':0};source['trace_duration']=0
    result=summarize([source])
    assert result['metrics']['output_tokens']['complete_sum']==0
    assert result['metrics']['duration_ms']['complete_sum']==0


def test_duplicate_rejected_not_double_counted():
    with pytest.raises(ValueError,match='DUPLICATE'):summarize([row(),row()])


def test_query_scoped_to_project_cohort_task_and_run_without_prompt():
    class Repo:
        def conn(self):return nullcontext(self)
        def execute(self,sql,params):
            assert params==('project','cohort')
            assert 'c.project_id=%s AND c.cohort_id=%s' in sql
            assert 'i.run_id=r.run_id AND i.task_id=t.task_id' in sql
            assert 'r.project_id=c.project_id' in sql
            assert 'input_json' not in sql and 'i.*' not in sql
            return self
        def fetchall(self):return [row()]
    result=read(Repo(),'project','cohort')
    assert result['groups'][0]['journal_invocations']==1
    assert result['cases']['task']['journal_invocations']==1
