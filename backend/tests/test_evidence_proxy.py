from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import evidence_proxy as proxy

def test_proxy_never_forwards_writes_or_unlisted_sources(monkeypatch):
    calls=[]
    monkeypatch.setattr(proxy,'fetch',lambda path:calls.append(path))
    app=FastAPI();app.include_router(proxy.create_evidence_router());client=TestClient(app)
    path=proxy.PREFIX+'/tasks/TASK-20260928-0001/runs/unknown/sa-authorization'
    assert client.post(path,json={'consent':True}).status_code==405
    assert client.get(proxy.PREFIX+'/settings/groups').status_code==404
    assert client.get(proxy.PREFIX+'/tasks/not-an-accepted-task').status_code==404
    assert not calls

def test_origin_is_fixed_not_user_supplied(monkeypatch):
    import pytest
    from fastapi import HTTPException
    monkeypatch.setenv('WORKBENCH_EVIDENCE_ORIGIN','https://example.com')
    with pytest.raises(HTTPException) as error:proxy.origin()
    assert error.value.status_code==503

def test_download_url_rewrite_does_not_modify_checksums_or_artifact_content():
    original={'download_url':'/api/tasks/TASK-20260928-0001/release/download',
              'checksum':'a'*64,'content':'/api/original/artifact'}
    value=proxy.urls(original)
    assert value['download_url'].startswith(proxy.PREFIX+'/tasks/')
    assert value['checksum']==original['checksum']
    assert value['content']==original['content']

def test_readonly_workflow_disables_each_write_even_for_current_queued_source(monkeypatch):
    run={'task_id':'TASK-20260928-0001','run_id':'retained-run','state':'QUEUED','phase':'REQUIREMENT_GATE','matches_current':True}
    def document(path):
        if path.endswith('/runs'):return {'runs':[run]}
        if path.endswith('/specifications'):return {'items':[]}
        if path.endswith('/runs/retained-run'):return run
        return {}
    monkeypatch.setattr(proxy,'document',document)
    result=proxy.workflow('TASK-20260928-0001',run['run_id'])
    assert result['read_only_source'] and not result['matches_current']
    assert not result['next_action']['operation_enabled']
    assert not any(stage['can_operate'] for stage in result['stages'])
    for operation in result['operation_qualifications'].values():
        assert not operation['enabled']
        assert operation['blocked_reason']

def test_readonly_workflow_preserves_actual_download_qualification(monkeypatch):
    run={'task_id':'TASK-20260928-0001','run_id':'released-run','state':'SUCCEEDED','matches_current':True}
    def document(path):
        if path.endswith('/runs'):return {'runs':[run]}
        if path.endswith('/specifications'):return {'items':[]}
        if path.endswith('/release'):return {'status':'RELEASE_READY','release_ready':True}
        if path.endswith('/runs/released-run'):return run
        return {}
    monkeypatch.setattr(proxy,'document',document)
    result=proxy.workflow('TASK-20260928-0001',run['run_id'])
    assert result['operation_qualifications']['release_download']['enabled']
    assert not any(op['enabled'] for key,op in result['operation_qualifications'].items() if key!='release_download')
