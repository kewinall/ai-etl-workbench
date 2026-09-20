"""Actual isolated PG request lifecycle; synthetic roles, no Vertica/model/Hop."""
from contextlib import nullcontext
from uuid import UUID,uuid4
import pytest
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import task_uploads,specification_store
from app.run_queue import RunQueue
from app.sa_journal import SAJournal
from app.sa_approval import read,approve
from app.developer_contract import load_context,DeveloperProposalV1
from app.developer_gateway import PROMPT,PROMPT_VERSION
from app.developer_journal import DeveloperJournal
from app.hop_dispatch import offer,claim,finish
from app.hop_dispatch_api import create_hop_dispatch_router
from app.sa_contract import digest
from test_run_queue_integration import context
from test_specification_api_integration import prepared,pytestmark
from oracle_fixture import approved_answer


def test_website_hop_request_requires_lineage_and_is_single_consumption(context,tmp_path,monkeypatch):
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path)
    upload=task_uploads.save_and_profile('input.csv','類別,金額\nA,101.25\n'.encode())
    source={**upload,'type':'CSV','has_actual_data':True,'fields':[{'name':'類別','type':'VARCHAR(32)'},{'name':'金額','type':'NUMERIC(12,2)'}]}
    base,task,run,spec,_,_=prepared(context,source)
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self):return nullcontext(conn)
        q=Queue(base.url)
        try:
            sa=SAJournal(q);intent=sa.reserve(task,run['run_id']);ctx=intent['context']
            review=dict(version=1,run_id=str(run['run_id']),input_checksum=run['input_checksum'],context_checksum=ctx['context_checksum'],
                status='READY_FOR_REVIEW',summary='Synthetic control test only',evidence_ids=['requirement'],issues=[])
            record=conn.execute('SELECT * FROM platform.agent_invocation WHERE invocation_id=%s',(intent['invocation_id'],)).fetchone()
            trace={key:record[key] for key in ('provider','model','context_checksum')}
            trace.update(run_id=str(run['run_id']),input_checksum=run['input_checksum'],
                prompt_checksum=record['input_json']['prompt_checksum'],schema_checksum=record['input_json']['schema_checksum'],usage={})
            sa.finish(task,intent['invocation_id'],review,trace)
            approve(q,task,run['run_id'],read(q,task,run['run_id'])['binding']['checksum'],confirmed=True)
            captured=load_context(q,conn,task,run['run_id']);ctx=captured['context'];journal=DeveloperJournal(q)
            dev=journal.reserve(task,run['run_id'],ctx['context_checksum'],confirmed=True);token=journal.claim(task,dev['invocation_id'])
            proposal=dict(version=1,context_checksum=ctx['context_checksum'],summary='Synthetic design',evidence_ids=['requirement'],specification=spec)
            trace.update(context_checksum=ctx['context_checksum'],model=run['settings_snapshot']['model_routes']['etl_specification'],
                prompt_version=PROMPT_VERSION,prompt_checksum=digest(PROMPT),schema_checksum=digest(DeveloperProposalV1.model_json_schema()),
                output_checksum=digest(proposal),duration_ms=1,status='VALIDATED_NOT_APPROVED')
            saved=journal.finish(task,dev['invocation_id'],token,proposal,trace)['specification'];sid=UUID(saved['specification_id'])
            specification_store.approve(q,conn,task,run['run_id'],sid,saved['content_checksum'])
            approved_answer(q,task,run['run_id'],sid)
            current=offer(q,conn,task,run['run_id'],sid)
            assert current['ddl'].startswith('CREATE TABLE "ai_sample".') and 'DROP' not in current['ddl']
            app=FastAPI();app.include_router(create_hop_dispatch_router(q));api=TestClient(app)
            url=f'/api/tasks/{task}/runs/{run["run_id"]}/hop-dispatch'
            assert api.get(url).json()['offer']['binding_checksum']==current['binding_checksum']
            body={'confirmed':True,'specification_id':str(sid),'binding_checksum':current['binding_checksum']}
            monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','false')
            assert api.post(url,json=body).status_code==409
            monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
            assert api.post(url,json={**body,'confirmed':False}).status_code==409
            assert api.post(url,json={**body,'binding_checksum':'0'*64}).status_code==409
            first=api.post(url,json=body);assert first.status_code==200
            assert api.post(url,json=body).json()==first.json()
            assert conn.execute('SELECT count(*) n FROM platform.task_run_execution_authorization WHERE run_id=%s',(run['run_id'],)).fetchone()['n']==1
            job=claim(q,task,run['run_id']);assert job and claim(q,task,run['run_id']) is None
            with pytest.raises(ValueError):finish(q,{**job,'claim_token':uuid4()},'COMPLETED','HOP_EXECUTED_QA_REQUIRED')
            finish(q,job,'NEEDS_REVIEW','HOP_PREPARATION_OR_COMPARISON_FAILED')
            assert api.get(url).json()['request']['status']=='NEEDS_REVIEW'
            assert claim(q,task,run['run_id']) is None
            for sql in ("UPDATE platform.hop_dispatch_request SET status='QUEUED' WHERE run_id=%s",
                        'DELETE FROM platform.hop_dispatch_request WHERE run_id=%s'):
                with pytest.raises(psycopg.Error):
                    with conn.transaction():conn.execute(sql,(run['run_id'],))
            assert not conn.execute('SELECT write_started FROM platform.task_run WHERE run_id=%s',(run['run_id'],)).fetchone()['write_started']
        finally:conn.rollback()
