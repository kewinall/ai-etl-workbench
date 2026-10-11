"""Isolated PostgreSQL/API: specification save/approve require a current same-Run SA approval.

Synthetic SA review only (no model call), no Hop, no Vertica. Preview routes are covered elsewhere and keep
their read-only behaviour without SA.
"""
from copy import deepcopy
from psycopg.types.json import Jsonb
from app.control_worker import run_once
from test_run_queue_integration import context, pytestmark
from test_specification_api_integration import prepared, approve_sa


def counts(queue, task_id, run_id):
    with queue.conn() as conn:
        one = lambda sql, *args: conn.execute(sql, args).fetchone()['n']
        return {
            'specifications': one('SELECT count(*) AS n FROM platform.specification WHERE task_id=%s', task_id),
            'approvals': one('SELECT count(*) AS n FROM platform.specification_approval a JOIN platform.specification s USING(specification_id) WHERE s.task_id=%s', task_id),
            'events': one("SELECT count(*) AS n FROM platform.task_run_event WHERE run_id=%s AND event_type LIKE 'SPECIFICATION%%'", run_id),
        }


def refused(response, code):
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == code
    assert 'SA' in response.json()['detail']['message']


def test_missing_sa_refuses_save_and_semantic_evidence_without_writes(context):
    queue, task_id, run, spec, naming, api = prepared(context, sa_approved=False)
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    refused(api.post(url, json=spec), 'SPEC_SA_APPROVAL_MISSING')
    # A semantically mismatched proposal is also refused before rejected-attempt evidence is written.
    bad = deepcopy(spec); bad['filters'][0]['operator'] = 'LT'
    refused(api.post(url, json=bad), 'SPEC_SA_APPROVAL_MISSING')
    assert counts(queue, task_id, run['run_id']) == {'specifications': 0, 'approvals': 0, 'events': 0}
    # Read-only preview and history keep their behaviour.
    assert api.post(url.replace('/specifications', '/specification/validate'), json=spec).json()['status'] == 'VALIDATED_NOT_APPROVED'
    assert api.get(url).json()['items'] == []


def test_valid_sa_allows_idempotent_save_and_approve(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    first = api.post(url, json=spec)
    assert first.status_code == 200 and first.json()['status'] == 'SAVED_NOT_EXECUTABLE', first.text
    assert api.post(url, json=spec).json() == first.json()
    body = {'content_checksum': first.json()['content_checksum']}
    approve_url = f"{url}/{first.json()['specification_id']}/approve"
    approved = api.post(approve_url, json=body)
    assert approved.status_code == 200 and approved.json()['execution_authorized'] is False
    assert api.post(approve_url, json=body).json()['approval_id'] == approved.json()['approval_id']
    assert counts(queue, task_id, run['run_id']) == {'specifications': 1, 'approvals': 1, 'events': 2}


def test_stale_sa_refuses_approve_and_save_and_keeps_history(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved = api.post(url, json=spec).json()
    with queue.conn() as conn:
        conn.execute('UPDATE platform.task SET requirement_text=%s WHERE task_id=%s', ('revised after SA', task_id))
    refused(api.post(f"{url}/{saved['specification_id']}/approve", json={'content_checksum': saved['content_checksum']}),
            'SPEC_SA_APPROVAL_STALE')
    refused(api.post(url, json=spec), 'SPEC_SA_APPROVAL_STALE')
    assert counts(queue, task_id, run['run_id']) == {'specifications': 1, 'approvals': 0, 'events': 1}
    assert len(api.get(url).json()['items']) == 1


def test_sa_approval_of_another_run_does_not_qualify(context):
    queue, task_id, first, spec, naming, api = prepared(context)
    queue.cancel_unstarted(task_id, first['run_id'])
    second = queue.enqueue(task_id, 'spec-preview-0002')
    queue.review(task_id, second['run_id'], second['input_checksum'], second['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    other = deepcopy(spec)
    other.update(run_id=str(second['run_id']), input_checksum=second['input_checksum'], settings_checksum=second['settings_snapshot']['checksum'])
    url = f'/api/tasks/{task_id}/runs/{second["run_id"]}/specifications'
    refused(api.post(url, json=other), 'SPEC_SA_APPROVAL_MISSING')
    assert counts(queue, task_id, second['run_id']) == {'specifications': 0, 'approvals': 0, 'events': 0}
    # The cancelled Run keeps its own SA approval but is no longer a current input for a specification.
    response = api.post(f'/api/tasks/{task_id}/runs/{first["run_id"]}/specifications', json=spec)
    assert response.status_code == 200 and response.json()['status'] == 'INVALID', response.text
    assert 'SPEC_INPUT_NOT_APPROVED' in {i['code'] for i in response.json()['issues']}
    assert counts(queue, task_id, first['run_id'])['specifications'] == 0
    approve_sa(queue, task_id, second)
    assert api.post(url, json=other).json()['status'] == 'SAVED_NOT_EXECUTABLE'


def test_started_write_with_valid_sa_still_refuses_save(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    with queue.conn() as conn:
        conn.execute('UPDATE platform.task_run SET write_started=true WHERE run_id=%s', (run['run_id'],))
    response = api.post(f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications', json=spec)
    # SA is still valid; the existing post-write rule rejects it (semantic INVALID, not a save).
    assert response.status_code == 200 and response.json()['status'] == 'INVALID', response.text
    assert 'SPEC_INPUT_NOT_APPROVED' in {i['code'] for i in response.json()['issues']}
    assert counts(queue, task_id, run['run_id'])['specifications'] == 0
