from copy import deepcopy
from uuid import UUID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from app import task_uploads
from app.excel_profile import selected_profile
from app.run_api import create_run_router
from app.control_worker import run_once
from test_run_queue_integration import context, pytestmark
from test_excel_input_contract import policy, workbook


def test_excel_contract_revision_requires_fresh_approval(context, tmp_path, monkeypatch):
    queue, task_id = context
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    upload = task_uploads.save_and_profile('synthetic.xlsx', workbook())
    profile = selected_profile(upload['upload_id'], upload['checksum'], upload['size'], '明細', 2)
    config = {'sources': [{**upload, **profile, 'type': 'EXCEL', 'has_actual_data': True}]}
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET source_type='EXCEL',source_config=%s WHERE task_id=%s", (Jsonb(config), task_id))
    parent = queue.enqueue(task_id, 'excel-revision-parent')
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    app = FastAPI()
    app.include_router(create_run_router(queue))
    api = TestClient(app)
    url = f'/api/tasks/{task_id}/runs/{parent["run_id"]}/revisions'
    body = dict(request_key='excel-revision-child', input_checksum=parent['input_checksum'],
                requirement_text='synthetic requirement', target_schema='ai_sample', target_table='synthetic',
                excel_input_contract_v1=policy())
    wrong = deepcopy(body)
    wrong['excel_input_contract_v1']['worksheet'] = 'unconfirmed'
    assert api.post(url, json=wrong).status_code == 422
    response = api.post(url, json=body)
    assert response.status_code == 201, response.text
    child = response.json()
    assert child['input_summary']['excel_input_contract_v1']['contract'] == policy()
    assert child['input_summary']['excel_selection'] == {'worksheet': '明細', 'header_row': 2}
    assert 'upload_id' not in str(child['input_summary']) and 'sample_rows' not in str(child['input_summary'])
    assert api.post(url, json=body).json()['run_id'] == child['run_id']
    changed = deepcopy(body)
    changed['excel_input_contract_v1']['blank_rows'] = 'PRESERVE'
    assert api.post(url, json=changed).status_code == 409
    saved = queue.detail(task_id, UUID(child['run_id']))
    assert saved['approval'] is None and not saved['write_started']
    assert saved['input_checksum'] != parent['input_checksum']
    old = queue.detail(task_id, parent['run_id'])
    assert old['state'] == 'CANCELLED'
    assert old['input_snapshot'] == parent['input_snapshot']
    assert old['approval']['decision'] == 'APPROVE'
    assert run_once(queue)['status'] == 'IDLE'
    queue.review(task_id, saved['run_id'], saved['input_checksum'], saved['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    final = queue.detail(task_id, saved['run_id'])
    assert final['gate_result']['source_evidence'][0]['excel_full_file_validated']
    assert not final['write_started']
