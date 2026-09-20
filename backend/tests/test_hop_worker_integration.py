"""Real PostgreSQL/control/files, synthetic synchronous engine. No ETL writes."""
from uuid import UUID
import os
from hashlib import sha256
from xml.etree import ElementTree as ET
import pytest
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from app import task_uploads
from oracle_fixture import approved_answer
from app.execution_authorization import offer, authorize
from app.hop_worker import execute_once
from app import hop_worker
from app.private_log_store import save_private_log,read_private_log
from app.run_queue import RunConflict
from app.execution_oracle import load_execution_oracle


@pytest.mark.parametrize('failure', [False, True, 'TAMPER', pytest.param('NATIVE_NO_CONNECTION',marks=pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_HOP_ADAPTER_TEST')!='1',reason='Native worker image required'))])
def test_worker_persists_terminal_review_and_cleans_staging(context,tmp_path,monkeypatch,failure):
    monkeypatch.setattr(task_uploads,'ROOT',tmp_path)
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path/'uploads')
    upload=task_uploads.save_and_profile('input.csv','類別,金額\nA,101.25\n'.encode())
    source={**upload,'type':'CSV','has_actual_data':True,'fields':[{'name':'類別','type':'VARCHAR(32)'},{'name':'金額','type':'NUMERIC(12,2)'}]}
    queue,task_id,run,spec,naming,api=prepared(context,source)
    base=f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved=api.post(base,json=spec).json()
    sid=UUID(saved['specification_id'])
    assert api.post(base+'/'+str(sid)+'/approve',json={'content_checksum':saved['content_checksum']}).status_code==200
    approved_answer(queue,task_id,run['run_id'],sid)
    with queue.conn() as conn:
        current=offer(queue,conn,task_id,run['run_id'],sid)
    consent=authorize(queue,task_id,run['run_id'],sid,current['binding_checksum'],True)
    with pytest.raises(ValueError,match='COMPLETED_HOP_EXECUTION_REQUIRED'):
        load_execution_oracle(queue,task_id,run['run_id'])
    calls=[]
    if failure=='TAMPER':
        original=hop_worker.reserve
        def tamper(*args):
            receipt=original(*args)
            for path in (tmp_path/'runtime-temp'/'run-sources').glob('*/source.csv'):
                path.write_bytes(b'changed after reservation')
            return receipt
        monkeypatch.setattr(hop_worker,'reserve',tamper)
    def executor(candidate,lost,log_sink):
        calls.append(candidate['directory'])
        assert candidate['source_path'].is_file() and candidate['hpl_path'].is_file()
        active=queue.detail(task_id,run['run_id'])
        assert active['state']=='RUNNING' and active['phase']=='HOP_EXECUTION' and active['write_started']
        if failure=='NATIVE_NO_CONNECTION':
            from app.hop_cli import run_hop_cli
            from app.hop_metadata import local_metadata_json
            metadata=local_metadata_json().encode()
            (candidate['directory']/'metadata.json').write_bytes(metadata)
            nodes=[n.findtext('name') for n in ET.fromstring(candidate['hpl_path'].read_bytes()).findall('transform')]
            # Deliberately no rdbms metadata or platform credentials in child env.
            evidence=run_hop_cli(candidate,lost,metadata_checksum=sha256(metadata).hexdigest(),
                expected_nodes=nodes,environment={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/home/workbench'},log_sink=log_sink)
            return evidence['result']
        log=b'synthetic private-host credential=not-real'
        receipt=log_sink(log)
        assert save_private_log(queue,run['run_id'],active['lease_token'],log)==receipt
        assert read_private_log(queue,task_id,run['run_id'])==log
        with pytest.raises(RunConflict,match='PRIVATE_LOG_ALREADY_RECORDED'):
            save_private_log(queue,run['run_id'],active['lease_token'],b'changed')
        with pytest.raises(RunConflict,match='PRIVATE_LOG_NOT_FOUND'):
            read_private_log(queue,'different-task',run['run_id'])
        if failure:
            raise RuntimeError('synthetic-private-error-not-for-storage')
        return {'status':'COMPLETED','exit_code':0,'errors':0,'log_checksum':receipt['checksum']}
    # Only this test process enables reservation; native case has no DB metadata.
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    result=execute_once(queue,task_id,run['run_id'],sid,UUID(consent['authorization_id']),executor)
    expected='HOP_EXECUTION_FAILED' if failure=='NATIVE_NO_CONNECTION' else 'HOP_PREPARATION_INVALID' if failure=='TAMPER' else 'HOP_RESULT_UNKNOWN' if failure else 'HOP_EXECUTED_QA_REQUIRED'
    assert result['status']==expected
    assert len(calls)==(0 if failure=='TAMPER' else 1)
    assert not list((tmp_path/'runtime-temp'/'run-sources').iterdir())
    final=queue.detail(task_id,run['run_id'])
    assert final['state']=='NEEDS_REVIEW' and final['outcome_code']==expected and final['lease_token'] is None
    assert final['write_started'] is (failure!='TAMPER')
    if failure is False:
        pinned=load_execution_oracle(queue,task_id,run['run_id'])
        assert pinned['oracle_id']==current['binding']['oracle_id']
        assert pinned['document_checksum']==current['binding']['oracle_checksum']
        assert pinned['binding_checksum']==current['binding_checksum']
        assert pinned['qa_passed'] is False and pinned['release_ready'] is False
        assert b'101.25' in pinned['content']
        from decimal import Decimal
        from app.execution_result_comparison import compare_execution_cursor
        class ResultCursor:
            description=[('category',),('total_amount',),('row_count',)]
            def __init__(self,amount):self.rows=[('A',Decimal(amount),1)]
            def fetchmany(self,size):rows=self.rows;self.rows=[];return rows
        compared=compare_execution_cursor(queue,task_id,run['run_id'],ResultCursor('101.25'))
        assert compared['status']=='MATCH' and compared['actual_count']==1
        assert compared['qa_passed'] is False and compared['actual_provenance']=='NOT_VERIFIED'
        wrong=compare_execution_cursor(queue,task_id,run['run_id'],ResultCursor('102.25'))
        assert wrong['status']=='MISMATCH' and wrong['missing_count']==1
        assert 'rows' not in compared and 'content' not in compared
        assert compared['hop_log_checksum']==pinned['hop_log_checksum']
        assert compared['hop_event_id']==pinned['hop_event_id']
        from app.comparison_store import record_execution_comparison,list_comparisons
        import psycopg
        recorded=record_execution_comparison(queue,task_id,run['run_id'],ResultCursor('101.25'))
        assert record_execution_comparison(queue,task_id,run['run_id'],ResultCursor('101.25'))==recorded
        mismatch=record_execution_comparison(queue,task_id,run['run_id'],ResultCursor('102.25'))
        assert mismatch['comparison_id']!=recorded['comparison_id']
        def evidence_counts():
            with queue.conn() as conn:
                records=conn.execute('SELECT count(*) AS n FROM platform.task_run_result_comparison WHERE run_id=%s',(run['run_id'],)).fetchone()['n']
                events=conn.execute("SELECT count(*) AS n FROM platform.task_run_event WHERE run_id=%s AND event_type='RESULT_COMPARISON_RECORDED'",(run['run_id'],)).fetchone()['n']
                return records,events
        before=evidence_counts()
        class StateChangingCursor(ResultCursor):
            def fetchmany(self,size):
                if self.rows:
                    with queue.conn() as conn:
                        queue.locked_task(conn,task_id)
                        conn.execute("UPDATE platform.task_run SET outcome_code='HOP_RESULT_UNKNOWN' WHERE run_id=%s",(run['run_id'],))
                return super().fetchmany(size)
        try:
            with pytest.raises(ValueError,match='COMPLETED_HOP_EXECUTION_REQUIRED'):
                record_execution_comparison(queue,task_id,run['run_id'],StateChangingCursor('103.25'))
            assert evidence_counts()==before
        finally:
            with queue.conn() as conn:
                conn.execute("UPDATE platform.task_run SET outcome_code='HOP_EXECUTED_QA_REQUIRED' WHERE run_id=%s",(run['run_id'],))
        def fail_event(*args,**kwargs):raise RuntimeError('synthetic timeline failure')
        with monkeypatch.context() as patcher:
            patcher.setattr(queue,'event',fail_event)
            with pytest.raises(RuntimeError,match='synthetic timeline failure'):
                record_execution_comparison(queue,task_id,run['run_id'],ResultCursor('103.25'))
        assert evidence_counts()==before
        history=list_comparisons(queue,task_id,run['run_id'])
        assert len(history['items'])==2 and history['qa_passed'] is False
        assert {item['evidence']['status'] for item in history['items']}=={'MATCH','MISMATCH'}
        from app.run_api import create_run_router
        api.app.include_router(create_run_router(queue))
        response=api.get(f'/api/tasks/{task_id}/runs/{run["run_id"]}/comparisons')
        assert response.status_code==200
        assert len(response.json()['items'])==2 and response.json()['release_ready'] is False
        assert api.get(f'/api/tasks/other-task/runs/{run["run_id"]}/comparisons').status_code==404
        with pytest.raises(ValueError,match='COMPARISON_RUN_NOT_FOUND'):
            list_comparisons(queue,'other-task',run['run_id'])
        with pytest.raises(psycopg.Error):
            with queue.conn() as conn:
                conn.execute('UPDATE platform.task_run_result_comparison SET checksum=%s WHERE comparison_id=%s',('0'*64,recorded['comparison_id']))
        # Corrupt only this fixture's event, then restore it; no user Run touched.
        from psycopg.types.json import Jsonb
        with queue.conn() as conn:
            event=conn.execute('SELECT event_context FROM platform.task_run_event WHERE event_id=%s',(pinned['hop_event_id'],)).fetchone()['event_context']
            conn.execute('UPDATE platform.task_run_event SET event_context=%s WHERE event_id=%s',(Jsonb({**event,'log_checksum':'0'*64}),pinned['hop_event_id']))
        try:
            with pytest.raises(ValueError,match='HOP_COMPLETION_EVIDENCE_CHANGED'):
                load_execution_oracle(queue,task_id,run['run_id'])
        finally:
            with queue.conn() as conn:
                conn.execute('UPDATE platform.task_run_event SET event_context=%s WHERE event_id=%s',(Jsonb(event),pinned['hop_event_id']))
    else:
        with pytest.raises(ValueError,match='COMPLETED_HOP_EXECUTION_REQUIRED'):
            load_execution_oracle(queue,task_id,run['run_id'])
    if failure=='NATIVE_NO_CONNECTION':
        log=read_private_log(queue,task_id,run['run_id'])
        assert b'target.0 - ERROR: Error initializing transform [target]' in log
        assert b'databaseMeta' in log and b'is null' in log
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) AS n FROM platform.task_run_execution_reservation WHERE run_id=%s',(run['run_id'],)).fetchone()['n']==1
