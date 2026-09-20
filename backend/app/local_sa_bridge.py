"""Local Docker-exec transport. No listener, no database password copied to Windows."""
import json
import os
import sys
from uuid import UUID
from .run_queue import RunQueue, RunConflict
from .sa_work_queue import SAWorkQueue, authorization_offer
from .sa_journal import SAJournal


def handle(queue, data):
    work = SAWorkQueue(queue)
    action = data['action']
    if action == 'presence':
        from .worker_presence import WorkerRegistry
        return WorkerRegistry(queue).touch(data['instance_id'], 'SA_COPILOT', data['mode'], data['activity'])
    if action == 'observe':
        return {'status': 'OBSERVING', 'expired_calls_held': work.reap_expired()}
    task_id = data.get('task_id')
    run_id = UUID(data['run_id']) if data.get('run_id') else None
    if bool(task_id) != bool(run_id) or (action != 'claim' and not task_id):
        raise ValueError('INVALID_LOCAL_WORKER_SCOPE')
    if action == 'claim':
        if os.getenv('WORKBENCH_SA_DISPATCH_ENABLED') != 'true':
            raise RunConflict('SA_DISPATCH_DISABLED')
        work.reap_expired()
        row = work.claim('LOCAL_COPILOT', task_id, run_id)
        if not row or row['status'] != 'DISPATCH_RESERVED':
            return {'status': row['status'] if row else 'IDLE'}
        return {key: row[key] for key in ('status','task_id','run_id','invocation_id','claim_token','model','input_json')}
    invocation_id, token = UUID(data['invocation_id']), UUID(data['claim_token'])
    with queue.conn() as conn:
        row = conn.execute("SELECT * FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND invocation_id=%s AND claim_token=%s AND provider='LOCAL_COPILOT'", (task_id, run_id, invocation_id, token)).fetchone()
        if not row:
            raise RunConflict('SA_LEASE_LOST')
    if action == 'heartbeat':
        run = queue.detail(task_id, run_id)
        if (not run['matches_current'] or run['state'] != 'NEEDS_REVIEW'
                or row['input_json']['authorization'] != authorization_offer(run)):
            raise RunConflict('SA_AUTHORIZATION_VERSION_MISMATCH')
        work.heartbeat(invocation_id, token)
        return {'status': 'LEASE_ACTIVE'}
    if action == 'finish':
        status = SAJournal(queue).finish(task_id, invocation_id, data['review'], data['trace'], token)
        return {'status': status, 'invocation_id': str(invocation_id), 'execution_authorized': False}
    if action == 'uncertain':
        SAJournal(queue).hold_uncertain(task_id, invocation_id, data.get('trace'))
        return {'status': 'OUTCOME_UNKNOWN_NEEDS_REVIEW'}
    raise ValueError('UNKNOWN_LOCAL_WORKER_ACTION')


def main():
    try:
        raw = sys.stdin.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('LOCAL_WORKER_INPUT_TOO_LARGE')
        result = handle(RunQueue(os.environ['DATABASE_URL']), json.loads(raw))
        print(json.dumps(result, default=str, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'status': 'ERROR', 'code': str(error) if isinstance(error, RunConflict) else 'LOCAL_WORKER_REQUEST_FAILED'}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
