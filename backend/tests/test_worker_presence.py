from threading import Event
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.local_sa_worker import serve
from app.worker_presence import PresenceReporter
from app.runtime_api import create_runtime_router


def test_observe_mode_never_claims_or_calls_model():
    stop = Event()
    actions = []
    def transport(data):
        actions.append(data)
        if data['action'] == 'observe':
            stop.set()
        return {'status': 'OK'}
    def forbidden(*args, **kwargs):
        raise AssertionError('Observe mode must never invoke a model')
    serve(stop=stop, transport=transport, completion=forbidden, log=lambda _: None)
    assert [row['action'] for row in actions] == ['presence', 'observe', 'presence']
    assert actions[0]['mode'] == 'OBSERVE'
    assert actions[-1]['activity'] == 'STOPPED'


def test_serve_consumes_one_claim_and_does_not_replay():
    stop = Event()
    actions, calls = [], []
    def transport(data):
        actions.append(data)
        if data['action'] == 'claim':
            if calls:
                stop.set()
                return {'status': 'IDLE'}
            return {'status': 'DISPATCH_RESERVED', 'task_id': 't', 'run_id': 'r', 'invocation_id': 'i',
                    'claim_token': 'lease', 'input_json': {}, 'model': 'copilot/test'}
        return {'status': 'VALIDATED_NOT_APPROVED' if data['action'] == 'finish' else 'RECORDED'}
    def completion(*args, before_call, **kwargs):
        calls.append(1)
        before_call()
        return {}, {}
    serve(allow_model_dispatch=True, stop=stop, transport=transport, completion=completion, poll_seconds=1, log=lambda _: None)
    assert calls == [1]
    assert all(row['task_id'] == 't' and row['run_id'] == 'r' for row in actions if row['action'] == 'heartbeat')
    assert actions[-1]['activity'] == 'STOPPED'


def test_serve_reconnects_after_store_error_without_model_calls():
    stop = Event()
    attempts, logs = [], []
    def transport(data):
        if data['action'] == 'observe':
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError('private database details')
            stop.set()
        return {'status': 'OBSERVING'}
    serve(stop=stop, transport=transport, poll_seconds=1, log=logs.append)
    assert len(attempts) == 2
    assert 'private database details' not in str(logs)
    assert 'LOCAL_WORKER_STORE_UNAVAILABLE' in str(logs)


def test_presence_reconnects_after_failed_initial_registration():
    recovered = Event()
    calls = []
    def report(state):
        calls.append(state)
        if len(calls) == 1:
            raise RuntimeError('temporary outage')
        recovered.set()
    with PresenceReporter(report, interval=1):
        assert recovered.wait(3)
    assert calls[-1] == 'STOPPED'


def test_unavailable_registry_does_not_claim_all_workers_offline():
    class Unavailable:
        def conn(self):
            raise RuntimeError('private database password')
    app = FastAPI()
    app.include_router(create_runtime_router(Unavailable()))
    response = TestClient(app).get('/api/runtime/workers')
    assert response.status_code == 503
    assert 'private database password' not in response.text
