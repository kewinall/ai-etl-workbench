"""Read-only delivery check under the existing Task transaction lock."""
from .run_queue import RunConflict


def require_undelivered(queue, conn, task_id, run_id):
    queue.locked_task(conn, task_id)
    if not conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s AND run_id=%s', (task_id, run_id)).fetchone():
        raise ValueError('RUN_NOT_FOUND')
    delivered = conn.execute('''SELECT d.release_id FROM platform.release_delivery d
        JOIN platform.release_candidate_record c USING(candidate_id)
        WHERE c.task_id=%s AND c.run_id=%s LIMIT 1''', (task_id, run_id)).fetchone()
    if delivered:
        raise RunConflict('RUN_ALREADY_DELIVERED_READ_ONLY')
