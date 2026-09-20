"""Real PostgreSQL tests; synthetic rows only, external ETL never invoked."""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from app.run_queue import RunQueue, RunConflict, RunBlocked

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated Compose DB required')


@pytest.fixture
def context():
    assert os.getenv('DATABASE_HOST') == 'postgres'
    assert os.getenv('DATABASE_NAME') == 'workbench'
    queue = RunQueue(os.environ['DATABASE_URL'])
    project_id = uuid4()
    task_id = 'queue-test-' + uuid4().hex
    profile_id = 'queue-profile-' + uuid4().hex
    with queue.conn() as conn:
        assert conn.execute('SELECT current_database() AS name').fetchone()['name'] == 'workbench'
        assert conn.execute("SELECT count(*) AS n FROM platform.worker_presence WHERE activity<>'STOPPED' AND last_seen>clock_timestamp()-interval '45 seconds'").fetchone()['n'] == 0, 'Stop all native and container workers before isolated DB tests'
        assert conn.execute("SELECT count(*) AS n FROM platform.task_run WHERE state IN ('QUEUED','RUNNING','NEEDS_REVIEW')").fetchone()['n'] == 0, 'Refuse tests when other runs are active'
        previous = conn.execute("SELECT setting_value,updated_at FROM platform.system_setting WHERE setting_key='data_connections_targets'").fetchone()
        assert previous is not None
        connection = {'connection_id': 'queue-test-qa', 'host': 'synthetic-no-connection', 'port': 5433, 'database': 'synthetic', 'user': 'synthetic'}
        conn.execute("UPDATE platform.system_setting SET setting_value=%s WHERE setting_key='data_connections_targets'", (Jsonb({**previous['setting_value'], 'etl_qa': connection}),))
        conn.execute('INSERT INTO platform.ai_provider_profile(profile_id,display_name,provider_type,region,model_routes) VALUES(%s,%s,%s,%s,%s)', (profile_id, 'Synthetic queue test', 'LITELLM_BEDROCK', 'us-east-1', Jsonb({role: 'bedrock/synthetic' for role in ('requirement_gate','etl_specification','qa_review')})))
        conn.execute('INSERT INTO platform.project(project_id,project_name,default_ai_profile,default_connection) VALUES(%s,%s,%s,%s)', (project_id, str(project_id), profile_id, 'queue-test-qa'))
        conn.execute("INSERT INTO platform.task(task_id,project_id,task_name,task_type,requirement_text,status,source_type,target_type,source_config,target_config) VALUES(%s,%s,'Queue test','NEW','synthetic requirement','CREATED','CSV','VERTICA',%s,%s)", (task_id, project_id, Jsonb({'path': '/synthetic/input.csv', 'password': 'must-not-persist', 'sources': [{'type': 'CSV', 'has_actual_data': False, 'fields': [{'name': 'id', 'type': 'BIGINT'}]}], 'csv_input_contract_v1': {'version': 1, 'encoding': 'UTF-8', 'delimiter': ',', 'header': True, 'extra_columns': 'REJECT'}}), Jsonb({'schema': 'ai_sample', 'table': 'synthetic', 'requirements_v1': {'version': 1, 'write_mode': 'APPEND', 'date_scope': 'ALL'}})))
    try:
        yield queue, task_id
    finally:
        with queue.conn() as conn:
            conn.execute('DELETE FROM platform.task_run_execution_reservation WHERE run_id IN (SELECT run_id FROM platform.task_run WHERE task_id=%s)', (task_id,))
            conn.execute('DELETE FROM platform.task_run_execution_authorization WHERE run_id IN (SELECT run_id FROM platform.task_run WHERE task_id=%s)', (task_id,))
            conn.execute('DELETE FROM platform.specification_approval WHERE specification_id IN (SELECT specification_id FROM platform.specification WHERE task_id=%s)', (task_id,))
            conn.execute('DELETE FROM platform.specification WHERE task_id=%s', (task_id,))
            conn.execute('DELETE FROM platform.agent_invocation WHERE task_id=%s', (task_id,))
            conn.execute('DELETE FROM platform.task_run_approval WHERE run_id IN (SELECT run_id FROM platform.task_run WHERE task_id=%s)', (task_id,))
            conn.execute('DELETE FROM platform.task_run_event WHERE run_id IN (SELECT run_id FROM platform.task_run WHERE task_id=%s)', (task_id,))
            conn.execute('DELETE FROM platform.task_run WHERE task_id=%s', (task_id,))
            conn.execute('DELETE FROM platform.task WHERE task_id=%s', (task_id,))
            conn.execute('DELETE FROM platform.project WHERE project_id=%s', (project_id,))
            conn.execute('DELETE FROM platform.ai_provider_profile WHERE profile_id=%s', (profile_id,))
            conn.execute("UPDATE platform.system_setting SET setting_value=%s,updated_at=%s WHERE setting_key='data_connections_targets'", (Jsonb(previous['setting_value']), previous['updated_at']))


@pytest.mark.parametrize('missing_target', [False, True])
def test_control_worker_persists_gate_and_stops(context, missing_target):
    from app.control_worker import run_once
    queue, task_id = context
    if missing_target:
        with queue.conn() as conn:
            conn.execute("UPDATE platform.task SET target_config='{}'::jsonb WHERE task_id=%s", (task_id,))
    run = queue.enqueue(task_id, 'control-worker-0001')
    assert run_once(queue)['status'] == 'IDLE'
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == ('NEEDS_INPUT' if missing_target else 'CHECKED')
    saved = queue.detail(task_id, run['run_id'])
    assert saved['state'] == 'NEEDS_REVIEW'
    assert saved['phase'] == 'REQUIREMENT_GATE'
    assert saved['outcome_code'] == ('REQUIREMENT_NEEDS_INPUT' if missing_target else 'PIPELINE_NOT_READY')
    assert saved['write_started'] is False
    assert saved['lease_token'] is None
    assert saved['gate_result']['scope'] == 'INITIAL_DETERMINISTIC_CHECK_ONLY'
    assert [event['event_type'] for event in saved['events']] == ['ENQUEUED', 'INPUT_APPROVE', 'CLAIMED', 'REQUIREMENT_GATE_STARTED', saved['outcome_code']]
    assert run_once(queue)['status'] == 'IDLE'
    with pytest.raises(RunConflict):
        queue.complete_gate(run['run_id'], uuid4(), saved['gate_result'])


def test_revision_preserves_history_and_requires_new_approval(context):
    from app.control_worker import run_once
    queue, task_id = context
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET requirement_text='' WHERE task_id=%s", (task_id,))
    parent = queue.enqueue(task_id, 'revision-parent-01')
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    args = (task_id, parent['run_id'], 'revision-child-01', parent['input_checksum'], 'corrected requirement', 'ai_sample', 'corrected')
    child = queue.revise(*args)
    assert queue.revise(*args)['run_id'] == child['run_id']
    assert child['parent_run_id'] == parent['run_id']
    assert child['input_checksum'] != parent['input_checksum']
    assert child['phase'] == 'PREFLIGHT'
    assert run_once(queue)['status'] == 'IDLE'
    old = queue.detail(task_id, parent['run_id'])
    assert old['state'] == 'CANCELLED'
    assert old['input_snapshot'] == parent['input_snapshot']
    assert old['approval']['decision'] == 'APPROVE'
    assert old['gate_result']['status'] == 'NEEDS_INPUT'
    assert queue.detail(task_id, child['run_id'])['approval'] is None
    with pytest.raises(RunConflict, match='IDEMPOTENCY_KEY_REUSED'):
        queue.revise(*args[:-3], 'different requirement', 'ai_sample', 'corrected')
    queue.review(task_id, child['run_id'], child['input_checksum'], child['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    assert queue.detail(task_id, child['run_id'])['write_started'] is False
    with pytest.raises(psycopg.errors.RaiseException, match='immutable'):
        with queue.conn() as conn:
            conn.execute('UPDATE platform.task_run SET parent_run_id=NULL WHERE run_id=%s', (child['run_id'],))


def test_source_only_revision_is_persisted_and_requires_approval(context):
    from app.control_worker import run_once
    queue, task_id = context
    original = {'sources': [{'type': 'CSV', 'alias': 'synthetic', 'has_actual_data': False, 'fields': [{'name': 'id', 'type': 'BIGINT'}]}]}
    with queue.conn() as conn:
        conn.execute('UPDATE platform.task SET source_config=%s WHERE task_id=%s', (Jsonb(original), task_id))
    parent = queue.enqueue(task_id, 'source-parent-01')
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    run_once(queue)
    fields = {'fields': [{'name': 'id', 'type': 'BIGINT'}, {'name': 'created_date', 'type': 'DATE'}]}
    args = (task_id, parent['run_id'], 'source-child-01', parent['input_checksum'], parent['input_snapshot']['requirement_text'], 'ai_sample', 'synthetic', None, fields)
    child = queue.revise(*args)
    assert queue.revise(*args)['run_id'] == child['run_id']
    assert child['input_snapshot']['source_config']['sources'][0]['fields'] == fields['fields']
    assert queue.detail(task_id, parent['run_id'])['input_snapshot']['source_config'] == original
    assert run_once(queue)['status'] == 'IDLE'
    with queue.conn() as conn:
        assert conn.execute('SELECT source_config FROM platform.task WHERE task_id=%s', (task_id,)).fetchone()['source_config'] == child['input_snapshot']['source_config']


def test_revision_rejects_stale_or_running_input_without_mutation(context):
    queue, task_id = context
    parent = queue.enqueue(task_id, 'revision-parent-01')
    args = (task_id, parent['run_id'], 'revision-child-01', parent['input_checksum'], 'corrected', 'ai_sample', 'corrected')
    with pytest.raises(RunConflict, match='RUN_NOT_REVISABLE'):
        queue.revise(*args)
    queue.review(task_id, parent['run_id'], parent['input_checksum'], parent['settings_snapshot']['checksum'], 'APPROVE')
    claimed = queue.claim()
    with pytest.raises(RunConflict, match='RUN_NOT_REVISABLE'):
        queue.revise(*args)
    queue.start_gate(parent['run_id'], claimed['lease_token'])
    queue.complete_gate(parent['run_id'], claimed['lease_token'], {'status': 'CHECKED'})
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET requirement_text='other edit' WHERE task_id=%s", (task_id,))
    with pytest.raises(RunConflict, match='INPUT_OR_SETTINGS_CHANGED'):
        queue.revise(*args)
    assert len(queue.list_runs(task_id)) == 1
    assert queue.detail(task_id, parent['run_id'])['state'] == 'NEEDS_REVIEW'


@pytest.mark.parametrize('uncertain', [False, True])
def test_sa_journal_persists_intent_and_never_resends(context, uncertain):
    from app.control_worker import run_once
    from app.sa_journal import SAJournal
    queue, task_id = context
    run = queue.enqueue(task_id, 'sa-journal-0001')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    run_once(queue)
    journal = SAJournal(queue)
    assert journal.read(task_id, run['run_id'])['invocation'] is None
    reserved = journal.reserve(task_id, run['run_id'])
    visible = journal.read(task_id, run['run_id'])
    assert visible['invocation']['status'] == 'DISPATCH_RESERVED'
    assert visible['dispatch_available'] is False
    assert 'input_json' not in visible['invocation']
    with pytest.raises(ValueError, match='RUN_NOT_FOUND'):
        journal.read(task_id, uuid4())
    with pytest.raises(RunConflict, match='SA_ALREADY_RESERVED'):
        SAJournal(RunQueue(queue.url)).reserve(task_id, run['run_id'])
    if uncertain:
        journal.hold_uncertain(task_id, reserved['invocation_id'])
    else:
        ctx = reserved['context']
        payload = dict(version=1, run_id=str(run['run_id']), input_checksum=ctx['input_checksum'], context_checksum=ctx['context_checksum'], status='READY_FOR_REVIEW', summary='Synthetic response', evidence_ids=['requirement'], issues=[])
        assert journal.finish(task_id, reserved['invocation_id'], payload) == 'VALIDATED_NOT_APPROVED'
        with pytest.raises(RunConflict):
            journal.finish(task_id, reserved['invocation_id'], payload)
    with queue.conn() as conn:
        saved = conn.execute('SELECT status FROM platform.agent_invocation WHERE invocation_id=%s', (reserved['invocation_id'],)).fetchone()
    assert saved['status'] == ('OUTCOME_UNKNOWN_NEEDS_REVIEW' if uncertain else 'VALIDATED_NOT_APPROVED')
    visible = journal.read(task_id, run['run_id'])
    assert visible['invocation']['status'] == saved['status']
    assert visible['execution_authorized'] is False
    if not uncertain:
        assert visible['invocation']['review']['summary'] == 'Synthetic response'
    with pytest.raises(RunConflict, match='SA_ALREADY_RESERVED'):
        journal.reserve(task_id, run['run_id'])
    assert queue.detail(task_id, run['run_id'])['write_started'] is False


@pytest.mark.parametrize('provider_failure', [False, True])
def test_sa_dispatch_integrates_journal_gateway_and_persistence(context, provider_failure):
    import json
    from types import SimpleNamespace as NS
    from app.control_worker import run_once
    from app.sa_dispatch import dispatch_sa
    from app.run_queue import LockedSettings
    queue, task_id = context
    run = queue.enqueue(task_id, 'sa-dispatch-0001')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    run_once(queue)
    class Repo:
        def ai_profile(self, profile_id):
            with queue.conn() as conn:
                return LockedSettings(conn).ai_profile(profile_id)
    calls = []
    def provider(**kwargs):
        calls.append(1)
        if provider_failure:
            raise RuntimeError('private provider exception')
        ctx = json.loads(kwargs['messages'][1]['content'])['context']
        result = dict(version=1, run_id=ctx['run_id'], input_checksum=ctx['input_checksum'], context_checksum=ctx['context_checksum'], status='READY_FOR_REVIEW', summary='Synthetic only', evidence_ids=['requirement'], issues=[])
        return NS(choices=[NS(message=NS(content=json.dumps(result)))], usage=NS(prompt_tokens=2, completion_tokens=3, total_tokens=5))
    with pytest.raises(RunConflict, match='CONSENT_REQUIRED'):
        dispatch_sa(queue, Repo(), task_id, run['run_id'], completion=provider)
    assert calls == []
    result = dispatch_sa(queue, Repo(), task_id, run['run_id'], authorize_model_call=True, completion=provider)
    assert len(calls) == 1
    assert result['status'] == ('OUTCOME_REQUIRES_RECONCILIATION' if provider_failure else 'VALIDATED_NOT_APPROVED')
    with queue.conn() as conn:
        record = conn.execute('SELECT status,output_json FROM platform.agent_invocation WHERE invocation_id=%s', (result['invocation_id'],)).fetchone()
    assert 'private provider exception' not in str(record)
    if not provider_failure:
        assert record['output_json']['trace']['usage']['total_tokens'] == 5
    with pytest.raises(RunConflict, match='SA_ALREADY_RESERVED'):
        dispatch_sa(queue, Repo(), task_id, run['run_id'], authorize_model_call=True, completion=provider)
    assert len(calls) == 1


def test_request_idempotency_and_immutable_snapshot(context):
    queue, task_id = context
    first = queue.enqueue(task_id, 'request-0001')
    assert 'must-not-persist' not in str(first)
    assert first['settings_snapshot']['origins']['ai_profile'] == 'PROJECT'
    assert queue.enqueue(task_id, 'request-0001')['run_id'] == first['run_id']
    with pytest.raises(RunConflict, match='ACTIVE_RUN_EXISTS'):
        queue.enqueue(task_id, 'request-0002')
    with pytest.raises(RunConflict, match='IDEMPOTENCY_KEY_REUSED'):
        queue.enqueue(task_id, 'request-0001', {'connection_id': 'other'})
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET requirement_text='later revision' WHERE task_id=%s", (task_id,))
    assert queue.enqueue(task_id, 'request-0001')['input_snapshot']['requirement_text'] == 'synthetic requirement'
    with pytest.raises(psycopg.errors.RaiseException, match='immutable'):
        with queue.conn() as conn:
            conn.execute("UPDATE platform.task_run SET input_snapshot='{}'::jsonb WHERE run_id=%s", (first['run_id'],))


def test_parallel_workers_claim_only_once(context):
    queue, task_id = context
    queued = queue.enqueue(task_id, 'request-0001')
    assert queue.claim() is None
    queue.review(task_id, queued['run_id'], queued['input_checksum'], queued['settings_snapshot']['checksum'], 'APPROVE')
    with ThreadPoolExecutor(max_workers=4) as executor:
        claims = list(executor.map(lambda _: queue.claim(), range(4)))
    claimed = [row for row in claims if row]
    assert len(claimed) == 1
    run = claimed[0]
    assert run['run_id'] == queued['run_id']
    queue.heartbeat(run['run_id'], run['lease_token'])
    with pytest.raises(RunConflict, match='LEASE_LOST'):
        queue.heartbeat(run['run_id'], uuid4())
    queue.finish(run['run_id'], run['lease_token'], 'SUCCEEDED')
    with pytest.raises(RunConflict, match='LEASE_LOST'):
        queue.finish(run['run_id'], run['lease_token'], 'SUCCEEDED')
    with queue.conn() as conn:
        events = conn.execute('SELECT event_type FROM platform.task_run_event WHERE run_id=%s ORDER BY event_id', (run['run_id'],)).fetchall()
    assert [row['event_type'] for row in events] == ['ENQUEUED','INPUT_APPROVE','CLAIMED','SUCCEEDED']


def test_expired_write_never_requeues_or_accepts_stale_owner(context):
    queue, task_id = context
    queued = queue.enqueue(task_id, 'request-0001')
    queue.review(task_id, queued['run_id'], queued['input_checksum'], queued['settings_snapshot']['checksum'], 'APPROVE')
    run = queue.claim()
    # Simulate a previously-started write only in the isolated fixture. Input
    # approval alone must no longer authorize starting external writes.
    with pytest.raises(RunConflict):
        queue.begin_external_write(run['run_id'], run['lease_token'])
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task_run SET write_started=true,phase='HOP_EXECUTION',lease_until=now()-interval '1 second' WHERE run_id=%s", (run['run_id'],))
    assert queue.reap_expired() == 1
    assert queue.reap_expired() == 0
    assert queue.claim() is None
    with pytest.raises(RunConflict, match='LEASE_LOST'):
        queue.finish(run['run_id'], run['lease_token'], 'SUCCEEDED')
    with pytest.raises(RunConflict, match='ACTIVE_RUN_EXISTS'):
        queue.enqueue(task_id, 'request-0002')
    persisted = RunQueue(queue.url).enqueue(task_id, 'request-0001')
    assert persisted['state'] == 'NEEDS_REVIEW'
    assert persisted['write_started'] is True
    assert persisted['outcome_code'] == 'HOP_RESULT_UNKNOWN'
    detail = queue.detail(task_id, run['run_id'])
    assert detail['events'][-1]['event_context'] == {'outcome_code':'HOP_RESULT_UNKNOWN', 'external_write_may_have_occurred':True, 'automatic_retry_allowed':False}


def test_missing_settings_does_not_enqueue(context):
    queue, task_id = context
    with pytest.raises(RunBlocked):
        queue.enqueue(task_id, 'request-0001', {'ai_profile_id': 'does-not-exist'})
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) AS n FROM platform.task_run WHERE task_id=%s', (task_id,)).fetchone()['n'] == 0


def test_changed_input_rejects_old_confirmation(context):
    queue, task_id = context
    run = queue.enqueue(task_id, 'request-0001')
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET requirement_text='new requirement' WHERE task_id=%s", (task_id,))
    with pytest.raises(RunConflict, match='INPUT_OR_SETTINGS_CHANGED'):
        queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    assert queue.detail(task_id, run['run_id'])['matches_current'] is False
    queue.cancel_unstarted(task_id, run['run_id'])
    new = queue.enqueue(task_id, 'request-0002')
    assert new['input_checksum'] != run['input_checksum']


def test_profile_change_invalidates_approved_run_before_claim(context):
    queue, task_id = context
    run = queue.enqueue(task_id, 'request-0001')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    with queue.conn() as conn:
        conn.execute("UPDATE platform.ai_provider_profile SET region='us-west-2' WHERE profile_id=%s", (run['settings_snapshot']['ai_profile_id'],))
    with pytest.raises(RunConflict, match='INPUT_OR_SETTINGS_CHANGED'):
        queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    assert queue.claim() is None
    result = queue.detail(task_id, run['run_id'])
    assert result['state'] == 'NEEDS_REVIEW'
    assert result['outcome_code'] == 'INPUT_OR_SETTINGS_CHANGED'


def test_review_idempotency_and_rejection(context):
    queue, task_id = context
    run = queue.enqueue(task_id, 'request-0001')
    args = (task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'])
    first = queue.review(*args, 'REJECT')
    assert queue.review(*args, 'REJECT')['approval_id'] == first['approval_id']
    with pytest.raises(RunConflict, match='REVIEW_ALREADY_RECORDED'):
        queue.review(*args, 'APPROVE')
    assert queue.detail(task_id, run['run_id'])['state'] == 'CANCELLED'
    assert queue.claim() is None


def test_changes_after_claim_block_external_write(context):
    queue, task_id = context
    run = queue.enqueue(task_id, 'request-0001')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    claimed = queue.claim()
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET requirement_text='changed after claim' WHERE task_id=%s", (task_id,))
    with pytest.raises(RunConflict, match='INPUT_OR_SETTINGS_CHANGED'):
        queue.begin_external_write(claimed['run_id'], claimed['lease_token'])
    assert queue.detail(task_id, run['run_id'])['write_started'] is False
