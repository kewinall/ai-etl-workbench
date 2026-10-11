from app import local_acceptance_worker as worker

def test_readiness_and_offers_never_create_dispatch(monkeypatch):
    reads=[]
    def get(path):
        reads.append(path)
        if path.endswith('/runs'):return {'runs':[{'run_id':'11111111-1111-4111-8111-111111111111'}]}
        if path.endswith('/hop-dispatch'):return {'request':None,'offer':{'eligible':True}}
        if path.endswith('/release'):return {'status':'PREREQUISITES_REQUIRED','candidate':None}
        return {'invocation':None,'eligible':True,'dispatch_enabled':True}
    monkeypatch.setattr(worker,'get',get)
    tasks=[{'id':'TASK-TEST'}]
    assert list(worker.pending(tasks))==[]
    assert len(reads)==7


def test_authorized_comparison_uses_read_only_worker_not_hop(monkeypatch):
    def get(path):
        if path.endswith('/runs'):return {'runs':[{'run_id':'11111111-1111-4111-8111-111111111111'}]}
        if path.endswith('/comparison-recovery'):return {'status':'QUEUED','recovery_id':'approved-read'}
        return {}
    monkeypatch.setattr(worker,'get',get)
    assert list(worker.pending([{'id':'TASK-TEST'}]))==[
        ('comparison','approved-read','TASK-TEST','11111111-1111-4111-8111-111111111111',None)]
    captured=[]
    monkeypatch.setattr(worker.subprocess,'CREATE_NO_WINDOW',0,raising=False)
    monkeypatch.setattr(worker.subprocess,'run',lambda args,**kw:captured.append(args))
    worker.launch('comparison','TASK-TEST','11111111-1111-4111-8111-111111111111',None,'project')
    assert 'app.comparison_recovery_worker' in captured[0]
    assert 'app.pilot_hop_worker' not in captured[0]
    assert '--candidate-id' not in captured[0]

def test_unknown_results_and_claimed_hop_never_replay(monkeypatch):
    def get(path):
        if path.endswith('/runs'):return {'runs':[{'run_id':'11111111-1111-4111-8111-111111111111'}]}
        if path.endswith('/hop-dispatch'):return {'request':{'status':'CLAIMED','request_id':'x'}}
        if path.endswith('/release'):return {'status':'PORTABILITY_REQUIRED','candidate':{'candidate_id':'y'},'portability':{'status':'UNKNOWN'}}
        return {'invocation':{'status':'DEVELOPER_OUTCOME_UNKNOWN'}}
    monkeypatch.setattr(worker,'get',get)
    tasks=[{'id':'TASK-TEST'}]
    assert list(worker.pending(tasks))==[]


def test_real_task_list_shape_reads_latest_run_and_existing_authorized_intent(monkeypatch):
    calls=[]
    def get(path):
        calls.append(path)
        if path.endswith('/runs'):return {'runs':[{'run_id':'22222222-2222-4222-8222-222222222222'}, {'run_id':'11111111-1111-4111-8111-111111111111'}]}
        if path.endswith('/sa-invocation'):return {'invocation':{'status':'SA_QUEUED','invocation_id':'existing-approved-intent'}}
        return {}
    monkeypatch.setattr(worker,'get',get)
    assert list(worker.pending([{'id':'TASK-TEST'}]))==[
        ('local_sa_worker','existing-approved-intent','TASK-TEST','22222222-2222-4222-8222-222222222222',None)]
    assert not any('11111111' in path for path in calls)


def test_scoped_run_never_reads_or_claims_an_unexpected_latest_version(monkeypatch):
    from unittest.mock import Mock
    read=Mock(return_value={'runs':[{'run_id':'22222222-2222-4222-8222-222222222222'}]})
    monkeypatch.setattr(worker,'get',read)
    assert list(worker.pending([{'id':'TASK-TEST'}],'11111111-1111-4111-8111-111111111111'))==[]
    read.assert_called_once_with('/tasks/TASK-TEST/runs')


def test_default_scope_preserves_multiple_tasks_with_distinct_runs(monkeypatch):
    ids={'TASK-A':'11111111-1111-4111-8111-111111111111','TASK-B':'22222222-2222-4222-8222-222222222222'}
    def get(path):
        task=path.split('/')[2]
        if path.endswith('/runs'):return {'runs':[{'run_id':ids[task]}]}
        if path.endswith('/sa-invocation'):return {'invocation':{'status':'SA_QUEUED','invocation_id':task+'-intent'}}
        return {}
    monkeypatch.setattr(worker,'get',get)
    results=list(worker.pending([{'id':task} for task in ids]))
    assert [(row[2],row[3]) for row in results]==list(ids.items())


def test_scoped_failure_worker_uses_explicit_target_and_original_binding(monkeypatch):
    calls=[]
    monkeypatch.setattr(worker.subprocess,'CREATE_NO_WINDOW',0,raising=False)
    monkeypatch.setattr(worker.subprocess,'run',lambda args,**kw:calls.append(args))
    worker.launch('hop','TASK-TEST','11111111-1111-4111-8111-111111111111',None,'project',
                  'ui_accept_revision_20261011_v1','a'*64)
    args=calls[0]
    assert 'app.pilot_failure_probe' in args and '--once' not in args
    assert args[args.index('--binding-checksum')+1]=='a'*64
    assert 'WORKBENCH_UI_ACCEPT_FAILURE_TARGET=ui_accept_revision_20261011_v1' in args
    assert 'WORKBENCH_SYNTHETIC_FAILURE_PROBE=missing-column-v1' in args
