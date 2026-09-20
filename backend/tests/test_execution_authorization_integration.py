from uuid import UUID
import pytest
import psycopg
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from app import task_uploads
from oracle_fixture import approved_answer
from app.execution_authorization import offer, authorize


def test_execution_consent_is_distinct_immutable_and_idempotent(context,tmp_path,monkeypatch):
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path)
    upload=task_uploads.save_and_profile('input.csv','類別,金額\nA,101.25\n'.encode())
    source={**upload,'type':'CSV','has_actual_data':True,'fields':[{'name':'類別','type':'VARCHAR(32)'},{'name':'金額','type':'NUMERIC(12,2)'}]}
    queue,task_id,run,spec,naming,api=prepared(context,source)
    base=f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved=api.post(base,json=spec).json();sid=UUID(saved['specification_id'])
    assert api.post(base+'/'+str(sid)+'/approve',json={'content_checksum':saved['content_checksum']}).status_code==200
    with pytest.raises(ValueError,match='EXPECTED_RESULT_ORACLE_REQUIRED'):
        with queue.conn() as conn:offer(queue,conn,task_id,run['run_id'],sid)
    answer=approved_answer(queue,task_id,run['run_id'],sid,approve=False)
    with pytest.raises(ValueError,match='EXPECTED_RESULT_ORACLE_APPROVAL_REQUIRED'):
        with queue.conn() as conn:offer(queue,conn,task_id,run['run_id'],sid)
    from app.oracle_store import approve_oracle
    approve_oracle(queue,task_id,run['run_id'],sid,answer['oracle_id'],answer['document_checksum'])
    with queue.conn() as conn:
        current=offer(queue,conn,task_id,run['run_id'],sid)
        assert current['binding']['oracle_id']==answer['oracle_id']
        assert current['binding']['oracle_checksum']==answer['document_checksum']
        assert current['binding']['policy_version']=='hop-single-attempt-v2'
        assert conn.execute('SELECT count(*) AS n FROM platform.task_run_execution_authorization WHERE run_id=%s',(run['run_id'],)).fetchone()['n']==0
    with pytest.raises(ValueError,match='EXPLICIT_EXECUTION_CONSENT_REQUIRED'):
        authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],False)
    with pytest.raises(ValueError,match='EXECUTION_BINDING_CHANGED'):
        authorize(queue,task_id,run['run_id'],sid,'0'*64,True)
    result=authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],True)
    assert authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],True)==result
    with queue.conn() as conn:
        persisted=conn.execute('SELECT binding,binding_checksum FROM platform.task_run_execution_authorization WHERE run_id=%s',(run['run_id'],)).fetchone()
        assert persisted['binding']==current['binding']
        assert len(persisted['binding']['result_query_checksum'])==64
    # Simulate a compiler-policy change without modifying persisted history.
    # A new offer must change, and the existing consent cannot authorize it.
    from app import approved_candidate
    original_query_builder=approved_candidate.build_result_query_plan
    def changed_query(*args):
        value=original_query_builder(*args)
        return {**value,'checksum':'f'*64}
    with monkeypatch.context() as altered:
        altered.setattr(approved_candidate,'build_result_query_plan',changed_query)
        with queue.conn() as conn:
            changed_offer=offer(queue,conn,task_id,run['run_id'],sid)
        assert changed_offer['binding_checksum']!=current['binding_checksum']
        with pytest.raises(ValueError,match='EXECUTION_BINDING_CHANGED'):
            authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],True)
        with pytest.raises(ValueError,match='EXECUTION_AUTHORIZATION_CONFLICT_OR_EXPIRED'):
            authorize(queue,task_id,run['run_id'],sid,changed_offer['binding_checksum'],True)
    assert authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],True)==result
    with pytest.raises(psycopg.Error,match='immutable'):
        with queue.conn() as conn:
            conn.execute('UPDATE platform.task_run_execution_authorization SET binding_checksum=%s WHERE run_id=%s',('0'*64,run['run_id']))
    detail=queue.detail(task_id,run['run_id'])
    assert detail['state']=='NEEDS_REVIEW' and not detail['write_started']
    assert sum(e['event_type']=='EXECUTION_CONSENT_RECORDED' for e in detail['events'])==1
    changed=approved_answer(queue,task_id,run['run_id'],sid,[{'category':'A','total_amount':'102.25','row_count':1}])
    assert changed['version']==2
    with pytest.raises(ValueError,match='EXECUTION_BINDING_CHANGED'):
        authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],True)
    from app.execution_preparation import prepare_approved_source
    from app.execution_reservation import reserve
    from app.run_queue import RunConflict
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    with prepare_approved_source(queue,task_id,run['run_id'],sid) as staged:
        with pytest.raises(RunConflict,match='EXECUTION_BINDING_CHANGED'):
            reserve(queue,task_id,run['run_id'],sid,UUID(result['authorization_id']),staged['binding'])
    assert queue.detail(task_id,run['run_id'])['write_started'] is False
