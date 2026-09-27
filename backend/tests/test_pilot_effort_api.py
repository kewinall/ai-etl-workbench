from uuid import uuid4
import pytest
from test_project_api import client_repo


def test_effort_read_scope_no_store_and_no_public_write(client_repo, monkeypatch):
    client, _ = client_repo
    project = client.post('/api/projects', json={'project_name':'Effort read'}).json()
    path = f"/api/projects/{project['project_id']}/pilot-cohorts/{uuid4()}/cases/case-00/effort"
    monkeypatch.setattr('app.pilot_effort_store.read', lambda *args: {'events':[], 'comparison_ready':False})
    response = client.get(path)
    assert response.status_code == 200 and response.headers['cache-control']=='no-store'
    assert response.json()['comparison_ready'] is False
    assert client.post(path, json={'actor':'HUMAN'}).status_code == 422
    assert client.get(f'/api/projects/{uuid4()}/pilot-cohorts/{uuid4()}/cases/case-00/effort').status_code == 404


@pytest.mark.parametrize('message,code', [('EFFORT_CASE_SCOPE_INVALID',404), ('private-secret-host',503)])
def test_effort_read_error_masking(client_repo, monkeypatch, message, code):
    client, _ = client_repo
    project = client.post('/api/projects', json={'project_name':'Effort failure'}).json()
    def fail(*args): raise ValueError(message)
    monkeypatch.setattr('app.pilot_effort_store.read', fail)
    result = client.get(f"/api/projects/{project['project_id']}/pilot-cohorts/{uuid4()}/cases/case-00/effort")
    assert result.status_code == code and message not in result.text
