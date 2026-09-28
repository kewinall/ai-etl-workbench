"""Actual isolated control DB; synthetic model responses, never a provider call."""
from contextlib import nullcontext
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from app import task_uploads
from app.json_source_profile import confirmed_json_profile
from app.json_contract_binding import validated_json_contract
from app.sa_contract import build_sa_context, digest
from app.sa_gateway import sa_material
from app.sa_journal import SAJournal
from app.sa_work_queue import SAWorkQueue, authorization_offer
from app.sa_approval import read, approve
from app.developer_contract import load_context
from app.developer_gateway import developer_material
from app.developer_journal import DeveloperJournal
from app.run_queue import RunQueue
from app.execution_authorization import offer
from test_run_queue_integration import context, pytestmark
from test_specification_api_integration import prepared
from test_json_specification import json_design, CONTENT


def prepared_json(context, tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    spec, template, naming = json_design()
    upload = task_uploads.save_and_profile('synthetic.json', CONTENT)
    profile = confirmed_json_profile(upload['upload_id'], upload['checksum'], upload['size'])
    source = {**upload, **profile, 'type': 'JSON', 'has_actual_data': True}
    source.pop('sample_rows', None)
    config = template['input_snapshot']['source_config']
    config['sources'] = [source]
    spec['json_source'] = validated_json_contract(config)['reference']
    queue, task_id = context
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET source_type='JSON' WHERE task_id=%s", (task_id,))
    return prepared(context, design_factory=lambda: deepcopy((spec, template, naming)))


def test_json_api_preview_save_approval_history_and_runtime_block(context, tmp_path, monkeypatch):
    queue, task, run, spec, naming, api = prepared_json(context, tmp_path, monkeypatch)
    base = f'/api/tasks/{task}/runs/{run["run_id"]}'
    editor = api.get(base + '/specification/editor-context').json()
    assert editor['status'] == 'EDITOR_CONTEXT_READY'
    assert editor['binding']['version'] == 5 and editor['binding']['json_source'] == spec['json_source']
    for route in ('validate', 'compile-preview'):
        response = api.post(base + '/specification/' + route, json=spec)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['status'] == 'VALIDATED_NOT_APPROVED' and not result['execution_authorized']
        if route == 'compile-preview':
            assert 'SOURCE_JSON=' in result['parameters'] and 'SOURCE_CSV' not in result['parameters']
            assert 'HOP_JSON_INPUT_INCLUDE_NULLS=Y' in result['parameters']
            assert not result['qa_passed'] and not result['release_ready']
    wrong = deepcopy(spec); wrong['json_source']['profile_checksum'] = 'f' * 64
    assert api.post(base + '/specifications', json=wrong).json()['status'] == 'INVALID'
    assert api.get(base + '/specifications').json()['items'] == []
    saved = api.post(base + '/specifications', json=spec).json()
    approval = api.post(base + '/specifications/' + saved['specification_id'] + '/approve',
                        json={'content_checksum': saved['content_checksum']})
    assert approval.status_code == 200, approval.text
    history = api.get(base + '/specifications').json()['items']
    assert len(history) == 1 and history[0]['approval_effective'] is True
    assert history[0]['spec_json'] == spec
    assert api.get(base + '/specifications/' + saved['specification_id'] + '/sdm-preview').status_code == 409
    with queue.conn() as conn:
        with pytest.raises(ValueError, match='JSON_EXECUTION_NOT_READY'):
            offer(queue, conn, task, run['run_id'], saved['specification_id'])
        conn.execute("UPDATE platform.task SET requirement_text=requirement_text||' changed' WHERE task_id=%s", (task,))
    historical = api.get(base + '/specifications').json()['items'][0]
    assert historical['approval_id'] and not historical['approval_effective']
    assert not queue.detail(task, run['run_id'])['write_started']


@pytest.mark.parametrize('stale', [False, True])
def test_json_sa_claim_material_is_exact_and_not_repeated(context, tmp_path, monkeypatch, stale):
    queue, task, run, *_ = prepared_json(context, tmp_path, monkeypatch)
    run = queue.detail(task, run['run_id'])
    material = sa_material(build_sa_context(run))
    work = SAWorkQueue(queue)
    auth = authorization_offer(run)
    reserved = work.enqueue(task, run['run_id'], auth)
    assert reserved['status'] == 'SA_QUEUED'
    with queue.conn() as conn:
        row = conn.execute('SELECT * FROM platform.agent_invocation WHERE invocation_id=%s', (reserved['invocation_id'],)).fetchone()
    assert row['prompt_version'] == 8 and row['input_json']['context']['version'] == 6
    assert row['input_json']['prompt_checksum'] == auth['prompt_checksum'] == material['prompt_checksum']
    if stale:
        monkeypatch.setattr('app.sa_work_queue.sa_material', lambda context: {**material, 'prompt_version': 9})
    claim = work.claim()
    assert claim['status'] == ('STALE_NOT_DISPATCHED' if stale else 'DISPATCH_RESERVED')
    assert work.claim() is None
    assert not queue.detail(task, run['run_id'])['write_started']


@pytest.mark.parametrize('stale', [False, True])
def test_json_developer_atomic_handoff_has_no_automatic_approval(context, tmp_path, monkeypatch, stale):
    base, task, run, spec, naming, _ = prepared_json(context, tmp_path, monkeypatch)
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self): return nullcontext(conn)
        queue = Queue(base.url)
        try:
            sa = SAJournal(queue); reserved = sa.reserve(task, run['run_id']); ctx = reserved['context']
            review = dict(version=1, run_id=str(run['run_id']), input_checksum=run['input_checksum'],
                context_checksum=ctx['context_checksum'], status='READY_FOR_REVIEW', summary='Synthetic review',
                evidence_ids=['requirement', 'source.0.json_input'], issues=[])
            sa.finish(task, reserved['invocation_id'], review)
            approve(queue, task, run['run_id'], read(queue, task, run['run_id'])['binding']['checksum'], confirmed=True)
            captured = load_context(queue, conn, task, run['run_id']); ctx = captured['context']
            assert ctx['version'] == 5
            material = developer_material(ctx)
            journal = DeveloperJournal(queue)
            intent = journal.reserve(task, run['run_id'], ctx['context_checksum'], confirmed=True)
            identity = intent['invocation_id']; token = journal.claim(task, identity)
            stored = conn.execute('SELECT * FROM platform.agent_invocation WHERE invocation_id=%s', (identity,)).fetchone()
            assert stored['prompt_version'] == material['prompt_version'] == 8
            assert stored['input_json']['schema'] == material['schema']
            payload = dict(version=5, context_checksum=ctx['context_checksum'], summary='Synthetic design',
                evidence_ids=['requirement', 'source.0.json_input'], specification=spec)
            trace = dict(provider=stored['provider'], model=stored['model'], prompt_version=8,
                run_id=str(run['run_id']), input_checksum=run['input_checksum'], context_checksum=ctx['context_checksum'],
                prompt_checksum=material['prompt_checksum'], schema_checksum=material['schema_checksum'],
                output_checksum=digest(payload), status='VALIDATED_NOT_APPROVED', duration_ms=1,
                usage={'input_tokens': 3, 'output_tokens': 4, 'total_tokens': 7})
            if stale:
                conn.execute("UPDATE platform.task SET requirement_text=requirement_text||' changed' WHERE task_id=%s", (task,))
            result = journal.finish(task, identity, token, payload, trace)
            assert result['status'] == ('STALE_RESULT_NEEDS_REVIEW' if stale else 'VALIDATED_NOT_APPROVED')
            assert not result['execution_authorized'] and not result['release_ready']
            assert (result['specification'] is None) == stale
            assert conn.execute('SELECT count(*) n FROM platform.specification WHERE task_id=%s', (task,)).fetchone()['n'] == (0 if stale else 1)
            assert conn.execute('SELECT count(*) n FROM platform.specification_approval a JOIN platform.specification s USING(specification_id) WHERE s.run_id=%s', (run['run_id'],)).fetchone()['n'] == 0
            with pytest.raises(ValueError): journal.claim(task, identity)
        finally:
            conn.rollback()
