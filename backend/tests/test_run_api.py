from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.run_api import create_run_router, public_run
from app.run_queue import RunConflict, RunBlocked


class Queue:
    def revise(self, *args): raise RunConflict('RUN_NOT_REVISABLE')
    def list_runs(self, task_id): return []
    def enqueue(self, *args): raise RunBlocked([{'code': 'CONNECTION_NOT_CONFIGURED'}])
    def detail(self, *args): raise ValueError('RUN_NOT_FOUND')
    def review(self, *args): raise RunConflict('INPUT_OR_SETTINGS_CHANGED')
    def cancel_unstarted(self, *args): raise RunConflict('RUN_REQUIRES_EXECUTION_RECONCILIATION')


def client():
    app = FastAPI()
    app.include_router(create_run_router(Queue()))
    return TestClient(app)


def test_preparation_is_explicit_and_never_silently_executes():
    api = client()
    assert api.post('/api/tasks/task/runs', json={'request_key': 'request-0001'}).status_code == 422
    response = api.post('/api/tasks/task/runs', json={'mode': 'PREPARE', 'request_key': 'request-0001'})
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'RUN_SETTINGS_BLOCKED'
    assert api.get('/api/tasks/task/runs').json() == {'runs': [], 'worker_connected': None}


def test_review_scope_and_checksum_validation():
    api = client()
    body = {'run_id': str(uuid4()), 'kind': 'INPUT_REVIEW', 'decision': 'APPROVE', 'input_checksum': 'a'*64, 'settings_checksum': 'b'*64}
    assert api.post('/api/tasks/task/approvals', json=body).status_code == 409
    assert api.post('/api/tasks/task/approvals', json={**body, 'kind': 'RELEASE'}).status_code == 422
    assert api.post('/api/tasks/task/approvals', json={**body, 'input_checksum': 'wrong'}).status_code == 422


def test_unknown_or_cross_task_run_is_not_returned():
    assert client().get('/api/tasks/task/runs/'+str(uuid4())).status_code == 404
    assert client().get('/api/tasks/task/runs/'+str(uuid4())+'/sa-context').status_code == 404


def test_revision_requires_typed_fields_and_scope():
    api = client()
    url = '/api/tasks/task/runs/'+str(uuid4())+'/revisions'
    body = dict(request_key='revision-0001', input_checksum='a'*64, requirement_text='corrected', target_schema='ai_sample', target_table='synthetic')
    assert api.post(url, json=body).status_code == 409
    for invalid in ({'target_table': 'x;drop table x'}, {'requirement_text': '  '}, {'source_config': {}}, {'input_checksum': 'bad'}):
        assert api.post(url, json={**body, **invalid}).status_code == 422


def test_public_run_never_exposes_worker_lease_or_raw_settings():
    result = public_run({'run_id': uuid4(), 'lease_token': 'private-owner-token', 'lease_until': 'private',
                         'settings_snapshot': {'checksum': 'a'*64, 'host': 'internal-host', 'password': 'private'},
                         'input_snapshot': {'password': 'private'}})
    assert 'private' not in str(result)
    assert 'internal-host' not in str(result)
    assert result['approval_scope'] == 'INPUT_ONLY_NOT_EXECUTION_OR_RELEASE'
