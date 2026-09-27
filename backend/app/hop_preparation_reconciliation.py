"""Operator attestation closes a lost preparation owner; never retries or drops."""
import re
from uuid import uuid4
from psycopg.types.json import Jsonb
from .sa_contract import digest


def load(queue, conn, task_id, run_id):
    queue.locked_task(conn, task_id)
    run = conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND run_id=%s FOR UPDATE', (task_id, run_id)).fetchone()
    if not run: raise ValueError('RUN_NOT_FOUND')
    request = conn.execute('SELECT * FROM platform.hop_dispatch_request WHERE run_id=%s FOR UPDATE', (run_id,)).fetchone()
    saved = conn.execute('SELECT * FROM platform.hop_preparation_reconciliation WHERE request_id=%s', (request['request_id'],)).fetchone() if request else None
    return run, request, saved


def binding(run, request):
    if (not request or request['status'] != 'CLAIMED' or run['state'] != 'NEEDS_REVIEW'
            or run['write_started'] or run['lease_token'] is not None):
        raise ValueError('PREPARATION_RECONCILIATION_NOT_ELIGIBLE')
    result = dict(version=1, request_id=str(request['request_id']), run_id=str(run['run_id']),
        task_id=run['task_id'], project_id=str(run['project_id']),
        request_checksum=request['binding_checksum'], claim_checksum=digest(str(request['claim_token'])),
        claimed_at=request['claimed_at'].isoformat(), updated_at=run['updated_at'].isoformat())
    return {**result, 'checksum': digest(result)}


def public(saved):
    return dict(status='CLOSED_WITHOUT_RETRY', reconciliation_id=str(saved['reconciliation_id']),
        evidence_sha256=saved['evidence_sha256'], target_exists=saved['target_exists'],
        observed_row_count=saved['observed_row_count'], automatic_retry_allowed=False,
        release_ready=False, evidence_source='OPERATOR_ATTESTATION')


def read(queue, task_id, run_id):
    with queue.conn() as conn:
        run, request, saved = load(queue, conn, task_id, run_id)
        if saved: return public(saved)
        try: current = binding(run, request)
        except ValueError: return dict(status='NOT_ELIGIBLE', release_ready=False)
        return dict(status='AWAITING_RECONCILIATION', binding=current, release_ready=False)


def close(queue, task_id, run_id, data):
    if any(data.get(key) is not True for key in ('engine_stopped', 'target_checked', 'confirmed')):
        raise ValueError('PREPARATION_CONFIRMATION_REQUIRED')
    exists, count = data.get('target_exists'), data.get('observed_row_count')
    if (type(exists) is not bool or (exists and (type(count) is not int or not 0 <= count <= 9223372036854775807))
            or (not exists and count is not None)
            or not re.fullmatch('[a-f0-9]{64}', data.get('evidence_sha256', ''))):
        raise ValueError('PREPARATION_EVIDENCE_REQUIRED')
    with queue.conn() as conn:
        run, request, saved = load(queue, conn, task_id, run_id)
        if saved:
            if any(saved[key] != data.get(key) for key in ('binding_checksum', 'evidence_sha256', 'target_exists', 'observed_row_count')):
                raise ValueError('PREPARATION_RECONCILIATION_CONFLICT')
            return public(saved)
        current = binding(run, request)
        if current['checksum'] != data.get('binding_checksum'):
            raise ValueError('PREPARATION_RECONCILIATION_CONFLICT')
        operator = conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
        if not operator: raise ValueError('OPERATOR_NOT_CONFIGURED')
        saved = conn.execute('''INSERT INTO platform.hop_preparation_reconciliation
            (reconciliation_id,request_id,operator_id,binding,binding_checksum,evidence_sha256,target_exists,observed_row_count)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (uuid4(),request['request_id'],operator['operator_id'],Jsonb(current),current['checksum'],data['evidence_sha256'],exists,count)).fetchone()
        conn.execute("UPDATE platform.hop_dispatch_request SET status='NEEDS_REVIEW',outcome_code='HOP_PREPARATION_RECONCILED',finished_at=clock_timestamp() WHERE request_id=%s", (request['request_id'],))
        conn.execute("UPDATE platform.task_run SET state='FAILED',outcome_code='HOP_PREPARATION_RECONCILED',updated_at=clock_timestamp() WHERE run_id=%s", (run_id,))
        queue.event(conn,run_id,'HOP_PREPARATION_RECONCILED_WITHOUT_RETRY','HOP_PREPARATION',public(saved))
        return public(saved)
