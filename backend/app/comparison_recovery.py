"""Single-consumption, explicitly approved result re-read. No ETL imports/calls."""
import os
from uuid import uuid4
from psycopg.types.json import Jsonb
from .sa_contract import digest
from .bound_result_query import load_bound_result_query
from .specification_store import context
from .comparison_store import checked_public_evidence


def offer(queue, conn, task_id, run_id):
    run, naming = context(queue, conn, task_id, run_id)
    job = conn.execute('SELECT * FROM platform.hop_dispatch_request WHERE run_id=%s FOR SHARE', (run_id,)).fetchone()
    if (not job or job['status'] != 'NEEDS_REVIEW'
            or job['outcome_code'] != 'HOP_PREPARATION_OR_COMPARISON_FAILED'
            or job['finished_at'] is None or not run['matches_current'] or not naming):
        raise ValueError('COMPARISON_RECOVERY_NOT_ELIGIBLE')
    _, pin = load_bound_result_query(queue, task_id, run_id, connection=conn)
    if (digest(job['binding']) != job['binding_checksum']
            or job['binding'].get('execution_binding_checksum') != pin['binding_checksum']
            or job['binding'].get('run_id') != str(run_id)
            or job['binding'].get('specification_id') != str(job['specification_id'])):
        raise ValueError('COMPARISON_RECOVERY_BINDING_CHANGED')
    # Do not let recovery replace evidence already reviewed by QA.
    if conn.execute("SELECT 1 FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa'", (run_id,)).fetchone():
        raise ValueError('COMPARISON_RECOVERY_QA_ALREADY_STARTED')
    return dict(version=1, run_id=str(run_id), request_id=str(job['request_id']),
        request_checksum=job['binding_checksum'], specification_id=str(job['specification_id']),
        input_checksum=run['input_checksum'], settings_checksum=run['settings_snapshot']['checksum'],
        naming_checksum=naming['checksum'], naming_contract_id=str(naming['contract_id']),
        execution_binding_checksum=pin['binding_checksum'], oracle_id=pin['oracle_id'],
        oracle_document_checksum=pin['document_checksum'], query_checksum=pin['result_query_checksum'],
        hop_event_id=pin['hop_event_id'], hop_log_checksum=pin['hop_log_checksum'],
        scope='READ_ORIGINAL_TARGET_ONLY_NO_ETL')


def public(row):
    return dict(recovery_id=str(row['recovery_id']), status=row['status'],
        binding_checksum=row['binding_checksum'], outcome_code=row['outcome_code'],
        comparison_id=str(row['comparison_id']) if row['comparison_id'] else None,
        comparison_checksum=row['comparison_checksum'], automatic_retry=False,
        etl_replay_allowed=False, qa_passed=False, release_ready=False)


def read(queue, task_id, run_id):
    with queue.conn() as conn:
        queue.locked_task(conn, task_id)
        if not conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s AND run_id=%s', (task_id,run_id)).fetchone():
            raise ValueError('RUN_NOT_FOUND')
        row = conn.execute('SELECT * FROM platform.comparison_recovery WHERE run_id=%s', (run_id,)).fetchone()
        if row: return public(row)
        try: binding = offer(queue, conn, task_id, run_id)
        except ValueError:
            return dict(status='NOT_ELIGIBLE', etl_replay_allowed=False, release_ready=False)
    return dict(status='AWAITING_CONFIRMATION', binding_checksum=digest(binding),
        enabled=os.getenv('WORKBENCH_EXECUTION_ENABLED') == 'true',
        etl_replay_allowed=False, qa_passed=False, release_ready=False)


def enqueue(queue, task_id, run_id, binding_checksum, confirmed):
    if confirmed is not True: raise ValueError('COMPARISON_RECOVERY_CONFIRMATION_REQUIRED')
    if os.getenv('WORKBENCH_EXECUTION_ENABLED') != 'true': raise ValueError('EXECUTION_DISABLED')
    with queue.conn() as conn:
        queue.locked_task(conn, task_id)
        if not conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s AND run_id=%s', (task_id,run_id)).fetchone():
            raise ValueError('RUN_NOT_FOUND')
        previous = conn.execute('SELECT * FROM platform.comparison_recovery WHERE run_id=%s', (run_id,)).fetchone()
        if previous:
            if previous['binding_checksum'] != binding_checksum: raise ValueError('COMPARISON_RECOVERY_CONFLICT')
            return public(previous)
        binding = offer(queue, conn, task_id, run_id)
        if digest(binding) != binding_checksum: raise ValueError('COMPARISON_RECOVERY_CONFLICT')
        operator = conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
        if not operator: raise ValueError('OPERATOR_NOT_CONFIGURED')
        row = conn.execute('''INSERT INTO platform.comparison_recovery
            (recovery_id,request_id,run_id,operator_id,binding,binding_checksum,status)
            VALUES(%s,%s,%s,%s,%s,%s,'QUEUED') RETURNING *''',
            (uuid4(),binding['request_id'],run_id,operator['operator_id'],Jsonb(binding),binding_checksum)).fetchone()
        queue.event(conn,run_id,'COMPARISON_RECOVERY_QUEUED','QA_PREPARATION',public(row))
        return public(row)


def claim(queue, task_id=None, run_id=None):
    if os.getenv('WORKBENCH_EXECUTION_ENABLED') != 'true': raise ValueError('EXECUTION_DISABLED')
    if bool(task_id) != bool(run_id): raise ValueError('COMPARISON_RECOVERY_SCOPE_REQUIRED')
    with queue.conn() as conn:
        rows = conn.execute('''SELECT c.recovery_id,c.run_id,r.task_id FROM platform.comparison_recovery c
            JOIN platform.task_run r USING(run_id) WHERE c.status='QUEUED'
            AND (%s::uuid IS NULL OR c.run_id=%s::uuid) AND (%s::text IS NULL OR r.task_id=%s)
            ORDER BY c.created_at LIMIT 20''', (run_id,run_id,task_id,task_id)).fetchall()
    for row in rows:
        with queue.conn() as conn:
            queue.locked_task(conn,row['task_id'])
            saved = conn.execute("""UPDATE platform.comparison_recovery SET status='CLAIMED',claim_token=%s,claimed_at=clock_timestamp()
                WHERE recovery_id=%s AND status='QUEUED' RETURNING *""", (uuid4(),row['recovery_id'])).fetchone()
            if saved:
                queue.event(conn,row['run_id'],'COMPARISON_RECOVERY_CLAIMED','QA_PREPARATION',public(saved))
                return {**saved,'task_id':row['task_id']}
    return None


def check_current(queue, conn, request):
    current = offer(queue,conn,request['task_id'],request['run_id'])
    if current != request['binding'] or digest(current) != request['binding_checksum']:
        raise ValueError('COMPARISON_RECOVERY_BINDING_CHANGED')
    active = conn.execute("""SELECT 1 FROM platform.comparison_recovery
        WHERE recovery_id=%s AND claim_token=%s AND status='CLAIMED'""",
        (request['recovery_id'],request['claim_token'])).fetchone()
    if not active: raise ValueError('COMPARISON_RECOVERY_CLAIM_LOST')


def checked_comparison(conn, run_id, comparison_id, checksum, binding):
    row = conn.execute('''SELECT c.evidence,c.checksum,p.query_checksum,p.settings_checksum,p.hop_event_id
        FROM platform.task_run_result_comparison c JOIN platform.result_comparison_provenance p
        ON p.comparison_id=c.comparison_id AND p.run_id=c.run_id AND p.comparison_checksum=c.checksum
        WHERE c.run_id=%s AND c.comparison_id=%s AND c.checksum=%s''', (run_id,comparison_id,checksum)).fetchone()
    if not row: raise ValueError('COMPARISON_RECOVERY_PROVENANCE_REQUIRED')
    evidence = checked_public_evidence(row['evidence'],row['checksum'],run_id)
    for key in ('execution_binding_checksum','oracle_id','oracle_document_checksum','hop_event_id','hop_log_checksum'):
        if evidence[key] != binding[key]: raise ValueError('COMPARISON_RECOVERY_PROVENANCE_CHANGED')
    if any(row[key] != binding[key] for key in ('query_checksum','settings_checksum','hop_event_id')):
        raise ValueError('COMPARISON_RECOVERY_PROVENANCE_CHANGED')
    return evidence


def finish(queue, request, result=None):
    with queue.conn() as conn:
        queue.locked_task(conn,request['task_id'])
        comparison_id = checksum = None
        status, code = 'FAILED','COMPARISON_RECOVERY_FAILED_NO_ETL_RETRY'
        if result is not None:
            check_current(queue,conn,request)
            comparison_id,checksum = result['comparison_id'],result['checksum']
            evidence = checked_comparison(conn,request['run_id'],comparison_id,checksum,request['binding'])
            status,code = 'COMPLETED','RESULT_'+evidence['status']+'_QA_REQUIRED'
        saved = conn.execute('''UPDATE platform.comparison_recovery SET status=%s,outcome_code=%s,
            comparison_id=%s,comparison_checksum=%s,finished_at=clock_timestamp()
            WHERE recovery_id=%s AND claim_token=%s AND status='CLAIMED' RETURNING *''',
            (status,code,comparison_id,checksum,request['recovery_id'],request['claim_token'])).fetchone()
        if not saved: raise ValueError('COMPARISON_RECOVERY_CLAIM_LOST')
        queue.event(conn,request['run_id'],'COMPARISON_RECOVERY_'+status,'QA_PREPARATION',public(saved))
        return public(saved)


def require_completed_recovery(conn, job):
    """Additional release lineage; the failed original request stays immutable."""
    if job['status'] != 'NEEDS_REVIEW' or job['outcome_code'] != 'HOP_PREPARATION_OR_COMPARISON_FAILED':
        raise ValueError('RELEASE_WEBSITE_EXECUTION_REQUIRED')
    row = conn.execute("SELECT * FROM platform.comparison_recovery WHERE request_id=%s AND run_id=%s AND status='COMPLETED'",
        (job['request_id'],job['run_id'])).fetchone()
    if not row or row['outcome_code'] != 'RESULT_MATCH_QA_REQUIRED': raise ValueError('RELEASE_COMPARISON_RECOVERY_REQUIRED')
    binding = row['binding']
    if (digest(binding) != row['binding_checksum'] or digest(job['binding']) != job['binding_checksum']
            or binding.get('request_checksum') != job['binding_checksum']
            or binding.get('request_id') != str(job['request_id']) or binding.get('run_id') != str(job['run_id'])
            or binding.get('execution_binding_checksum') != job['binding'].get('execution_binding_checksum')):
        raise ValueError('RELEASE_COMPARISON_RECOVERY_CHANGED')
    if checked_comparison(conn,job['run_id'],row['comparison_id'],row['comparison_checksum'],binding)['status'] != 'MATCH':
        raise ValueError('RELEASE_COMPARISON_RECOVERY_MISMATCH')
