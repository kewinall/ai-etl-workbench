from datetime import datetime, timezone
from uuid import uuid4
from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from psycopg.errors import UniqueViolation
from app.project_api import create_project_router, ProjectConflict


class MemoryRepository:
    def __init__(self):
        self.projects = {}
        self.tasks = []

    def list_projects(self):
        return list(self.projects.values())

    def get_project(self, project_id):
        return self.projects.get(project_id)

    def create_project(self, data):
        if any(p['project_name'] == data['project_name'] for p in self.projects.values()):
            raise UniqueViolation('database detail must not leak')
        p = {**deepcopy(data), 'project_id': str(uuid4()), 'updated_at': datetime.now(timezone.utc)}
        self.projects[p['project_id']] = p
        return p

    def update_project(self, project_id, data):
        old = self.projects[project_id]
        if data.get('expected_updated_at') and old['updated_at'] != data['expected_updated_at']:
            raise ProjectConflict()
        self.projects[project_id] = {**old, **data, 'updated_at': datetime.now(timezone.utc)}
        return self.projects[project_id]

    def list_tasks(self, project_id=None):
        return [t for t in self.tasks if t['project_id'] == project_id]


@pytest.fixture
def client_repo():
    repo = MemoryRepository()
    app = FastAPI()
    app.include_router(create_project_router(repo))
    return TestClient(app), repo


def test_project_create_edit_readback(client_repo):
    client, _ = client_repo
    response = client.post('/api/projects', json={'project_name': '  測試專案  ', 'naming_rules': {'column_aliases': {'客戶編號': 'customer_id'}}})
    assert response.status_code == 201
    project = response.json()
    assert project['project_name'] == '測試專案'
    result = client.put('/api/projects/'+project['project_id'], json={'project_name': '更新專案', 'description': 'updated', 'naming_rules': project['naming_rules'], 'expected_updated_at': project['updated_at']})
    assert result.status_code == 200
    saved = client.get('/api/projects/'+project['project_id']).json()
    assert saved['description'] == 'updated'
    assert saved['naming_rules'] == project['naming_rules']


def test_project_rejects_blank_and_duplicate_names(client_repo):
    client, _ = client_repo
    assert client.post('/api/projects', json={'project_name': '   '}).status_code == 422
    client.post('/api/projects', json={'project_name': 'duplicate'})
    response = client.post('/api/projects', json={'project_name': 'duplicate'})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'PROJECT_NAME_EXISTS'
    assert 'database detail' not in response.text


def test_project_invalid_and_missing_ids(client_repo):
    client, _ = client_repo
    assert client.get('/api/projects/not-a-uuid').status_code == 422
    assert client.get('/api/projects/'+str(uuid4())).status_code == 404


def test_project_dictionary_is_validated_server_side(client_repo):
    client, _ = client_repo
    for aliases in ({'客戶': 'name; DROP TABLE t'}, {'': 'name'}, ['not a mapping']):
        response = client.post('/api/projects', json={'project_name': 'invalid dictionary', 'naming_rules': {'column_aliases': aliases}})
        assert response.status_code == 422


def test_project_tasks_are_scoped(client_repo):
    client, repo = client_repo
    first = client.post('/api/projects', json={'project_name': 'first'}).json()
    second = client.post('/api/projects', json={'project_name': 'second'}).json()
    repo.tasks = [{'id': 'a', 'project_id': first['project_id']}, {'id': 'b', 'project_id': second['project_id']}]
    assert client.get(f"/api/projects/{first['project_id']}/tasks").json() == [repo.tasks[0]]


def test_project_stale_update_is_rejected(client_repo):
    client, _ = client_repo
    p = client.post('/api/projects', json={'project_name': 'original'}).json()
    payload = {'project_name': 'updated', 'expected_updated_at': p['updated_at']}
    assert client.put('/api/projects/'+p['project_id'], json=payload).status_code == 200
    response = client.put('/api/projects/'+p['project_id'], json=payload)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'PROJECT_CHANGED'


def test_summary_missing_project_does_not_query_counts(client_repo, monkeypatch):
    client, _ = client_repo
    def unexpected(*args):
        pytest.fail('Missing project must not query summary')
    monkeypatch.setattr('app.project_summary.project_summary', unexpected)
    response = client.get(f'/api/projects/{uuid4()}/summary')
    assert response.status_code == 404
    assert response.json()['detail']['code'] == 'PROJECT_NOT_FOUND'
    assert client.get('/api/projects/invalid/summary').status_code == 422


@pytest.mark.parametrize('failure_stage', ['lookup', 'summary'])
def test_summary_errors_are_not_empty_counts_or_secret_leaks(client_repo, monkeypatch, failure_stage):
    client, repo = client_repo
    project = client.post('/api/projects', json={'project_name': 'summary errors'}).json()
    def fail(*args):
        raise RuntimeError('password=synthetic-secret host=private.example')
    if failure_stage == 'lookup':
        monkeypatch.setattr(repo, 'get_project', fail)
    else:
        monkeypatch.setattr('app.project_summary.project_summary', fail)
    response = client.get(f"/api/projects/{project['project_id']}/summary")
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'PROJECT_SUMMARY_UNAVAILABLE'
    assert 'task_count' not in response.text
    assert 'synthetic-secret' not in response.text and 'private.example' not in response.text
