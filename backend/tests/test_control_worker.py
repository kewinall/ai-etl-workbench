import pytest
from app import control_worker as worker
from app.run_queue import RunConflict


class Queue:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.calls = []
        self.result = None
    def reap_expired(self): self.calls.append('reap')
    def claim(self, **kwargs):
        self.calls.append('claim')
        return None if self.snapshot is None else dict(run_id='run', lease_token='lease', input_snapshot=self.snapshot)
    def heartbeat(self, *args, **kwargs): self.calls.append('heartbeat')
    def start_gate(self, *args): self.calls.append('start')
    def complete_gate(self, run, token, result):
        self.calls.append('complete')
        self.result = result


def test_idle_does_not_start_gate():
    queue = Queue()
    assert worker.run_once(queue) == {'status': 'IDLE'}
    assert queue.calls == ['reap', 'claim']


def test_missing_inputs_are_retained():
    queue = Queue({})
    assert worker.run_once(queue)['status'] == 'NEEDS_INPUT'
    assert {issue['field_path'] for issue in queue.result['issues']} >= {'requirement', 'target_config.table'}
    assert queue.calls == ['reap', 'claim', 'heartbeat', 'start', 'complete']


def test_checked_is_not_etl_success():
    queue = Queue(dict(requirement_text='Synthetic', source_config={'sources': [{'fields': [{'name': 'id'}]}]}, target_config={'schema': 'ai_sample', 'table': 'synthetic', 'requirements_v1': {'version': 1, 'write_mode': 'APPEND', 'date_scope': 'ALL'}}))
    assert worker.run_once(queue)['status'] == 'CHECKED'
    assert queue.result['scope'] == 'INITIAL_DETERMINISTIC_CHECK_ONLY'


def test_internal_error_does_not_expose_exception(monkeypatch):
    def fail(_): raise RuntimeError('secret-credential')
    monkeypatch.setattr(worker, 'check_requirements', fail)
    queue = Queue({})
    assert worker.run_once(queue)['status'] == 'ERROR'
    assert 'secret-credential' not in str(queue.result)


def test_lost_lease_cannot_complete(monkeypatch):
    queue = Queue({})
    def fail(*args, **kwargs): raise RunConflict('LEASE_LOST')
    monkeypatch.setattr(queue, 'heartbeat', fail)
    assert worker.run_once(queue)['status'] == 'LEASE_LOST'
    assert queue.result is None
    assert 'start' not in queue.calls


def test_invalid_heartbeat_interval():
    with pytest.raises(ValueError, match='INVALID_HEARTBEAT_INTERVAL'):
        worker.run_once(Queue(), heartbeat_seconds=60)


def test_background_heartbeat_failure_prevents_completion(monkeypatch):
    from threading import Event
    failed = Event()
    queue = Queue({})
    calls = []
    def heartbeat(*args, **kwargs):
        calls.append('heartbeat')
        if len(calls) > 1:
            failed.set()
            raise RunConflict('LEASE_LOST')
    def check(snapshot):
        assert failed.wait(5), 'Background heartbeat did not run'
        return {'status': 'CHECKED', 'issues': []}
    monkeypatch.setattr(queue, 'heartbeat', heartbeat)
    monkeypatch.setattr(worker, 'check_requirements', check)
    assert worker.run_once(queue, heartbeat_seconds=1)['status'] == 'LEASE_LOST'
    assert queue.result is None
