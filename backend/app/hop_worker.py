"""Internal single-attempt orchestration. No production adapter or dispatcher."""
from threading import Event, Thread

from .execution_preparation import prepare_approved_source
from .execution_reservation import reserve
from .prepared_integrity import verify_prepared_files
from .hop_outcome import validated_hop_outcome
from .private_log_store import save_private_log


def execute_once(queue, task_id, run_id, specification_id, authorization_id,
                 executor, heartbeat_seconds=10):
    """Executor must be synchronous and own termination/join of its child process.

    It must not return or raise while a child still uses the staging directory.
    No fallback, retries, model calls, or public execution endpoint are provided.
    """
    if not callable(executor):
        raise ValueError('HOP_ADAPTER_REQUIRED')
    if not 1 <= heartbeat_seconds <= 20:
        raise ValueError('INVALID_HEARTBEAT_INTERVAL')
    with prepare_approved_source(queue, task_id, run_id, specification_id) as prepared:
        verify_prepared_files(prepared)
        preflight = getattr(executor, 'preflight', None)
        if preflight is not None:
            preflight(prepared)
        receipt = reserve(queue, task_id, run_id, specification_id, authorization_id, prepared['binding'])
        token = receipt['lease_token']
        stop, lost = Event(), Event()

        def heartbeat():
            while not stop.wait(heartbeat_seconds):
                try:
                    queue.heartbeat(run_id, token)
                except Exception:
                    lost.set()
                    return

        thread = Thread(target=heartbeat, daemon=True)
        try:
            queue.heartbeat(run_id, token)
            thread.start()
            try:
                verify_prepared_files(prepared)
            except ValueError:
                return queue.fail_hop_preparation(run_id, token)
            if lost.is_set():
                return {'status':'LEASE_LOST', 'run_id':str(run_id)}
            queue.begin_external_write(run_id, token, prepared['binding'])
            try:
                result = executor(prepared, lost, lambda content: save_private_log(queue, run_id, token, content))
                validated_hop_outcome(result)
            except Exception:
                # Do not leak raw errors or assume that target writes did not occur.
                result = {'status':'UNKNOWN', 'exit_code':None, 'errors':None, 'log_checksum':None}
            if lost.is_set():
                return {'status':'LEASE_LOST', 'run_id':str(run_id)}
            return queue.complete_hop(run_id, token, result)
        finally:
            stop.set()
            if thread.ident is not None:
                thread.join(timeout=16)
