"""Isolated PostgreSQL evidence, not Join execution acceptance."""
from copy import deepcopy
import pytest
from psycopg.types.json import Jsonb
from app.control_worker import run_once
from app.run_queue import RunConflict
from test_run_queue_integration import context, pytestmark
from test_join_contract import contract
from test_multi_csv import contracts


def test_join_revision_is_idempotent_reapproved_and_history_preserved(context):
    queue, task_id = context
    with queue.conn() as conn:
        source = conn.execute('SELECT source_config FROM platform.task WHERE task_id=%s', (task_id,)).fetchone()['source_config']
        source['sources'] = [{'type': 'CSV', 'has_actual_data': False,
                             'fields': [{'name': '客戶編號', 'type': 'BIGINT'}]} for _ in range(2)]
        conn.execute('UPDATE platform.task SET source_config=%s WHERE task_id=%s', (Jsonb(source), task_id))
    parent = queue.enqueue(task_id, 'join-parent-01')
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    old = queue.detail(task_id, parent['run_id'])
    assert any(i['field_path'] == 'join_contract_v1' and i['issue_type'] == 'MISSING' for i in old['gate_result']['issues'])
    target = parent['input_snapshot']['target_config']
    args = (task_id, parent['run_id'], 'join-child-01', parent['input_checksum'],
            '明確 LEFT JOIN，null 鍵不相符，重複鍵展開', target['schema'], target['table'])
    child = queue.revise(*args, join_contract_v1=contract(), csv_input_contracts_v1=contracts())
    assert queue.revise(*args, join_contract_v1=contract(), csv_input_contracts_v1=contracts())['run_id'] == child['run_id']
    changed = deepcopy(contract())
    changed['joins'][0]['join_type'] = 'INNER'
    with pytest.raises(RunConflict, match='IDEMPOTENCY_KEY_REUSED'):
        queue.revise(*args, join_contract_v1=changed, csv_input_contracts_v1=contracts())
    changed_csv = contracts()
    changed_csv['sources']['source.1']['delimiter'] = ';'
    with pytest.raises(RunConflict, match='IDEMPOTENCY_KEY_REUSED'):
        queue.revise(*args, join_contract_v1=contract(), csv_input_contracts_v1=changed_csv)
    assert child['input_snapshot']['source_config']['csv_input_contracts_v1'] == contracts()
    assert 'csv_input_contract_v1' not in child['input_snapshot']['source_config']
    assert child['input_checksum'] != parent['input_checksum']
    assert child['input_snapshot']['target_config']['join_contract_v1'] == contract()
    assert queue.detail(task_id, child['run_id'])['approval'] is None
    assert run_once(queue)['status'] == 'IDLE'
    queue.review(task_id, child['run_id'], child['input_checksum'], child['settings_snapshot']['checksum'], 'APPROVE')
    # Deliberately still blocked: a captured contract alone is not a working
    # multi-source CSV compiler/stager or real INNER/LEFT mismatch acceptance.
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    current = queue.detail(task_id, child['run_id'])
    assert not any(i['field_path'] == 'join_contract_v1' for i in current['gate_result']['issues'])
    assert not any(i['field_path'].startswith('source_config.csv_input_contract') for i in current['gate_result']['issues'])
    assert any(i['issue_type'] == 'UNSUPPORTED' for i in current['gate_result']['issues'])
    assert not current['write_started']
    preserved = queue.detail(task_id, parent['run_id'])
    assert preserved['input_snapshot'] == parent['input_snapshot']
    assert preserved['gate_result'] == old['gate_result']
    assert preserved['state'] == 'CANCELLED' and not preserved['write_started']
