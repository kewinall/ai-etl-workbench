from copy import deepcopy
import pytest
from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from app import task_uploads
from app.json_source_profile import confirmed_json_profile
from app.run_api import create_run_router
from app.control_worker import run_once
from test_run_queue_integration import context, pytestmark
from test_json_input_contract import policy


def test_json_revision_invalidates_approval_and_preserves_history(context, tmp_path, monkeypatch):
    queue, task_id = context
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    upload = task_uploads.save_and_profile('synthetic.json', b'\xef\xbb\xbf[{"id":1},{"id":2}]')
    profile = confirmed_json_profile(upload['upload_id'], upload['checksum'], upload['size'])
    config = {'sources': [{**upload, **profile, 'type': 'JSON', 'has_actual_data': True}]}
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET source_type='JSON',source_config=%s WHERE task_id=%s", (Jsonb(config), task_id))
    parent = queue.enqueue(task_id, 'json-revision-parent')
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    app = FastAPI()
    app.include_router(create_run_router(queue))
    api = TestClient(app)
    url = f'/api/tasks/{task_id}/runs/{parent["run_id"]}/revisions'
    body = dict(request_key='json-revision-child', input_checksum=parent['input_checksum'],
                requirement_text='synthetic requirement', target_schema='ai_sample', target_table='synthetic',
                json_input_contract_v1=policy())
    wrong = deepcopy(body)
    wrong['json_input_contract_v1']['root_shape'] = 'OBJECT'
    assert api.post(url, json=wrong).status_code == 422
    response = api.post(url, json=body)
    assert response.status_code == 201, response.text
    child = response.json()
    assert child['input_summary']['json_input_contract_v1']['contract'] == policy()
    assert child['input_summary']['json_profile'] == {'root_shape': 'ARRAY', 'row_count': 2}
    assert 'upload_id' not in str(child['input_summary']) and 'sample_rows' not in str(child['input_summary'])
    assert api.post(url, json=body).json()['run_id'] == child['run_id']
    changed = {**body, 'requirement_text': 'different requirement'}
    assert api.post(url, json=changed).status_code == 409
    saved = queue.detail(task_id, UUID(child['run_id']))
    assert saved['approval'] is None and not saved['write_started']
    assert saved['input_checksum'] != parent['input_checksum']
    old = queue.detail(task_id, parent['run_id'])
    assert old['state'] == 'CANCELLED' and old['input_snapshot'] == parent['input_snapshot']
    assert old['approval']['decision'] == 'APPROVE'
    assert run_once(queue)['status'] == 'IDLE'
    queue.review(task_id, saved['run_id'], saved['input_checksum'], saved['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    final = queue.detail(task_id, saved['run_id'])
    proof = final['gate_result']['source_evidence'][0]['json']
    assert proof['complete'] and proof['records_expected'] == 2
    assert proof['column_types_checked'] is True
    assert not proof['execution_authorized'] and not final['write_started']


@pytest.mark.parametrize('content,code', [
    (b'[{"day":"2026/09/28"}]', 'JSON_DATE_FORMAT'),
    (b'[{"id":1},{"id":""}]', 'JSON_NUMBER_TYPE'),
    (b'[{"enabled":"TRUE"}]', 'JSON_BOOLEAN_TYPE'),
    (b'[{"amount":1.5},{"amount":"private-marker"}]', 'JSON_STRING_TYPE_OR_LENGTH'),
])
def test_json_gate_rejects_profile_suggestions_that_require_implicit_conversion(context, tmp_path, monkeypatch, content, code):
    queue, task_id = context
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    upload = task_uploads.save_and_profile('synthetic.json', content)
    profile = confirmed_json_profile(upload['upload_id'], upload['checksum'], upload['size'])
    config = {'sources': [{**upload, **profile, 'type': 'JSON', 'has_actual_data': True}],
              'json_input_contract_v1': policy()}
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET source_type='JSON',source_config=%s WHERE task_id=%s", (Jsonb(config), task_id))
    prepared = queue.enqueue(task_id, 'json-typed-gate-parent')
    queue.review(task_id, prepared['run_id'], prepared['input_checksum'], prepared['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    final = queue.detail(task_id, prepared['run_id'])
    evidence = final['gate_result']['source_evidence'][0]
    assert evidence['status'].startswith(code + ': record=')
    assert 'private-marker' not in str(final['gate_result'])
    assert not final['write_started'] and final['phase'] == 'REQUIREMENT_GATE'
    assert final['approval']['decision'] == 'APPROVE'
