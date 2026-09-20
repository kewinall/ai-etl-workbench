import pytest
from psycopg.types.json import Jsonb
from test_run_queue_integration import context, pytestmark
from app import task_uploads
from app.control_worker import run_once


@pytest.mark.parametrize('tamper', [False, True])
def test_replacement_transaction_and_idempotency(context, tmp_path, monkeypatch, tamper):
    queue, task_id = context
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    old = task_uploads.save_and_profile('old.csv', b'id\n1\n')
    new = task_uploads.save_and_profile('new.csv', b'id\n2\n')
    config = {'sources':[{**old, 'type':'CSV', 'has_actual_data':True}],
              'csv_input_contract_v1':{'version':1,'encoding':'UTF-8','delimiter':',','header':True,'extra_columns':'REJECT'}}
    with queue.conn() as conn:
        conn.execute('UPDATE platform.task SET source_config=%s WHERE task_id=%s', (Jsonb(config),task_id))
    parent = queue.enqueue(task_id, 'replacement-parent')
    queue.review(task_id,parent['run_id'],parent['input_checksum'],parent['settings_snapshot']['checksum'],'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    replacement = {key:new[key] for key in ('upload_id','checksum','size','original_name','fields')}
    def revise():
        return queue.revise(task_id,parent['run_id'],'replacement-child',parent['input_checksum'],
                            parent['input_snapshot']['requirement_text'],'ai_sample','synthetic',
                            csv_replacement_v1=replacement)
    if tamper:
        (tmp_path / new['upload_id'] / 'source.csv').write_bytes(b'id\n3\n')
        with pytest.raises(ValueError, match='UPLOAD_CONTENT_CHANGED'):
            revise()
        with queue.conn() as conn:
            assert conn.execute('SELECT source_config FROM platform.task WHERE task_id=%s',(task_id,)).fetchone()['source_config'] == config
        assert len(queue.list_runs(task_id)) == 1
        assert queue.detail(task_id,parent['run_id'])['state'] == 'NEEDS_REVIEW'
    else:
        child = revise()
        assert revise()['run_id'] == child['run_id']
        assert len(queue.list_runs(task_id)) == 2
        saved = queue.detail(task_id,child['run_id'])
        assert saved['approval'] is None
        assert saved['write_started'] is False
        assert saved['input_checksum'] != parent['input_checksum']
        historical = queue.detail(task_id,parent['run_id'])
        assert historical['outcome_code'] == 'SUPERSEDED_BY_REVISION'
        assert historical['approval']['decision'] == 'APPROVE'
        assert historical['input_snapshot']['source_config']['sources'][0]['checksum'] == old['checksum']
        assert run_once(queue)['status'] == 'IDLE'
        queue.review(task_id,child['run_id'],child['input_checksum'],child['settings_snapshot']['checksum'],'APPROVE')
        assert run_once(queue)['status'] == 'CHECKED'
        assert queue.detail(task_id,child['run_id'])['gate_result']['source_evidence'][0]['content_checksum'] == new['checksum']
    assert (tmp_path / old['upload_id'] / 'source.csv').read_bytes() == b'id\n1\n'
