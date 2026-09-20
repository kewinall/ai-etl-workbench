"""Real isolated PostgreSQL and API; provider responses remain synthetic."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_run_queue_integration import context
from app.control_worker import run_once as gate_once
from app.run_queue import RunConflict, RunQueue, LockedSettings
from app.run_api import create_run_router
from app.sa_work_queue import SAWorkQueue, authorization_offer
from app.sa_journal import SAJournal
from app.sa_worker import run_once

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated Compose DB required')


def prepared(context):
    queue, task_id = context
    run = queue.enqueue(task_id, 'sa-async-0001')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    assert gate_once(queue)['status'] == 'CHECKED'
    return queue, task_id, queue.detail(task_id, run['run_id'])


def test_authorization_api_is_version_bound_idempotent_and_immutable(context, monkeypatch):
    queue, task_id, run = prepared(context)
    app = FastAPI()
    app.include_router(create_run_router(queue))
    api = TestClient(app)
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/sa-authorization'
    offer = api.get(url).json()
    assert offer['eligible'] is True
    authorization = offer['authorization']
    monkeypatch.setenv('WORKBENCH_SA_DISPATCH_ENABLED', 'false')
    assert api.post(url, json=authorization).status_code == 503
    monkeypatch.setenv('WORKBENCH_SA_DISPATCH_ENABLED', 'true')
    assert api.post(url, json={**authorization, 'consent': 'true'}).status_code == 422
    assert api.post(url, json={**authorization, 'consent': False}).status_code == 409
    assert api.post(url, json={**authorization, 'context_checksum': 'a'*64}).status_code == 409
    result = api.post(url, json=authorization)
    assert result.status_code == 202
    assert result.json()['status'] == 'SA_QUEUED'
    assert api.post(url, json=authorization).json() == result.json()
    with queue.conn() as conn:
        record = conn.execute('SELECT * FROM platform.agent_invocation WHERE run_id=%s', (run['run_id'],)).fetchone()
        assert record['input_json']['authorization'] == authorization
        assert record['input_json']['operator_id']
        assert record['claim_token'] is None
    with pytest.raises(psycopg.errors.RaiseException, match='immutable'):
        with queue.conn() as conn:
            conn.execute("UPDATE platform.agent_invocation SET input_json='{}'::jsonb WHERE run_id=%s", (run['run_id'],))


def test_parallel_claim_expiry_restart_does_not_replay(context):
    queue, task_id, run = prepared(context)
    work = SAWorkQueue(queue)
    offer = authorization_offer(run)
    work.enqueue(task_id, run['run_id'], offer)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = [row for row in pool.map(lambda _: SAWorkQueue(RunQueue(queue.url)).claim(), range(4)) if row]
    assert len(claims) == 1
    record = claims[0]
    assert record['status'] == 'DISPATCH_RESERVED'
    with pytest.raises(RunConflict, match='SA_LEASE_LOST'):
        work.heartbeat(record['invocation_id'], uuid4())
    with queue.conn() as conn:
        conn.execute("UPDATE platform.agent_invocation SET lease_until=clock_timestamp()-interval '1 second' WHERE invocation_id=%s", (record['invocation_id'],))
    restarted = SAWorkQueue(RunQueue(queue.url))
    assert restarted.reap_expired() == 1
    assert restarted.reap_expired() == 0
    assert restarted.claim() is None
    assert restarted.enqueue(task_id, run['run_id'], offer)['status'] == 'OUTCOME_UNKNOWN_NEEDS_REVIEW'
    assert restarted.claim() is None
    assert queue.detail(task_id, run['run_id'])['write_started'] is False


def test_changed_settings_before_claim_never_dispatch(context):
    queue, task_id, run = prepared(context)
    work = SAWorkQueue(queue)
    work.enqueue(task_id, run['run_id'], authorization_offer(run))
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET requirement_text='new input' WHERE task_id=%s", (task_id,))
    assert work.claim()['status'] == 'STALE_NOT_DISPATCHED'
    assert work.claim() is None
    assert SAJournal(queue).read(task_id, run['run_id'])['invocation']['status'] == 'STALE_NOT_DISPATCHED'


def test_queued_cancellation_is_idempotent_and_cannot_be_resubmitted(context):
    queue, task_id, run = prepared(context)
    work = SAWorkQueue(queue)
    offer = authorization_offer(run)
    work.enqueue(task_id, run['run_id'], offer)
    cancelled = work.cancel_queued(task_id, run['run_id'])
    assert work.cancel_queued(task_id, run['run_id']) == cancelled
    assert work.enqueue(task_id, run['run_id'], offer)['status'] == 'CANCELLED_NOT_DISPATCHED'
    assert work.claim() is None


def test_sa_need_input_is_not_reported_as_requirement_success(context):
    queue, task_id, run = prepared(context)
    journal = SAJournal(queue)
    reserved = journal.reserve(task_id, run['run_id'])
    ctx = reserved['context']
    review = dict(version=1, run_id=ctx['run_id'], input_checksum=ctx['input_checksum'], context_checksum=ctx['context_checksum'],
                  status='NEEDS_INPUT', summary='Synthetic missing requirement', evidence_ids=['requirement'],
                  issues=[{'issue_type': 'MISSING', 'message': 'CSV format is not defined', 'evidence_ids': ['requirement']}])
    assert journal.finish(task_id, reserved['invocation_id'], review) == 'VALIDATED_NOT_APPROVED'
    stored = queue.detail(task_id, run['run_id'])
    assert stored['outcome_code'] == 'SA_REQUIREMENT_NEEDS_INPUT'
    assert stored['state'] == 'NEEDS_REVIEW' and stored['write_started'] is False


def test_claimed_work_cannot_be_cancelled_as_unbilled(context):
    queue, task_id, run = prepared(context)
    work = SAWorkQueue(queue)
    work.enqueue(task_id, run['run_id'], authorization_offer(run))
    work.claim()
    with pytest.raises(RunConflict, match='SA_ALREADY_CLAIMED'):
        work.cancel_queued(task_id, run['run_id'])


@pytest.mark.parametrize('failure', [False, True])
def test_async_worker_persists_provider_result_and_does_not_repeat(context, failure):
    queue, task_id, run = prepared(context)
    work = SAWorkQueue(queue)
    work.enqueue(task_id, run['run_id'], authorization_offer(run))
    class Repo:
        def ai_profile(self, profile_id):
            with queue.conn() as conn:
                return LockedSettings(conn).ai_profile(profile_id)
    calls = []
    def provider(**kwargs):
        calls.append(kwargs['max_tokens'])
        if failure:
            raise RuntimeError('private provider error')
        ctx = json.loads(kwargs['messages'][1]['content'])['context']
        result = dict(version=1, run_id=ctx['run_id'], input_checksum=ctx['input_checksum'], context_checksum=ctx['context_checksum'], status='READY_FOR_REVIEW', summary='Synthetic asynchronous response', evidence_ids=['requirement'], issues=[])
        return NS(choices=[NS(message=NS(content=json.dumps(result)))], usage=NS(prompt_tokens=2, completion_tokens=3, total_tokens=5))
    outcome = run_once(queue, Repo(), completion=provider)
    assert outcome['status'] == ('OUTCOME_REQUIRES_RECONCILIATION' if failure else 'VALIDATED_NOT_APPROVED')
    assert run_once(queue, Repo(), completion=provider)['status'] == 'IDLE'
    assert calls == [2048]
    record = SAJournal(queue).read(task_id, run['run_id'])['invocation']
    assert 'private provider error' not in str(record)
    if not failure:
        assert record['usage']['total_tokens'] == 5
        assert record['review']['summary'] == 'Synthetic asynchronous response'
        assert queue.detail(task_id, run['run_id'])['outcome_code'] == 'SA_REVIEW_REQUIRES_APPROVAL'


def test_expired_lease_prevents_next_transient_retry(context):
    queue, task_id, run = prepared(context)
    SAWorkQueue(queue).enqueue(task_id, run['run_id'], authorization_offer(run))
    class Repo:
        def ai_profile(self, profile_id):
            with queue.conn() as conn:
                return LockedSettings(conn).ai_profile(profile_id)
    calls = []
    def interrupted(**kwargs):
        calls.append(1)
        with queue.conn() as conn:
            conn.execute("UPDATE platform.agent_invocation SET lease_until=clock_timestamp()-interval '1 second' WHERE run_id=%s", (run['run_id'],))
        raise TimeoutError('synthetic timeout')
    assert run_once(queue, Repo(), completion=interrupted)['status'] == 'OUTCOME_REQUIRES_RECONCILIATION'
    assert calls == [1]
    assert SAWorkQueue(queue).claim() is None


def test_local_copilot_bridge_is_scoped_and_docker_worker_cannot_claim(context, monkeypatch):
    from app.local_sa_bridge import handle
    queue, task_id = context
    with queue.conn() as conn:
        conn.execute("UPDATE platform.ai_provider_profile SET provider_type='LOCAL_COPILOT',region=NULL,model_routes=%s WHERE profile_id=(SELECT default_ai_profile FROM platform.project WHERE project_id=(SELECT project_id FROM platform.task WHERE task_id=%s))", (Jsonb({role: 'gpt-5.4' for role in ('requirement_gate','etl_specification','qa_review')}), task_id))
    queue, task_id, run = prepared(context)
    work = SAWorkQueue(queue)
    offer = authorization_offer(run)
    assert offer['policy_version'] == 'copilot-cli-once-v1'
    work.enqueue(task_id, run['run_id'], offer)
    assert work.claim() is None
    monkeypatch.setenv('WORKBENCH_SA_DISPATCH_ENABLED', 'true')
    identity = {'task_id': task_id, 'run_id': str(run['run_id'])}
    record = handle(queue, {**identity, 'action': 'claim'})
    assert record['status'] == 'DISPATCH_RESERVED'
    assert 'settings_snapshot' not in record and 'synthetic-no-connection' not in str(record)
    identity.update(invocation_id=str(record['invocation_id']), claim_token=str(record['claim_token']))
    assert handle(queue, {**identity, 'action': 'heartbeat'})['status'] == 'LEASE_ACTIVE'
    ctx = record['input_json']['context']
    review = dict(version=1, run_id=ctx['run_id'], input_checksum=ctx['input_checksum'], context_checksum=ctx['context_checksum'], status='READY_FOR_REVIEW', summary='Synthetic local result', evidence_ids=['requirement'], issues=[])
    assert handle(queue, {**identity, 'action': 'finish', 'review': review, 'trace': {'model': record['model']}})['status'] == 'VALIDATED_NOT_APPROVED'
    assert handle(queue, {**identity, 'action': 'claim'})['status'] == 'IDLE'
