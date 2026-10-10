from app import local_acceptance_worker as worker

def test_readiness_and_offers_never_create_dispatch(monkeypatch):
    reads=[]
    def get(path):
        reads.append(path)
        if path.endswith('/hop-dispatch'):return {'request':None,'offer':{'eligible':True}}
        if path.endswith('/release'):return {'status':'PREREQUISITES_REQUIRED','candidate':None}
        return {'invocation':None,'eligible':True,'dispatch_enabled':True}
    monkeypatch.setattr(worker,'get',get)
    tasks=[{'id':'TASK-TEST','latest_run':{'run_id':'11111111-1111-4111-8111-111111111111'}}]
    assert list(worker.pending(tasks))==[]
    assert len(reads)==5

def test_unknown_results_and_claimed_hop_never_replay(monkeypatch):
    def get(path):
        if path.endswith('/hop-dispatch'):return {'request':{'status':'CLAIMED','request_id':'x'}}
        if path.endswith('/release'):return {'status':'PORTABILITY_REQUIRED','candidate':{'candidate_id':'y'},'portability':{'status':'UNKNOWN'}}
        return {'invocation':{'status':'DEVELOPER_OUTCOME_UNKNOWN'}}
    monkeypatch.setattr(worker,'get',get)
    tasks=[{'id':'TASK-TEST','latest_run':{'run_id':'11111111-1111-4111-8111-111111111111'}}]
    assert list(worker.pending(tasks))==[]
