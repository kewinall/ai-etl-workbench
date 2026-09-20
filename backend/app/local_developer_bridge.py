"""Single-Run Docker bridge. Consumes only a previously authorized website intent."""
import json
import os
import sys
from uuid import UUID
from .run_queue import RunQueue
from .developer_journal import DeveloperJournal

PUBLIC_ERRORS = frozenset({'DEVELOPER_DISPATCH_DISABLED', 'DEVELOPER_NATIVE_PROFILE_REQUIRED',
    'DEVELOPER_CONTEXT_VERSION_CHANGED', 'DEVELOPER_DISPATCH_ALREADY_CONSUMED',
    'DEVELOPER_NOT_DISPATCHABLE', 'DEVELOPER_DISPATCH_CLAIM_EXPIRED_OR_LOST',
    'DEVELOPER_CLAIM_SCOPE_MISMATCH'})


def public_error(error):
    return str(error) if isinstance(error, ValueError) and str(error) in PUBLIC_ERRORS else 'LOCAL_DEVELOPER_REQUEST_FAILED'


def handle(queue, data):
    task = data['task_id']; run = UUID(data['run_id']); action = data['action']
    if action in ('claim', 'check') and os.getenv('WORKBENCH_DEVELOPER_DISPATCH_ENABLED') != 'true':
        raise ValueError('DEVELOPER_DISPATCH_DISABLED')
    journal = DeveloperJournal(queue)
    with queue.conn() as conn:
        queue.locked_task(conn, task)
        row = conn.execute("SELECT * FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND role='pilot_developer'", (task, run)).fetchone()
    if not row: return {'status':'IDLE'} if action == 'claim' else _missing()
    if row['provider'] != 'LOCAL_COPILOT' or not row['model'].startswith('copilot/'):
        raise ValueError('DEVELOPER_NATIVE_PROFILE_REQUIRED')
    if action == 'claim':
        if row['status'] != 'DEVELOPER_RESERVED': return {'status':row['status']}
        token = journal.claim(task, row['invocation_id'])
        payload = {key:row['input_json'][key] for key in ('context', 'prompt', 'prompt_checksum', 'schema', 'schema_checksum')}
        return {'status':'DISPATCH_RESERVED', 'invocation_id':str(row['invocation_id']),
                'claim_token':str(token), 'model':row['model'], 'prompt_version':row['prompt_version'], 'payload':payload}
    invocation = UUID(data['invocation_id']); token = UUID(data['claim_token'])
    if invocation != row['invocation_id']: raise ValueError('DEVELOPER_CLAIM_SCOPE_MISMATCH')
    if action == 'check':
        journal.check(task, invocation, token)
        return {'status':'CLAIM_ACTIVE'}
    if action == 'finish': return journal.finish(task, invocation, token, data['proposal'], data['trace'])
    if action == 'uncertain':
        journal.hold_uncertain(task, invocation, token)
        return {'status':'DEVELOPER_OUTCOME_UNKNOWN'}
    raise ValueError('UNKNOWN_LOCAL_DEVELOPER_ACTION')


def _missing():
    raise ValueError('DEVELOPER_CLAIM_SCOPE_MISMATCH')


def main():
    try:
        raw = sys.stdin.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('INPUT_TOO_LARGE')
        print(json.dumps(handle(RunQueue(os.environ['DATABASE_URL']), json.loads(raw)), default=str, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'status':'ERROR', 'code':public_error(error)}))
        raise SystemExit(1) from None


if __name__ == '__main__': main()
