from uuid import uuid4
import pytest
from test_project_api import client_repo
from test_pilot_cohort import plan_payload
from app.pilot_cohort import PilotEnrollmentConflict


def test_project_scope_and_invalid_plan(client_repo, monkeypatch):
    client, repo = client_repo
    monkeypatch.setattr('app.pilot_cohort.register', lambda *a: pytest.fail('not called'))
    assert client.post(f'/api/projects/{uuid4()}/pilot-cohorts', json=plan_payload()).status_code == 404
    assert client.get(f'/api/projects/{uuid4()}/pilot-cohorts').status_code == 404
    project = client.post('/api/projects', json={'project_name': 'Cohort validation'}).json()
    payload = plan_payload()
    payload['cases'].pop()
    assert client.post(f"/api/projects/{project['project_id']}/pilot-cohorts", json=payload).status_code == 422


@pytest.mark.parametrize('method', ['GET', 'POST'])
@pytest.mark.parametrize('where', ['lookup', 'operation'])
def test_errors_do_not_expose_storage_details(client_repo, monkeypatch, method, where):
    client, repo = client_repo
    project = client.post('/api/projects', json={'project_name': 'Cohort failure'}).json()
    def fail(*args): raise RuntimeError('synthetic-secret@private.example')
    if where == 'lookup': monkeypatch.setattr(repo, 'get_project', fail)
    else: monkeypatch.setattr('app.pilot_cohort.' + ('register' if method == 'POST' else 'inventory'), fail)
    response = client.request(method, f"/api/projects/{project['project_id']}/pilot-cohorts",
                              **({'json': plan_payload()} if method == 'POST' else {}))
    assert response.status_code == 503
    assert 'synthetic-secret' not in response.text and 'private.example' not in response.text


def test_binding_conflict_and_safe_failure(client_repo, monkeypatch):
    client, _ = client_repo
    project = client.post('/api/projects', json={'project_name': 'Binding errors'}).json()
    url = f"/api/projects/{project['project_id']}/pilot-cohorts/{uuid4()}/cases/case-00/task"
    def conflict(*args): raise PilotEnrollmentConflict('已綁定')
    monkeypatch.setattr('app.pilot_cohort.bind_task', conflict)
    response = client.post(url, json={'task_id': 'synthetic-task'})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'PILOT_ENROLLMENT_CONFLICT'
    assert client.post(url, json={'task_id': 'synthetic-task', 'passed': True}).status_code == 422
    def fail(*args): raise RuntimeError('synthetic-secret@private.example')
    monkeypatch.setattr('app.pilot_cohort.bind_task', fail)
    response = client.post(url, json={'task_id': 'synthetic-task'})
    assert response.status_code == 503 and 'synthetic-secret' not in response.text


def test_template_and_synthetic_download_require_project(client_repo):
    from io import BytesIO
    from zipfile import ZipFile
    client, _ = client_repo
    assert client.get(f'/api/projects/{uuid4()}/pilot-cohort-template').status_code == 404
    project = client.post('/api/projects', json={'project_name': 'Template preview'}).json()
    url = f"/api/projects/{project['project_id']}/pilot-cohort-template"
    response = client.get(url)
    assert response.status_code == 200 and len(response.json()['plan']['cases']) == 20
    assert response.json()['execution_verified'] is False
    download = client.get(url+'/download')
    assert download.status_code == 200 and download.headers['content-type'] == 'application/zip'
    with ZipFile(BytesIO(download.content)) as archive:
        assert 'plan.json' in archive.namelist()
        assert 'Not a Release' in archive.read('README.txt').decode()
