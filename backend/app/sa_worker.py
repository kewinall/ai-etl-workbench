"""Opt-in worker for explicitly authorized, billed SA reviews. Never invokes Hop."""
import os
import signal
from uuid import uuid4
from threading import Event, Thread
from .run_queue import RunQueue
from .repository import PostgresRepository
from .sa_work_queue import SAWorkQueue
from .sa_dispatch import execute_reserved_sa
from .worker_presence import WorkerRegistry, PresenceReporter


def run_once(queue, repo, *, completion=None, heartbeat_seconds=10):
    if not 1 <= heartbeat_seconds <= 20:
        raise ValueError('INVALID_HEARTBEAT_INTERVAL')
    work = SAWorkQueue(queue)
    work.reap_expired()
    record = work.claim()
    if not record:
        return {'status': 'IDLE'}
    if record['status'] != 'DISPATCH_RESERVED':
        return {'status': record['status']}
    stop = Event()
    def heartbeat():
        while not stop.wait(heartbeat_seconds):
            try:
                work.heartbeat(record['invocation_id'], record['claim_token'])
            except Exception:
                return  # Finish also verifies lease ownership; never retry after loss.
    thread = Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        return execute_reserved_sa(queue, repo, record['task_id'], record['run_id'], record, completion=completion)
    finally:
        stop.set()
        thread.join(timeout=16)


def main():
    if os.getenv('WORKBENCH_SA_DISPATCH_ENABLED') != 'true':
        print('SA_DISPATCH_DISABLED', flush=True)
        return
    queue = RunQueue(os.environ['DATABASE_URL'])
    repo = PostgresRepository(queue.url)
    stop = Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stop.set())
    registry, instance = WorkerRegistry(queue), uuid4()
    with PresenceReporter(lambda state: registry.touch(instance, 'SA_LITELLM', 'EXECUTE', state)) as presence:
        while not stop.is_set():
            try:
                presence.activity = 'BUSY'
                result = run_once(queue, repo)
                if result['status'] != 'IDLE':
                    print(result, flush=True)
            except Exception:
                print('SA_WORKER_STORE_UNAVAILABLE', flush=True)
            finally:
                presence.activity = 'IDLE'
            stop.wait(3)


if __name__ == '__main__':
    main()
