"""Existing execution evidence, changes confined to one rolled-back PG transaction."""
import os
from pathlib import Path
from contextlib import nullcontext
from uuid import uuid4
import pytest
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.run_queue import RunQueue,RunConflict
from app.run_api import create_run_router

pytestmark=pytest.mark.skipif(not os.getenv('WORKBENCH_QA_CONTEXT_RUN'),reason='Explicit existing evidence required')


@pytest.mark.parametrize('outcome',['HOP_RESULT_UNKNOWN','HOP_EXECUTION_FAILED'])
def test_api_reconciliation_is_durable_idempotent_and_never_retries(outcome):
    base=RunQueue(os.environ['DATABASE_URL']);task=os.environ['WORKBENCH_QA_CONTEXT_TASK'];run=os.environ['WORKBENCH_QA_CONTEXT_RUN']
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self):return nullcontext(conn)
        q=Queue(base.url)
        try:
            if not conn.execute("SELECT to_regclass('platform.execution_reconciliation') n").fetchone()['n']:
                conn.execute(Path('/app/database/migrations/044_execution_reconciliation.sql').read_text())
            conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',outcome_code=%s WHERE run_id=%s",(outcome,run))
            before=conn.execute("SELECT count(*) n FROM platform.task_run_event WHERE run_id=%s AND event_type='WRITE_STARTED'",(run,)).fetchone()['n']
            app=FastAPI();app.include_router(create_run_router(q));api=TestClient(app)
            url=f'/api/tasks/{task}/runs/{run}/reconciliation'
            offer=api.get(url);assert offer.status_code==200
            body=dict(binding_checksum=offer.json()['binding']['checksum'],evidence_sha256='d'*64,observed_row_count=1,
                engine_stopped=True,target_checked=True,confirmed=True)
            assert api.post(url,json={**body,'confirmed':False}).status_code==422
            assert api.post(url,json={**body,'binding_checksum':'0'*64}).status_code==409
            assert api.post(url.replace(task,'missing-task'),json=body).status_code==404
            first=api.post(url,json=body);assert first.status_code==200
            assert api.post(url,json=body).json()==first.json()
            assert api.get(url).json()==first.json()
            assert api.post(url,json={**body,'observed_row_count':2}).status_code==409
            state=conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s',(run,)).fetchone()
            assert state['state']=='FAILED' and state['write_started'] and state['outcome_code']==outcome
            assert not first.json()['release_ready'] and not first.json()['automatic_retry_allowed']
            with pytest.raises(RunConflict):q.finish(run,uuid4(),'SUCCEEDED')
            with pytest.raises(RunConflict):q.cancel_unstarted(task,run)
            for operation in ('UPDATE platform.execution_reconciliation SET observed_row_count=0 WHERE run_id=%s',
                              'DELETE FROM platform.execution_reconciliation WHERE run_id=%s'):
                with pytest.raises(psycopg.Error):
                    with conn.transaction():conn.execute(operation,(run,))
            assert conn.execute("SELECT count(*) n FROM platform.task_run_event WHERE run_id=%s AND event_type='WRITE_STARTED'",(run,)).fetchone()['n']==before
            assert conn.execute("SELECT count(*) n FROM platform.task_run_event WHERE run_id=%s AND event_type='OPERATOR_RECONCILED_WITHOUT_RETRY'",(run,)).fetchone()['n']==1
        finally:conn.rollback()
