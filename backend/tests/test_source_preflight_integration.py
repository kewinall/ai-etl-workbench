"""Real isolated PostgreSQL queue + real temporary upload, no external ETL."""
import pytest
from psycopg.types.json import Jsonb
from test_run_queue_integration import context, pytestmark
from app import task_uploads
from app.control_worker import run_once


@pytest.mark.parametrize('tamper', [False, True])
def test_approved_upload_gate_evidence_persists(context, tmp_path, monkeypatch, tamper):
    queue, task_id = context
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    upload = task_uploads.save_and_profile('synthetic.csv', b'id\n1\n')
    with queue.conn() as conn:
        config = conn.execute('SELECT source_config FROM platform.task WHERE task_id=%s', (task_id,)).fetchone()['source_config']
        config['sources'] = [{**upload, 'type': 'CSV', 'has_actual_data': True}]
        conn.execute('UPDATE platform.task SET source_config=%s WHERE task_id=%s', (Jsonb(config), task_id))
    run = queue.enqueue(task_id, 'source-integrity-0001')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    if tamper:
        (tmp_path / upload['upload_id'] / 'source.csv').write_bytes(b'id\n2\n')
    assert run_once(queue)['status'] == ('NEEDS_INPUT' if tamper else 'CHECKED')
    saved = queue.detail(task_id, run['run_id'])
    assert saved['state'] == 'NEEDS_REVIEW'
    assert saved['write_started'] is False
    assert saved['gate_result']['source_evidence'][0]['status'] == ('UPLOAD_CONTENT_CHANGED' if tamper else 'UPLOAD_BYTES_VERIFIED')
    assert str(tmp_path) not in str(saved['gate_result'])
    assert run_once(queue)['status'] == 'IDLE'
