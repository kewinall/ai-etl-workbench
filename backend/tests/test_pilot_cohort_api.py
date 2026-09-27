from uuid import uuid4
import pytest
from test_project_api import client_repo
from test_pilot_cohort import plan_payload


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
