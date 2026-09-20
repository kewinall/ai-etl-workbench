from uuid import UUID, uuid4
import pytest
from psycopg.types.json import Jsonb
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from app.approved_candidate import load_approved_candidate


def test_saved_approval_required_and_stale_naming_blocks(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    base = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved = api.post(base,json=spec).json()
    sid = UUID(saved['specification_id'])
    with queue.conn() as conn:
        with pytest.raises(ValueError,match='SPECIFICATION_APPROVAL_REQUIRED'):
            load_approved_candidate(queue,conn,task_id,run['run_id'],sid)
    assert api.post(base+'/'+str(sid)+'/approve',json={'content_checksum':saved['content_checksum']}).status_code == 200
    before = queue.detail(task_id,run['run_id'])
    with queue.conn() as conn:
        candidate = load_approved_candidate(queue,conn,task_id,run['run_id'],sid)
        assert candidate['status'] == 'APPROVED_CANDIDATE_ONLY'
        assert not candidate['execution_authorized']
        assert candidate['compiled']['hpl']
        query = candidate['result_query']
        assert query['plan']['run_id'] == str(run['run_id'])
        assert query['plan']['specification_checksum'] == saved['content_checksum']
        assert query['plan']['naming_checksum'] == naming['checksum']
        assert query['execution_authorized'] is False
    assert queue.detail(task_id,run['run_id']) == before
    with queue.conn() as conn:
        conn.execute("INSERT INTO platform.naming_contract(contract_id,task_id,version,status,contract_json,checksum) VALUES(%s,%s,2,'DRAFT',%s,%s)",(uuid4(),task_id,Jsonb(naming['contract_json']),naming['checksum']))
    with queue.conn() as conn:
        with pytest.raises(ValueError,match='APPROVED_INPUTS_STALE_OR_INVALID'):
            load_approved_candidate(queue,conn,task_id,run['run_id'],sid)


def test_newer_specification_prevents_old_approved_candidate(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    base = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    first = api.post(base,json=spec).json()
    assert api.post(base+'/'+first['specification_id']+'/approve',json={'content_checksum':first['content_checksum']}).status_code == 200
    assert api.post(base,json={**spec,'filters':[]}).status_code == 200
    with queue.conn() as conn:
        with pytest.raises(ValueError,match='CURRENT_SPECIFICATION_REQUIRED'):
            load_approved_candidate(queue,conn,task_id,run['run_id'],UUID(first['specification_id']))
