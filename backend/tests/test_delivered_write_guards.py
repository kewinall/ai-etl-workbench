"""Synthetic immutable delivery record probes; not real QA/ZIP/ETL acceptance."""
from contextlib import nullcontext
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest
from app.run_queue import RunQueue
from app.run_api import create_run_router
from app.specification_api import create_specification_router
from app.formal_release_api import create_formal_release_router
from app.sdm_store import save_candidate
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from test_workflow_write_refusals import persisted_counts


@pytest.mark.parametrize('action', ['specifications', 'specification_approve', 'sdm_candidate', 'sdm-delivery', 'release/candidate', 'prepare', 'revise', 'input_review', 'cancel', 'sa_reserve', 'developer_reserve', 'qa_reserve', 'sa_approve', 'qa_approve', 'oracle_save', 'oracle_approve', 'hop_dispatch', 'comparison_recovery', 'sa_cancel', 'execution_close', 'preparation_close'])
def test_delivered_record_stops_new_artifacts_before_gate_side_effects(context, tmp_path, monkeypatch, action):
    base, task, run, spec, naming, api = prepared(context)
    prefix = f'/api/tasks/{task}/runs/{run["run_id"]}'
    saved = api.post(prefix+'/specifications', json=spec).json()
    sid = saved['specification_id']
    assert api.post(prefix+'/specifications/'+sid+'/approve', json={'content_checksum': saved['content_checksum']}).status_code == 200
    monkeypatch.setenv('WORKBENCH_ARTIFACT_ROOT', str(tmp_path))
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self): return nullcontext(conn)
        queue = Queue(base.url)
        try:
            sdm = save_candidate(queue, task, run['run_id'], sid, saved['content_checksum'], root=tmp_path)
            candidate, check, release = uuid4(), uuid4(), uuid4()
            conn.execute('''INSERT INTO platform.release_candidate_record
                (candidate_id,run_id,task_id,project_id,sdm_id,qa_binding_checksum,checksum,file_size,manifest)
                VALUES(%s,%s,%s,%s,%s,%s,%s,100,%s)''',
                (candidate,run['run_id'],task,run['project_id'],sdm['sdm_id'],'a'*64,'b'*64,Jsonb({'synthetic_guard_fixture':True})))
            conn.execute('''INSERT INTO platform.release_portability_check
                (check_id,candidate_id,claim_token,status,evidence,checksum,finished_at)
                VALUES(%s,%s,%s,'PASS',%s,%s,clock_timestamp())''',
                (check,candidate,uuid4(),Jsonb({'synthetic_guard_fixture':True}),'c'*64))
            operator = conn.execute('SELECT operator_id FROM platform.operator_profile LIMIT 1').fetchone()['operator_id']
            conn.execute('''INSERT INTO platform.release_delivery
                (release_id,candidate_id,check_id,operator_id,binding,binding_checksum,checksum,file_size,manifest)
                VALUES(%s,%s,%s,%s,%s,%s,%s,100,%s)''',
                (release,candidate,check,operator,Jsonb({'synthetic_guard_fixture':True}),'d'*64,'e'*64,Jsonb({'status':'RELEASE_READY','synthetic_guard_fixture':True})))
            app = FastAPI()
            app.include_router(create_run_router(queue))
            app.include_router(create_specification_router(queue))
            app.include_router(create_formal_release_router(queue, object()))
            client = TestClient(app)
            before = persisted_counts(queue)
            run_before = queue.detail(task, run['run_id'])
            files_before = sorted(str(p) for p in tmp_path.rglob('*') if p.is_file())
            if action == 'specifications': body = spec
            elif action in ('specification_approve','sdm_candidate'): body = {'content_checksum':saved['content_checksum']}
            else: body = {'qa_binding_checksum':'a'*64, **({'confirmed':True} if action=='release/candidate' else {})}
            route = '/specifications/'+sid+('/approve' if action=='specification_approve' else '/sdm-candidate') if action in ('specification_approve','sdm_candidate') else '/'+action
            services = {
                'prepare': lambda: queue.enqueue(task, 'terminal-prepare'),
                'revise': lambda: queue.revise(task, run['run_id'], 'terminal-revise', run['input_checksum'], 'changed requirement', 'ai_sample', 'changed_target'),
                'input_review': lambda: queue.review(task, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE'),
                'cancel': lambda: queue.cancel_unstarted(task, run['run_id']),
            }
            from app.sa_journal import SAJournal
            from app.developer_journal import DeveloperJournal
            from app.qa_journal import QAJournal
            from app.sa_approval import approve as sa_approve
            from app.qa_approval import approve_review as qa_approve
            from app.oracle_store import save_oracle, approve_oracle
            from app.hop_dispatch import enqueue as dispatch
            from app.comparison_recovery import enqueue as recover
            from app.sa_work_queue import SAWorkQueue
            from app.execution_reconciliation import close as close_execution
            from app.hop_preparation_reconciliation import close as close_preparation
            services.update({
                'sa_cancel': lambda: SAWorkQueue(queue).cancel_queued(task, run['run_id']),
                'execution_close': lambda: close_execution(queue, task, run['run_id'], 'a'*64, None, 0, engine_stopped=True, target_checked=True, confirmed=True),
                'preparation_close': lambda: close_preparation(queue, task, run['run_id'], {'binding_checksum':'a'*64,'target_exists':False,'observed_row_count':None,'engine_stopped':True,'target_checked':True,'confirmed':True}),
                'sa_reserve': lambda: SAJournal(queue).reserve(task, run['run_id']),
                'developer_reserve': lambda: DeveloperJournal(queue).reserve(task, run['run_id'], 'a'*64, confirmed=True),
                'qa_reserve': lambda: QAJournal(queue).reserve(task, run['run_id'], uuid4(), 'a'*64, True),
                'sa_approve': lambda: sa_approve(queue, task, run['run_id'], 'a'*64, confirmed=True),
                'qa_approve': lambda: qa_approve(queue, task, run['run_id'], 'a'*64, confirmed=True),
                'oracle_save': lambda: save_oracle(queue, task, run['run_id'], sid, b'{}'),
                'oracle_approve': lambda: approve_oracle(queue, task, run['run_id'], sid, uuid4(), 'a'*64),
                'hop_dispatch': lambda: dispatch(queue, task, run['run_id'], sid, 'a'*64, True),
                'comparison_recovery': lambda: recover(queue, task, run['run_id'], 'a'*64, True),
            })
            for _ in range(2):
                if action in services:
                    with pytest.raises(ValueError, match='RUN_ALREADY_DELIVERED_READ_ONLY'):
                        services[action]()
                    assert persisted_counts(queue) == before
                    assert queue.detail(task, run['run_id']) == run_before
                    assert sorted(str(p) for p in tmp_path.rglob('*') if p.is_file()) == files_before
                    continue
                response = client.post(prefix+route, json=body)
                assert response.status_code == 409, response.text
                assert not isinstance(response.json().get('detail'), list)
                assert persisted_counts(queue) == before
                assert queue.detail(task, run['run_id']) == run_before
                assert sorted(str(p) for p in tmp_path.rglob('*') if p.is_file()) == files_before
        finally:
            # All synthetic delivery metadata and SDM writes live only in this transaction.
            # Roll back rather than disable immutable history protection or delete records.
            conn.rollback()
