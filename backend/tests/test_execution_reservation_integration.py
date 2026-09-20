from concurrent.futures import ThreadPoolExecutor
from uuid import UUID
import pytest
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from app import task_uploads
from oracle_fixture import approved_answer
from app.execution_authorization import offer,authorize
from app.execution_preparation import prepare_approved_source
from app.execution_reservation import reserve
from app.run_queue import RunConflict
from app.private_log_store import save_private_log


@pytest.mark.parametrize('completion', ['EXPIRED', 'COMPLETED', 'FAILED', 'UNKNOWN'])
def test_only_one_worker_can_consume_execution_consent(context,tmp_path,monkeypatch,completion):
    monkeypatch.setattr(task_uploads,'ROOT',tmp_path)
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path/'uploads')
    upload=task_uploads.save_and_profile('input.csv','類別,金額\nA,101.25\n'.encode())
    source={**upload,'type':'CSV','has_actual_data':True,'fields':[{'name':'類別','type':'VARCHAR(32)'},{'name':'金額','type':'NUMERIC(12,2)'}]}
    queue,task_id,run,spec,naming,api=prepared(context,source)
    base=f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved=api.post(base,json=spec).json();sid=UUID(saved['specification_id'])
    assert api.post(base+'/'+str(sid)+'/approve',json={'content_checksum':saved['content_checksum']}).status_code==200
    approved_answer(queue,task_id,run['run_id'],sid)
    with queue.conn() as conn: current=offer(queue,conn,task_id,run['run_id'],sid)
    consent=authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],True)
    aid=UUID(consent['authorization_id'])
    with prepare_approved_source(queue,task_id,run['run_id'],sid) as prepared_source:
        binding=prepared_source['binding']
        monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','false')
        with pytest.raises(RunConflict,match='EXECUTION_DISABLED'):
            reserve(queue,task_id,run['run_id'],sid,aid,binding)
        # Synthetic control transaction only; no executor is called by reserve.
        monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
        with pytest.raises(RunConflict,match='PREPARED_BINDING_CHANGED'):
            reserve(queue,task_id,run['run_id'],sid,aid,{**binding,'source_checksum':'0'*64})
        def attempt():
            try:return reserve(queue,task_id,run['run_id'],sid,aid,binding)['status']
            except RunConflict as e:return str(e)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:attempt(),range(2)))
        assert sorted(results)==['EXECUTION_AUTHORIZATION_CONSUMED','RESERVED_NOT_STARTED']
        detail=queue.detail(task_id,run['run_id'])
        assert detail['state']=='RUNNING' and detail['phase']=='HOP_PREPARATION'
        assert detail['write_started'] is False
        with pytest.raises(RunConflict,match='EXECUTION_BINDING_CHANGED'):
            queue.begin_external_write(run['run_id'],detail['lease_token'],{**binding,'hpl_checksum':'0'*64})
        queue.begin_external_write(run['run_id'],detail['lease_token'],binding)
        assert queue.detail(task_id,run['run_id'])['write_started'] is True
        with pytest.raises(RunConflict,match='WRITE_NOT_AUTHORIZED_OR_ALREADY_STARTED'):
            queue.begin_external_write(run['run_id'],detail['lease_token'],binding)
        with pytest.raises(RunConflict):
            queue.finish(run['run_id'],detail['lease_token'],'SUCCEEDED')
        result={'status':'COMPLETED' if completion=='EXPIRED' else completion,
                'exit_code':1 if completion=='FAILED' else 0,'errors':0,'log_checksum':'a'*64}
        with pytest.raises(RunConflict,match='HOP_LOG_EVIDENCE_MISSING_OR_CHANGED'):
            queue.complete_hop(run['run_id'],detail['lease_token'],result)
        log=save_private_log(queue,run['run_id'],detail['lease_token'],b'synthetic engine log')
        with pytest.raises(RunConflict,match='HOP_LOG_EVIDENCE_MISSING_OR_CHANGED'):
            queue.complete_hop(run['run_id'],detail['lease_token'],result)
        result['log_checksum']=log['checksum']
        if completion=='EXPIRED':
            with queue.conn() as conn:
                conn.execute("UPDATE platform.task_run SET lease_until=now()-interval '1 second' WHERE run_id=%s",(run['run_id'],))
            with pytest.raises(RunConflict):
                queue.complete_hop(run['run_id'],detail['lease_token'],result)
            assert queue.reap_expired()==1
        else:
            with pytest.raises(ValueError):
                queue.complete_hop(run['run_id'],detail['lease_token'],{**result,'secret':'must-not-persist'})
            queue.complete_hop(run['run_id'],detail['lease_token'],result)
            with pytest.raises(RunConflict):
                queue.complete_hop(run['run_id'],detail['lease_token'],result)
        final=queue.detail(task_id,run['run_id'])
        assert final['state']=='NEEDS_REVIEW' and final['lease_token'] is None
        assert final['outcome_code']=={'EXPIRED':'HOP_RESULT_UNKNOWN','COMPLETED':'HOP_EXECUTED_QA_REQUIRED','FAILED':'HOP_EXECUTION_FAILED','UNKNOWN':'HOP_RESULT_UNKNOWN'}[completion]
        assert attempt()=='EXECUTION_AUTHORIZATION_CONSUMED'
