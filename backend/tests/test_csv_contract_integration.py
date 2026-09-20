"""Real isolated PostgreSQL/API; no model, file modification or ETL execution."""
import os
from copy import deepcopy
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from test_run_queue_integration import context
from app.control_worker import run_once
from app.run_api import create_run_router
from app.sa_journal import SAJournal
from app.sa_work_queue import authorization_offer, SAWorkQueue

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated Compose DB required')


def test_csv_only_revision_api_is_atomic_idempotent_and_requires_new_review(context):
    queue, task_id = context
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET source_config=source_config-'csv_input_contract_v1' WHERE task_id=%s", (task_id,))
    parent = queue.enqueue(task_id, 'csv-parent-0001')
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    app = FastAPI(); app.include_router(create_run_router(queue)); api = TestClient(app)
    assert api.get(f'/api/tasks/{task_id}/runs/{parent["run_id"]}/sa-authorization').json()['eligible'] is False
    url = f'/api/tasks/{task_id}/runs/{parent["run_id"]}/revisions'
    contract = {'version': 1, 'encoding': 'UTF-8', 'delimiter': '\t', 'header': False, 'extra_columns': 'IGNORE'}
    body = {'request_key': 'csv-child-0001', 'input_checksum': parent['input_checksum'], 'requirement_text': parent['input_snapshot']['requirement_text'], 'target_schema': 'ai_sample', 'target_table': 'synthetic', 'csv_input_contract_v1': contract}
    response = api.post(url, json=body)
    assert response.status_code == 201, response.text
    assert api.post(url, json=body).json()['run_id'] == response.json()['run_id']
    assert api.post(url, json={**body, 'csv_input_contract_v1': {**contract, 'extra_columns': 'REJECT'}}).status_code == 409
    from uuid import UUID
    child = queue.detail(task_id, UUID(response.json()['run_id']))
    assert child['approval'] is None
    assert child['input_snapshot']['source_config']['csv_input_contract_v1'] == contract
    assert queue.detail(task_id, parent['run_id'])['input_snapshot'] == parent['input_snapshot']
    assert run_once(queue)['status'] == 'IDLE'
    queue.review(task_id, child['run_id'], child['input_checksum'], child['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    assert queue.detail(task_id, child['run_id'])['write_started'] is False
    evidence = api.get(f'/api/tasks/{task_id}/runs/{child["run_id"]}/sa-context').json()
    assert evidence['context_origin'] == 'CURRENT_PREVIEW_NOT_DISPATCHED'
    assert evidence['context']['version'] == 2
    assert any(e['id'] == 'source.0.csv_input' and e['value']['header'] is False for e in evidence['context']['evidence'])
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) AS n FROM platform.agent_invocation WHERE task_id=%s', (task_id,)).fetchone()['n'] == 0
        assert conn.execute('SELECT source_config FROM platform.task WHERE task_id=%s', (task_id,)).fetchone()['source_config']['password'] == 'must-not-persist'


def test_captured_context_survives_rules_upgrade_without_recomputation(context, monkeypatch):
    queue, task_id = context
    run = queue.enqueue(task_id, 'csv-captured-01')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    run = queue.detail(task_id, run['run_id'])
    SAWorkQueue(queue).enqueue(task_id, run['run_id'], authorization_offer(run))
    journal = SAJournal(queue)
    before = deepcopy(journal.context(task_id, run['run_id']))
    assert before['context_origin'] == 'CAPTURED_AT_AUTHORIZATION'
    def forbidden(_):
        raise AssertionError('Historical authorization context must never be regenerated')
    monkeypatch.setattr('app.sa_journal.build_sa_context', forbidden)
    assert journal.context(task_id, run['run_id']) == before
