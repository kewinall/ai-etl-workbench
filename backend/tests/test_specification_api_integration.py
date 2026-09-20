"""Actual PostgreSQL/API preview verification, not model or Hop E2E."""
import os
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest
import psycopg
from test_run_queue_integration import context
from test_etl_specification import design
from app.control_worker import run_once
from app.specification_api import create_specification_router

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated Compose DB required')


def prepared(context, source_override=None):
    queue, task_id = context
    spec, template, naming = design()
    snapshot = template['input_snapshot']
    if source_override is not None:
        snapshot['source_config']['sources'] = [source_override]
    with queue.conn() as conn:
        conn.execute('UPDATE platform.task SET requirement_text=%s,source_config=%s,target_config=%s WHERE task_id=%s', (snapshot['requirement_text'], Jsonb(snapshot['source_config']), Jsonb(snapshot['target_config']), task_id))
        conn.execute("INSERT INTO platform.naming_contract(contract_id,task_id,version,status,contract_json,checksum,confirmed_at) VALUES(%s,%s,1,'CONFIRMED',%s,%s,now())", (naming['contract_id'], task_id, Jsonb(naming['contract_json']), naming['checksum']))
    run = queue.enqueue(task_id, 'spec-preview-0001')
    queue.review(task_id, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    spec.update(run_id=str(run['run_id']), input_checksum=run['input_checksum'], settings_checksum=run['settings_snapshot']['checksum'])
    app = FastAPI(); app.include_router(create_specification_router(queue))
    return queue, task_id, run, spec, naming, TestClient(app)


@pytest.mark.parametrize('action', ['validate', 'compile-preview'])
def test_preview_uses_saved_contract_and_never_persists_or_dispatches(context, action):
    queue, task_id, run, spec, naming, api = prepared(context)
    before = queue.detail(task_id, run['run_id'])
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specification/{action}'
    response = api.post(url, json=spec)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    assert result['execution_authorized'] is False
    assert result['compiler_status'] == ('PLAN_ONLY_HPL_NOT_GENERATED' if action == 'validate' else 'DELIVERY_COMPONENTS_NOT_RELEASED')
    if action == 'compile-preview':
        from hashlib import sha256
        from xml.etree.ElementTree import fromstring
        assert sha256(result['hpl'].encode()).hexdigest() == result['hpl_checksum']
        assert sha256(result['hwf'].encode()).hexdigest() == result['hwf_checksum']
        assert sha256(result['ddl'].encode()).hexdigest() == result['ddl_checksum']
        assert '"amount"' not in result['ddl']
        assert '"total_amount" NUMERIC(18,2)' in result['ddl']
        assert result['qa_passed'] is False and result['release_ready'] is False
        assert result['hpl_checksum'] in fromstring(result['hwf']).findtext('description')
        assert len(fromstring(result['hpl']).findall('transform')) == 7
        assert 'RUNTIME_CONNECTION_BINDING' in result['required_checks']
    assert api.post(url, json=spec).json() == result
    assert queue.detail(task_id, run['run_id']) == before
    with queue.conn() as conn:
        for table in ('specification', 'hop_artifact', 'agent_invocation'):
            assert conn.execute(f'SELECT count(*) AS n FROM platform.{table} WHERE task_id=%s', (task_id,)).fetchone()['n'] == 0
    assert api.post(url, json={**spec, 'sql': 'SELECT 1'}).status_code == 422
    assert api.post(url, json={**spec, 'run_id': str(uuid4())}).status_code == 409
    assert api.post(url.replace(task_id, 'not-this-task'), json=spec).status_code == 404


@pytest.mark.parametrize('action', ['validate', 'compile-preview'])
def test_newer_draft_cannot_fall_back_to_older_confirmed_naming(context, action):
    queue, task_id, run, spec, naming, api = prepared(context)
    with queue.conn() as conn:
        conn.execute("INSERT INTO platform.naming_contract(contract_id,task_id,version,status,contract_json,checksum) VALUES(%s,%s,2,'DRAFT',%s,%s)", (uuid4(), task_id, Jsonb(naming['contract_json']), naming['checksum']))
    result = api.post(f'/api/tasks/{task_id}/runs/{run["run_id"]}/specification/{action}', json=spec).json()
    assert result['status'] == 'INVALID'
    assert {'SPEC_NAMING_UNCONFIRMED', 'SPEC_NAMING_VERSION_MISMATCH'} <= {issue['code'] for issue in result['issues']}
    assert 'plan' not in result
    assert 'hpl' not in result


def test_saved_revision_approval_and_supersession_preserve_history(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    before = queue.detail(task_id, run['run_id'])
    saved = api.post(url, json=spec)
    assert saved.status_code == 200, saved.text
    first = saved.json()
    assert first['version'] == 1 and first['execution_authorized'] is False
    assert api.get(url).json()['items'][0]['reviewable'] is True
    assert api.post(url, json=spec).json() == first
    approve_url = url + '/' + first['specification_id'] + '/approve'
    body = {'content_checksum': first['content_checksum']}
    assert api.post(approve_url, json={'content_checksum': 'c'*64}).status_code == 409
    approval = api.post(approve_url, json=body)
    assert approval.status_code == 200, approval.text
    assert api.post(approve_url, json=body).json() == approval.json()
    assert api.get(url).json()['items'][0]['approval_effective'] is True
    changed = {**spec, 'filters': []}
    second = api.post(url, json=changed).json()
    assert second['version'] == 2
    assert api.post(approve_url, json=body).status_code == 409
    history = api.get(url).json()['items']
    assert [row['version'] for row in history] == [2, 1]
    assert not any(row['approval_effective'] for row in history)
    assert history[0]['reviewable'] is True and history[1]['reviewable'] is False
    assert history[1]['approval_id'] == approval.json()['approval_id']
    assert history[1]['spec_json'] == spec
    with pytest.raises(psycopg.errors.RaiseException, match='immutable'):
        with queue.conn() as conn:
            conn.execute("UPDATE platform.specification SET spec_json='{}' WHERE specification_id=%s", (first['specification_id'],))
    with pytest.raises(psycopg.errors.RaiseException, match='immutable'):
        with queue.conn() as conn:
            conn.execute("UPDATE platform.specification_approval SET content_checksum=%s WHERE specification_id=%s", ('d'*64, first['specification_id']))
    after = queue.detail(task_id, run['run_id'])
    assert {**after, 'events': before['events']} == before
    events = [event for event in after['events'] if event['event_type'].startswith('SPECIFICATION_')]
    assert [event['event_type'] for event in events] == ['SPECIFICATION_SAVED', 'SPECIFICATION_APPROVED', 'SPECIFICATION_SAVED']
    assert [event['event_context']['version'] for event in events] == [1, 1, 2]
    assert events[1]['event_context']['approval_id'] == approval.json()['approval_id']
    assert events[0]['event_context']['checksum'] == first['content_checksum']
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) AS n FROM platform.hop_artifact WHERE task_id=%s', (task_id,)).fetchone()['n'] == 0


def test_upstream_change_invalidates_saved_approval_without_erasing_it(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved = api.post(url, json=spec).json()
    approve_url = url + '/' + saved['specification_id'] + '/approve'
    body = {'content_checksum': saved['content_checksum']}
    assert api.post(approve_url, json=body).status_code == 200
    with queue.conn() as conn:
        conn.execute('UPDATE platform.task SET requirement_text=%s WHERE task_id=%s', ('revised requirement', task_id))
    assert api.post(approve_url, json=body).status_code == 409
    row = api.get(url).json()['items'][0]
    assert row['approval_id'] and not row['approval_effective']
    assert row['reviewable'] is False
    assert api.post(url, json=spec).json()['status'] == 'INVALID'
    assert len(api.get(url).json()['items']) == 1


def test_editor_context_uses_current_saved_run_and_blocks_stale(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specification/editor-context'
    response = api.get(url)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['status'] == 'EDITOR_CONTEXT_READY'
    assert result['binding']['run_id'] == str(run['run_id'])
    assert result['binding']['naming']['checksum'] == naming['checksum']
    assert 'filters' not in result['binding']
    assert 'synthetic-no-connection' not in response.text
    with queue.conn() as conn:
        conn.execute('UPDATE platform.task SET requirement_text=%s WHERE task_id=%s', ('changed', task_id))
    assert api.get(url).json()['status'] == 'BLOCKED'
