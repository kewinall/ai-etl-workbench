"""Control-only worker: deterministic initial checks, never AI/Hop/database ETL."""
import argparse
import os
import signal
from uuid import uuid4
from threading import Event, Thread
from .platform_harness import requirement_issues
from .run_queue import RunQueue, RunConflict
from .requirement_contract import condition_issues
from .csv_contract import csv_contract_issues
from .source_preflight import source_preflight
from .worker_presence import WorkerRegistry, PresenceReporter
from .qa_recovery import reap_expired_qa


def check_requirements(snapshot):
    task = {**snapshot, 'requirement': snapshot.get('requirement_text', '')}
    issues = requirement_issues(task) + condition_issues(snapshot) + csv_contract_issues(snapshot)
    return {'version': 1, 'scope': 'INITIAL_DETERMINISTIC_CHECK_ONLY',
            'status': 'NEEDS_INPUT' if issues else 'CHECKED', 'issues': issues}


def run_once(queue, heartbeat_seconds=10):
    if not 1 <= heartbeat_seconds <= 20:
        raise ValueError('INVALID_HEARTBEAT_INTERVAL')
    queue.reap_expired()
    run = queue.claim(lease_seconds=60)
    if not run:
        return {'status': 'IDLE'}
    run_id, token = run['run_id'], run['lease_token']
    stop, lost = Event(), Event()
    def heartbeat():
        while not stop.wait(heartbeat_seconds):
            try:
                queue.heartbeat(run_id, token, lease_seconds=60)
            except Exception:
                lost.set()
                return
    thread = Thread(target=heartbeat, daemon=True)
    try:
        queue.heartbeat(run_id, token, lease_seconds=60)
        queue.start_gate(run_id, token)
        thread.start()
        try:
            result = check_requirements(run['input_snapshot'])
            evidence, source_issues = source_preflight(run['input_snapshot'])
            result['source_evidence'] = evidence
            result['issues'].extend(source_issues)
            if source_issues:
                result['status'] = 'NEEDS_INPUT'
        except Exception:
            result = {'version': 1, 'scope': 'INITIAL_DETERMINISTIC_CHECK_ONLY', 'status': 'ERROR', 'issues': []}
        if lost.is_set():
            return {'status': 'LEASE_LOST', 'run_id': str(run_id)}
        queue.complete_gate(run_id, token, result)
        return {'status': result['status'], 'run_id': str(run_id)}
    except RunConflict:
        return {'status': 'LEASE_LOST', 'run_id': str(run_id)}
    finally:
        stop.set()
        if thread.ident is not None:
            thread.join(timeout=16)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if os.getenv('WORKBENCH_CONTROL_WORKER_ENABLED') != 'true':
        print('Control worker disabled', flush=True)
        return
    queue = RunQueue(os.environ['DATABASE_URL'])
    pause = Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: pause.set())
    registry, instance = WorkerRegistry(queue), uuid4()
    with PresenceReporter(lambda state: registry.touch(instance, 'CONTROL', 'EXECUTE', state)) as presence:
        while not pause.is_set():
            try:
                presence.activity = 'BUSY'
                reap_expired_qa(queue)
                result = run_once(queue)
                if result['status'] != 'IDLE' or args.once:
                    print(result, flush=True)
            except Exception:
                print('CONTROL_WORKER_STORE_UNAVAILABLE', flush=True)
                if args.once:
                    raise SystemExit(1) from None
            finally:
                presence.activity = 'IDLE'
            if args.once:
                return
            pause.wait(3)


if __name__ == '__main__':
    main()
