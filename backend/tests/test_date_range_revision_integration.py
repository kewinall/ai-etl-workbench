"""Real isolated PostgreSQL revision/approval evidence; no model or ETL writes."""
import pytest
from psycopg.types.json import Jsonb
from app.control_worker import run_once
from app.run_queue import RunConflict
from test_run_queue_integration import context, pytestmark


def test_recent_requirement_revision_restarts_gate_and_preserves_blocked_history(context):
    queue, task_id = context
    with queue.conn() as conn:
        # The date column exists before correction. This case revises requirements,
        # not file metadata (which the source edit policy intentionally protects).
        source = conn.execute('SELECT source_config FROM platform.task WHERE task_id=%s', (task_id,)).fetchone()['source_config']
        source['sources'][0]['fields'].append({'name': '日期', 'type': 'DATE'})
        conn.execute('UPDATE platform.task SET source_config=%s WHERE task_id=%s', (Jsonb(source), task_id))
        conn.execute("UPDATE platform.task SET requirement_text='最近客戶',target_config=%s WHERE task_id=%s",
                     (Jsonb({'schema': 'ai_sample', 'table': 'synthetic',
                             'requirements_v1': {'write_mode': 'APPEND'}}), task_id))
    parent = queue.enqueue(task_id, 'date-range-parent')
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    old = queue.detail(task_id, parent['run_id'])
    assert any(i['issue_type'] == 'AMBIGUOUS' and i['field_path'] == 'requirements_v1.date_scope'
               for i in old['gate_result']['issues'])
    conditions = {'write_mode': 'APPEND', 'date_scope': 'RANGE', 'date_column': '日期',
                  'start_date': '2026-09-01', 'end_date_exclusive': '2026-10-01'}
    args = (task_id, parent['run_id'], 'date-range-child', parent['input_checksum'],
            '最近客戶：2026 年 9 月', 'ai_sample', 'synthetic', conditions)
    child = queue.revise(*args)
    assert queue.revise(*args)['run_id'] == child['run_id']
    assert child['parent_run_id'] == parent['run_id']
    assert child['input_checksum'] != parent['input_checksum']
    assert queue.detail(task_id, child['run_id'])['approval'] is None
    assert run_once(queue)['status'] == 'IDLE'
    with pytest.raises(RunConflict):
        queue.review(task_id, child['run_id'], parent['input_checksum'], child['settings_snapshot']['checksum'], 'APPROVE')
    queue.review(task_id, child['run_id'], child['input_checksum'], child['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    current = queue.detail(task_id, child['run_id'])
    assert current['phase'] == 'REQUIREMENT_GATE' and not current['write_started']
    assert 'REQUIREMENT_GATE_STARTED' in [e['event_type'] for e in current['events']]
    preserved = queue.detail(task_id, parent['run_id'])
    assert preserved['input_snapshot'] == parent['input_snapshot']
    assert preserved['gate_result'] == old['gate_result']
    assert preserved['state'] == 'CANCELLED' and not preserved['write_started']
