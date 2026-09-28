"""Real isolated control DB, synthetic engine: never a real Hop/Vertica claim."""
from contextlib import contextmanager
from copy import deepcopy
from uuid import UUID
import pytest
from app import execution_preparation
from app.execution_authorization import offer, authorize
from app.execution_reservation import reserve
from app.execution_oracle import load_execution_oracle
from app.source_binding import expected_prepared_binding
from app.hop_worker import execute_once
from app.run_queue import RunConflict
from test_run_queue_integration import context, pytestmark
from test_json_role_api_integration import prepared_json
from test_json_specification import CONTENT
from oracle_fixture import approved_answer


def candidate(context, tmp_path, monkeypatch):
    queue, task, run, spec, naming, api = prepared_json(context, tmp_path, monkeypatch, b'\xef\xbb\xbf' + CONTENT)
    base = f'/api/tasks/{task}/runs/{run["run_id"]}/specifications'
    response = api.post(base, json=spec)
    assert response.status_code == 200, response.text
    saved = response.json()
    response = api.post(base + '/' + saved['specification_id'] + '/approve', json={'content_checksum': saved['content_checksum']})
    assert response.status_code == 200, response.text
    sid = UUID(saved['specification_id'])
    approved_answer(queue, task, run['run_id'], sid, rows=[
        {'category': 'A', 'total_amount': '251.75', 'row_count': 2},
        {'category': 'C', 'total_amount': '201.00', 'row_count': 1}])
    with queue.conn() as conn: current = offer(queue, conn, task, run['run_id'], sid)
    assert current['binding']['policy_version'] == 'hop-single-attempt-v5'
    auth = authorize(queue, task, run['run_id'], sid, current['binding_checksum'], True)
    return queue, task, run, sid, current, UUID(auth['authorization_id'])


@pytest.mark.parametrize('invalidate', [False, True])
def test_json_private_preparation_rechecks_approval_and_cleans(context, tmp_path, monkeypatch, invalidate):
    queue, task, run, sid, current, aid = candidate(context, tmp_path, monkeypatch)
    original = execution_preparation.stage_json_source
    folders = []
    @contextmanager
    def interleave(*args):
        with original(*args) as staged:
            folders.append(staged['directory'])
            if invalidate: queue.cancel_unstarted(task, run['run_id'])
            yield staged
    monkeypatch.setattr(execution_preparation, 'stage_json_source', interleave)
    if invalidate:
        with pytest.raises(ValueError, match='APPROVED_INPUTS_STALE_OR_INVALID'):
            with execution_preparation.prepare_approved_source(queue, task, run['run_id'], sid):
                pytest.fail('Cancelled input cannot be prepared')
    else:
        with execution_preparation.prepare_approved_source(queue, task, run['run_id'], sid) as prepared:
            assert prepared['source_path'].read_bytes() == CONTENT
            assert prepared['original_source_path'].read_bytes() == b'\xef\xbb\xbf' + CONTENT
            assert prepared['binding'] == expected_prepared_binding(current['binding'])
            assert not prepared['execution_authorized']
    assert folders and all(not folder.exists() for folder in folders)
    assert not queue.detail(task, run['run_id'])['write_started']


def test_json_single_attempt_requires_exact_reader_at_reserve_and_write(context, tmp_path, monkeypatch):
    queue, task, run, sid, current, aid = candidate(context, tmp_path, monkeypatch)
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
    with execution_preparation.prepare_approved_source(queue, task, run['run_id'], sid) as prepared:
        binding = prepared['binding']
        changed = deepcopy(binding); changed['json_reader']['reader_checksum'] = 'f' * 64
        with pytest.raises(RunConflict, match='PREPARED_BINDING_CHANGED'):
            reserve(queue, task, run['run_id'], sid, aid, changed)
        claim = reserve(queue, task, run['run_id'], sid, aid, binding)
        with pytest.raises(RunConflict, match='EXECUTION_AUTHORIZATION_CONSUMED'):
            reserve(queue, task, run['run_id'], sid, aid, binding)
        with pytest.raises(RunConflict, match='EXECUTION_BINDING_CHANGED'):
            queue.begin_external_write(run['run_id'], claim['lease_token'], changed)
        assert not queue.detail(task, run['run_id'])['write_started']
        queue.begin_external_write(run['run_id'], claim['lease_token'], binding)
        assert queue.detail(task, run['run_id'])['write_started']


def test_json_completed_control_attempt_retains_oracle_without_replay(context, tmp_path, monkeypatch):
    queue, task, run, sid, current, aid = candidate(context, tmp_path, monkeypatch)
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
    calls = []
    def synthetic_engine(prepared, lost, log_sink):
        calls.append(prepared['binding'])
        receipt = log_sink(b'Synthetic engine response: no native Hop or target writes')
        return dict(status='COMPLETED', exit_code=0, errors=0, log_checksum=receipt['checksum'])
    result = execute_once(queue, task, run['run_id'], sid, aid, synthetic_engine)
    assert result['status'] == 'HOP_EXECUTED_QA_REQUIRED' and len(calls) == 1
    pin = load_execution_oracle(queue, task, run['run_id'])
    assert pin['binding_checksum'] == current['binding_checksum']
    assert not pin['qa_passed'] and not pin['release_ready']
    with pytest.raises(ValueError):
        execute_once(queue, task, run['run_id'], sid, aid, synthetic_engine)
    assert len(calls) == 1
