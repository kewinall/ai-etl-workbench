"""Real isolated PostgreSQL, synthetic provider, rollback all test handoffs."""
from contextlib import nullcontext
from uuid import uuid4
import pytest
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.developer_api import create_developer_router
from app.local_developer_bridge import handle
from app.run_queue import RunQueue
from app.sa_journal import SAJournal
from app.sa_approval import read, approve
from app.developer_contract import load_context
from app.developer_gateway import developer_material
from app.developer_journal import DeveloperJournal
from app.sa_contract import digest
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark


@pytest.mark.parametrize('outcome', ['success', 'stale', 'unknown'])
@pytest.mark.parametrize('version', [1, 2])
def test_developer_single_consumption_atomic_save(context, outcome, monkeypatch, version):
    base, task = context
    with base.conn() as conn:
        conn.execute("""UPDATE platform.ai_provider_profile SET provider_type='LOCAL_COPILOT',region=NULL,
            model_routes='{"requirement_gate":"test-model","etl_specification":"test-model","qa_review":"test-model"}'::jsonb
            WHERE profile_id=(SELECT default_ai_profile FROM platform.project p JOIN platform.task t USING(project_id) WHERE t.task_id=%s)""", (task,))
    from test_join_semantics import join_design
    base, task, run, spec, naming, _ = (prepared(context, design_factory=join_design)
                                      if version == 2 else prepared(context))
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self): return nullcontext(conn)
        q = Queue(base.url)
        app = FastAPI(); app.include_router(create_developer_router(q)); api = TestClient(app)
        url = f'/api/tasks/{task}/runs/{run["run_id"]}/developer'
        try:
            sa = SAJournal(q); reserved = sa.reserve(task, run['run_id']); ctx = reserved['context']
            sa.finish(task, reserved['invocation_id'], dict(version=1, run_id=str(run['run_id']),
                input_checksum=run['input_checksum'], context_checksum=ctx['context_checksum'],
                status='READY_FOR_REVIEW', summary='Synthetic review', evidence_ids=['requirement'], issues=[]))
            approve(q, task, run['run_id'], read(q, task, run['run_id'])['binding']['checksum'], confirmed=True)
            captured = load_context(q, conn, task, run['run_id']); ctx = captured['context']
            material = developer_material(ctx)
            assert ctx['version'] == version
            offer = api.get(url).json(); assert offer['eligible']
            body = {k:offer[k] for k in ('model','prompt_checksum','schema_checksum')}
            body.update(confirmed=True, context_checksum=ctx['context_checksum'])
            monkeypatch.setenv('WORKBENCH_DEVELOPER_DISPATCH_ENABLED','false')
            assert api.post(url+'/authorize', json=body).status_code == 409
            monkeypatch.setenv('WORKBENCH_DEVELOPER_DISPATCH_ENABLED','true')
            assert api.post(url+'/authorize', json={**body,'confirmed':False}).status_code == 409
            assert api.post(url+'/authorize', json={**body,'model':'copilot/changed'}).status_code == 409
            assert api.post(url+'/authorize', json={**body,'context_checksum':'0'*64}).status_code == 409
            journal = DeveloperJournal(q)
            with pytest.raises(ValueError, match='CONSENT'):
                journal.reserve(task, run['run_id'], ctx['context_checksum'])
            response = api.post(url+'/authorize', json=body); assert response.status_code == 200
            intent = response.json()
            saved_intent = conn.execute('SELECT * FROM platform.agent_invocation WHERE invocation_id=%s',
                                        (intent['invocation_id'],)).fetchone()
            assert saved_intent['prompt_version'] == material['prompt_version']
            for key in ('prompt', 'prompt_checksum', 'schema', 'schema_checksum'):
                assert saved_intent['input_json'][key] == material[key]
            assert offer['schema_checksum'] == material['schema_checksum']
            assert offer['prompt_checksum'] == material['prompt_checksum']
            assert api.post(url+'/authorize', json=body).json() == intent
            assert journal.reserve(task, run['run_id'], ctx['context_checksum'], confirmed=True) == intent
            identity = intent['invocation_id']; token = journal.claim(task, identity)
            assert api.get(url).json()['invocation']['status'] == 'DEVELOPER_RESERVED'
            with pytest.raises(ValueError, match='ALREADY_CONSUMED'):
                handle(q, {'action':'claim','task_id':task,'run_id':str(run['run_id'])})
            with pytest.raises(ValueError, match='ALREADY_CONSUMED'): journal.claim(task, identity)
            with pytest.raises(ValueError, match='EXPIRED_OR_LOST'): journal.check(task, identity, uuid4())
            assert journal.check(task, identity, token)['context'] == ctx
            proposal = dict(version=version, context_checksum=ctx['context_checksum'], summary='Synthetic design',
                            evidence_ids=(['requirement', 'join.conditions', 'sources.csv_inputs']
                                          if version == 2 else ['requirement']), specification=spec)
            settings = captured['run']['settings_snapshot']
            trace = dict(provider=settings['ai']['provider_type'], model=settings['model_routes']['etl_specification'],
                prompt_version=material['prompt_version'], run_id=str(run['run_id']), input_checksum=run['input_checksum'],
                context_checksum=ctx['context_checksum'], prompt_checksum=material['prompt_checksum'],
                schema_checksum=material['schema_checksum'], output_checksum=digest(proposal),
                status='VALIDATED_NOT_APPROVED', duration_ms=1, usage={'cli_sessions':1, 'automatic_retries':0,
                    'tool_execution_count':0, 'ai_credits':0.25, 'output_tokens':123})
            before = conn.execute('SELECT count(*) n FROM platform.specification WHERE task_id=%s', (task,)).fetchone()['n']
            if outcome == 'unknown':
                journal.hold_uncertain(task, identity, token)
            else:
                if outcome == 'stale':
                    conn.execute("UPDATE platform.task SET requirement_text=requirement_text||' changed' WHERE task_id=%s", (task,))
                result = journal.finish(task, identity, token, proposal, trace)
                assert not result['execution_authorized'] and not result['release_ready']
                if outcome == 'success':
                    assert result['status'] == 'VALIDATED_NOT_APPROVED'
                    assert result['specification']['status'] == 'SAVED_NOT_EXECUTABLE'
                else:
                    assert result['status'] == 'STALE_RESULT_NEEDS_REVIEW' and result['specification'] is None
            if outcome != 'success':
                assert conn.execute('SELECT count(*) n FROM platform.specification WHERE task_id=%s', (task,)).fetchone()['n'] == before
            with pytest.raises(ValueError): journal.claim(task, identity)
            with pytest.raises(ValueError): journal.finish(task, identity, token, proposal, trace)
            history = api.get(url); assert history.status_code == 200
            if outcome != 'unknown':
                assert history.json()['invocation']['usage']['ai_credits'] == 0.25
                assert 'prompt' not in history.json()['invocation']
            for sql in ('UPDATE platform.agent_invocation SET status=status WHERE invocation_id=%s',
                        'DELETE FROM platform.agent_invocation WHERE invocation_id=%s',
                        'DELETE FROM platform.developer_dispatch_claim WHERE invocation_id=%s'):
                with pytest.raises(psycopg.Error):
                    with conn.transaction(): conn.execute(sql, (identity,))
        finally:
            conn.rollback()
