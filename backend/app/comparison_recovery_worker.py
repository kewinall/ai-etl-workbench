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
    except Exception as exc:
        # Preserve partial evidence. An unknown read outcome never grants replay.
        return recovery.finish(queue,request,failure_code=str(exc) if isinstance(exc, ValueError) else None)


def main():
    import argparse
    import os
    from uuid import UUID
    from .run_queue import RunQueue
    from .repository import PostgresRepository
    parser = argparse.ArgumentParser(description='Consume one authorized result read; never run ETL')
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--run-id', required=True, type=UUID)
    args = parser.parse_args()
    result = run_once(RunQueue(os.environ['DATABASE_URL']), PostgresRepository(os.environ['DATABASE_URL']),
                      args.task_id, args.run_id)
    print(result['status'])


if __name__ == '__main__':
    main()
