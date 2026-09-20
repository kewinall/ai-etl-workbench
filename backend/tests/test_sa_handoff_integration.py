"""Real PG/API handoff, synthetic SA response. Approval transaction rolls back."""
from contextlib import nullcontext
import pytest
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.run_queue import RunQueue
from app.sa_journal import SAJournal
from app.run_api import create_run_router
from app.developer_contract import load_context,validate_proposal
from test_run_queue_integration import context
from test_specification_api_integration import prepared,pytestmark


def test_sa_handoff_requires_review_and_binds_developer_context(context):
    base,task,run,spec,naming,_=prepared(context)
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self):return nullcontext(conn)
        q=Queue(base.url);app=FastAPI();app.include_router(create_run_router(q));api=TestClient(app)
        url=f'/api/tasks/{task}/runs/{run["run_id"]}/sa-approval'
        try:
            assert api.get(url).json()['status']=='NOT_ELIGIBLE'
            journal=SAJournal(q);reserved=journal.reserve(task,run['run_id']);ctx=reserved['context']
            review=dict(version=1,run_id=str(run['run_id']),input_checksum=run['input_checksum'],context_checksum=ctx['context_checksum'],
                status='READY_FOR_REVIEW',summary='Synthetic PG integration, not an actual model',evidence_ids=['requirement'],issues=[])
            journal.finish(task,reserved['invocation_id'],review)
            with pytest.raises(ValueError,match='SA_APPROVAL_REQUIRED'):load_context(q,conn,task,run['run_id'])
            offer=api.get(url).json();assert offer['status']=='AWAITING_CONFIRMATION'
            body={'confirmed':True,'binding_checksum':offer['binding']['checksum']}
            assert api.post(url,json={**body,'confirmed':False}).status_code==422
            assert api.post(url,json={**body,'binding_checksum':'0'*64}).status_code==409
            assert api.post(url.replace(task,'missing-task'),json=body).status_code==404
            first=api.post(url,json=body);assert first.status_code==200
            assert api.post(url,json=body).json()==first.json()
            assert api.get(url).json()['status']=='APPROVED_CURRENT'
            captured=load_context(q,conn,task,run['run_id'])
            proposal=dict(version=1,context_checksum=captured['context']['context_checksum'],summary='Synthetic proposal',evidence_ids=['requirement'],specification=spec)
            assert not validate_proposal(proposal,captured)['execution_authorized']
            for sql in ('UPDATE platform.sa_handoff_approval SET binding_checksum=binding_checksum WHERE run_id=%s',
                        'DELETE FROM platform.sa_handoff_approval WHERE run_id=%s'):
                with pytest.raises(psycopg.Error):
                    with conn.transaction():conn.execute(sql,(run['run_id'],))
            conn.execute("UPDATE platform.task SET requirement_text=requirement_text||' revised' WHERE task_id=%s",(task,))
            current=api.get(url).json();assert current['status']=='STALE_APPROVAL' and not current['developer_authorized']
            assert api.post(url,json=body).status_code==409
            assert conn.execute("SELECT count(*) n FROM platform.task_run_event WHERE run_id=%s AND event_type='SA_HANDOFF_APPROVED'",(run['run_id'],)).fetchone()['n']==1
        finally:conn.rollback()
