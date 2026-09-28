"""Own a result re-read request once, never execute Hop, SQL DDL or model calls."""
from . import comparison_recovery as recovery
from .bound_comparison import record_bound_comparison


def run_once(queue, repo, task_id=None, run_id=None):
    request = recovery.claim(queue,task_id,run_id)
    if not request: return {'status':'IDLE'}
    try:
        with queue.conn() as conn: recovery.check_current(queue,conn,request)
        result = record_bound_comparison(queue,repo,request['task_id'],request['run_id'])
        return recovery.finish(queue,request,result)
    except Exception:
        # Preserve partial evidence. An unknown read outcome never grants replay.
        return recovery.finish(queue,request)
