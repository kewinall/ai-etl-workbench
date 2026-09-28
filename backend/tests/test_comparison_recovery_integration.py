"""Real isolated PG and API, synthetic cursor/engine explicitly not runtime E2E."""
from contextlib import nullcontext
from decimal import Decimal
from hashlib import sha256
from unittest.mock import Mock
from uuid import UUID,uuid4
import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from app import comparison_recovery as recovery, bound_comparison
from app import comparison_recovery_worker as worker
from app.execution_authorization import offer,authorize
from app.hop_dispatch_api import create_hop_dispatch_router
from app.hop_worker import execute_once
from app.run_queue import RunQueue
from app.sa_contract import digest
from app.target_ownership import claim_target
from app.target_preflight import empty_target_sql
from oracle_fixture import approved_answer
from test_excel_preparation_integration import prepared_excel
from test_run_queue_integration import context,pytestmark


@pytest.fixture
def executed(context,tmp_path,monkeypatch):
    base,task,run,sid,*_=prepared_excel(context,tmp_path,monkeypatch)
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self): return nullcontext(conn)
            @staticmethod
            def event(connection,run_id,event,phase,context=None):
                # Rollback fixture shares one transaction; model the real separate
                # transactions' chronological event timestamps explicitly.
                connection.execute('INSERT INTO platform.task_run_event(run_id,event_type,phase,event_context,created_at) VALUES(%s,%s,%s,%s,clock_timestamp())',
                    (run_id,event,phase,Jsonb(context or {})))
        q=Queue(base.url)
        try:
            approved_answer(q,task,run['run_id'],sid,rows=[dict(category='A',total_amount='150.25',row_count=1)])
            current=offer(q,conn,task,run['run_id'],sid)
            auth=authorize(q,task,run['run_id'],sid,current['binding_checksum'],True)
            b=current['binding']
            # Synthetic registration only, no actual Vertica DDL or connection.
            from app.approved_candidate import load_approved_candidate
            from app.delivery_compiler import compile_delivery_components
            from app.specification_store import context as spec_context
            candidate=load_approved_candidate(q,conn,task,run['run_id'],sid)
            saved,naming=spec_context(q,conn,task,run['run_id'])
            compiled=compile_delivery_components(candidate['compiled']['specification'],saved,naming)
            spec=compiled['specification']
            conn.execute('''INSERT INTO platform.platform_sample_table
                (project_id,schema_name,table_name,task_id,ddl_checksum,row_count) VALUES(%s,%s,%s,%s,%s,0)''',
                (run['project_id'],spec['target_schema'],spec['target_table'],task,compiled['ddl_checksum']))
            claim_target(q,task,run['run_id'],sid)
            target=conn.execute('SELECT * FROM platform.task_run_target_claim WHERE run_id=%s',(run['run_id'],)).fetchone()
            conn.execute('''INSERT INTO platform.task_run_target_empty_check
                (run_id,task_id,project_id,settings_checksum,hpl_checksum,sql_checksum) VALUES(%s,%s,%s,%s,%s,%s)''',
                (run['run_id'],task,run['project_id'],b['settings_checksum'],b['hpl_checksum'],sha256(empty_target_sql(target).encode()).hexdigest()))
            job_binding=dict(run_id=str(run['run_id']),specification_id=str(sid),execution_binding_checksum=current['binding_checksum'])
            jid=uuid4()
            conn.execute('''INSERT INTO platform.hop_dispatch_request
                (request_id,run_id,authorization_id,specification_id,binding,binding_checksum,status)
                VALUES(%s,%s,%s,%s,%s,%s,'QUEUED')''',
                (jid,run['run_id'],auth['authorization_id'],sid,Jsonb(job_binding),digest(job_binding)))
            conn.execute("UPDATE platform.hop_dispatch_request SET status='CLAIMED',claim_token=%s,claimed_at=clock_timestamp() WHERE request_id=%s",(uuid4(),jid))
            calls=[]
            def engine(candidate,lost,sink):
                calls.append('synthetic-engine')
                log=sink(b'Synthetic control test, no actual ETL')
                return dict(status='COMPLETED',exit_code=0,errors=0,log_checksum=log['checksum'])
            assert execute_once(q,task,run['run_id'],sid,UUID(auth['authorization_id']),engine)['status']=='HOP_EXECUTED_QA_REQUIRED'
            conn.execute("UPDATE platform.hop_dispatch_request SET status='NEEDS_REVIEW',outcome_code='HOP_PREPARATION_OR_COMPARISON_FAILED',finished_at=clock_timestamp() WHERE request_id=%s",(jid,))
            app=FastAPI();app.include_router(create_hop_dispatch_router(q));api=TestClient(app)
            yield q,conn,task,run['run_id'],api,calls
        finally: conn.rollback()


def synthetic_read(monkeypatch,*,mismatch=False,fail=False):
    cursor=Mock(description=[('category',),('total_amount',),('row_count',)])
    cursor.fetchmany.side_effect=[ [('A',Decimal('151.25' if mismatch else '150.25'),1)], [] ]
    if fail: cursor.execute.side_effect=RuntimeError('private connection information')
    db=Mock();db.cursor.return_value=cursor
    connection=Mock(side_effect=lambda **kw:nullcontext(db))
    monkeypatch.setattr(bound_comparison.vertica_python,'connect',connection)
    monkeypatch.setattr(bound_comparison,'connection_runtime',lambda *a:nullcontext({'environment':{'WORKBENCH_VERTICA_PASSWORD':'synthetic'}}))
    return connection,cursor


@pytest.mark.parametrize('mode',['match','mismatch','read_failure','stale_before_claim','stale_after_read'])
def test_recovery_single_read_keeps_original_job_and_cannot_release_failures(executed,monkeypatch,mode):
    q,conn,task,run,api,engine=executed
    url=f'/api/tasks/{task}/runs/{run}/comparison-recovery'
    original=conn.execute('SELECT * FROM platform.hop_dispatch_request WHERE run_id=%s',(run,)).fetchone()
    offered=api.get(url); assert offered.status_code==200,offered.text
    body=dict(confirmed=True,binding_checksum=offered.json()['binding_checksum'])
    assert api.post(url,json={**body,'confirmed':'true'}).status_code==422
    assert api.post(url,json={**body,'confirmed':False}).status_code==409
    assert api.post(url,json={**body,'binding_checksum':'0'*64}).status_code==409
    assert api.post(url,json={**body,'sql':'SELECT 1'}).status_code==422
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','false')
    assert api.post(url,json=body).status_code==409
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    first=api.post(url,json=body);assert first.status_code==200,first.text
    assert api.post(url,json=body).json()==first.json()
    connect,cursor=synthetic_read(monkeypatch,mismatch=mode=='mismatch',fail=mode=='read_failure')
    timing=conn.execute("SELECT e.created_at AS empty_at,w.created_at AS write_at FROM platform.task_run_target_empty_check e JOIN platform.task_run_event w USING(run_id) WHERE e.run_id=%s AND w.event_type='WRITE_STARTED'",(run,)).fetchone()
    assert timing['empty_at']<=timing['write_at'],timing
    bound_comparison.capture_binding(q,q,task,run)
    if mode=='stale_before_claim':
        conn.execute("UPDATE platform.task SET requirement_text='Changed' WHERE task_id=%s",(task,))
    if mode=='stale_after_read':
        original_read=worker.record_bound_comparison
        def changed(*args):
            result=original_read(*args)
            conn.execute("UPDATE platform.task SET requirement_text='Changed' WHERE task_id=%s",(task,))
            return result
        monkeypatch.setattr(worker,'record_bound_comparison',changed)
    result=worker.run_once(q,q,task,run)
    assert result['status']==('COMPLETED' if mode in ('match','mismatch') else 'FAILED')
    assert result['qa_passed'] is False and result['release_ready'] is False and result['etl_replay_allowed'] is False
    assert worker.run_once(q,q,task,run)=={'status':'IDLE'}
    assert connect.call_count==(0 if mode=='stale_before_claim' else 1)
    assert engine==['synthetic-engine']
    assert conn.execute("SELECT count(*) n FROM platform.task_run_event WHERE run_id=%s AND event_type='WRITE_STARTED'",(run,)).fetchone()['n']==1
    assert conn.execute('SELECT * FROM platform.hop_dispatch_request WHERE run_id=%s',(run,)).fetchone()==original
    assert api.get(url).json()==result
    assert api.post(url,json=body).json()==result
    assert api.post(url,json={**body,'binding_checksum':'0'*64}).status_code==409
    if mode=='match':
        recovery.require_completed_recovery(conn,original)
        assert result['outcome_code']=='RESULT_MATCH_QA_REQUIRED'
        assert cursor.execute.call_args.args[0].lstrip().startswith('SELECT')
    else:
        with pytest.raises(ValueError,match='RELEASE_COMPARISON_RECOVERY'):
            recovery.require_completed_recovery(conn,original)
    for sql in ("UPDATE platform.comparison_recovery SET status='QUEUED' WHERE run_id=%s",
                'DELETE FROM platform.comparison_recovery WHERE run_id=%s',
                "UPDATE platform.hop_dispatch_request SET status='COMPLETED' WHERE run_id=%s"):
        with pytest.raises(psycopg.Error):
            with conn.transaction():conn.execute(sql,(run,))


@pytest.mark.parametrize('change',['unknown','active','input','naming','completion_missing','different_task'])
def test_recovery_refuses_unknown_active_or_changed_execution(executed,change):
    q,conn,task,run,api,_=executed
    if change=='unknown': conn.execute("UPDATE platform.task_run SET outcome_code='HOP_RESULT_UNKNOWN' WHERE run_id=%s",(run,))
    elif change=='active': conn.execute('UPDATE platform.task_run SET lease_token=%s WHERE run_id=%s',(uuid4(),run))
    elif change=='input': conn.execute("UPDATE platform.task SET requirement_text='Changed' WHERE task_id=%s",(task,))
    elif change=='naming':
        old=conn.execute('SELECT * FROM platform.naming_contract WHERE task_id=%s ORDER BY version DESC LIMIT 1',(task,)).fetchone()
        conn.execute("INSERT INTO platform.naming_contract(contract_id,task_id,version,status,contract_json,checksum) VALUES(%s,%s,%s,'DRAFT',%s,%s)",
            (uuid4(),task,old['version']+1,Jsonb(old['contract_json']),old['checksum']))
    elif change=='completion_missing': conn.execute("DELETE FROM platform.task_run_event WHERE run_id=%s AND event_type='HOP_EXECUTED_QA_REQUIRED'",(run,))
    if change=='different_task': task='not-this-task'
    response=api.get(f'/api/tasks/{task}/runs/{run}/comparison-recovery')
    if change=='different_task': assert response.status_code==404
    else: assert response.status_code==200 and response.json()['status']=='NOT_ELIGIBLE',response.text
    assert conn.execute('SELECT count(*) n FROM platform.comparison_recovery WHERE run_id=%s',(run,)).fetchone()['n']==0


def test_claim_cannot_be_repeated_or_finished_by_another_owner(executed):
    q,conn,task,run,api,_=executed
    checksum=recovery.read(q,task,run)['binding_checksum']
    recovery.enqueue(q,task,run,checksum,True)
    claimed=recovery.claim(q,task,run)
    assert recovery.claim(q,task,run) is None
    from app.qa_context import load_qa_context
    with pytest.raises(ValueError,match='QA_COMPARISON_RECOVERY_REQUIRED'):
        load_qa_context(q,task,run,uuid4(),connection=conn)
    with pytest.raises(ValueError,match='CLAIM_LOST'):
        recovery.finish(q,{**claimed,'claim_token':uuid4()})
    assert recovery.read(q,task,run)['status']=='CLAIMED'
    assert recovery.finish(q,claimed)['status']=='FAILED'
