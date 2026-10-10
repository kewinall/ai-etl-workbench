"""Revision persistence on the existing specification table; no execution side effects."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from .etl_specification import validate_specification
from .sa_contract import digest


def record_semantic_rejection(queue, conn, run, payload, result):
    """Persist rejected save evidence, not an executable spec or a new run.

    Caller holds the Task lock, making identical rejected submissions idempotent.
    Read-only validate/compile previews do not call this function.
    """
    issues = [issue for issue in result.get('issues', []) if issue.get('code') in
              ('SPEC_TRANSFORMATION_INTENT_MISMATCH', 'SPEC_JOIN_SEMANTICS_MISMATCH', 'SPEC_DATE_RANGE_FILTER_MISMATCH')]
    if (result.get('status') != 'INVALID' or not issues or not run.get('matches_current')
            or run.get('write_started') is not False or run.get('state') != 'NEEDS_REVIEW'
            or (run.get('approval') or {}).get('decision') != 'APPROVE'):
        return
    packet = {'version': 1, 'input_checksum': run['input_checksum'],
              'settings_checksum': run['settings_snapshot']['checksum'],
              'proposed_checksum': digest(payload), 'issues': issues,
              'specification_saved': False, 'execution_authorized': False}
    packet['attempt_checksum'] = digest(packet)
    exists = conn.execute("""SELECT event_id FROM platform.task_run_event
        WHERE run_id=%s AND event_type='SPECIFICATION_SEMANTIC_REJECTED'
          AND event_context->>'attempt_checksum'=%s""", (run['run_id'], packet['attempt_checksum'])).fetchone()
    if not exists:
        queue.event(conn, run['run_id'], 'SPECIFICATION_SEMANTIC_REJECTED', 'SPEC_VALIDATION', packet)


def context(queue, conn, task_id, run_id):
    task = queue.locked_task(conn, task_id)
    run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s FOR SHARE', (run_id, task_id)).fetchone()
    if not run:
        raise HTTPException(404, detail='找不到指定版本')
    naming = conn.execute('SELECT * FROM platform.naming_contract WHERE task_id=%s ORDER BY version DESC LIMIT 1 FOR SHARE', (task_id,)).fetchone()
    approval = conn.execute('SELECT * FROM platform.task_run_approval WHERE run_id=%s', (run_id,)).fetchone()
    return {**run, 'approval': approval, 'matches_current': queue.matches_current(conn, task, run)}, naming


def history(queue, conn, task_id, run_id):
    run, naming = context(queue, conn, task_id, run_id)
    rows = conn.execute('SELECT s.specification_id,s.version,s.spec_json,s.content_checksum,s.is_current,s.created_at,a.approval_id,a.created_at AS approved_at FROM platform.specification s LEFT JOIN platform.specification_approval a USING(specification_id) WHERE s.task_id=%s AND s.run_id=%s ORDER BY s.version DESC', (task_id, run_id)).fetchall()
    latest = conn.execute('SELECT specification_id FROM platform.specification WHERE task_id=%s ORDER BY version DESC LIMIT 1', (task_id,)).fetchone()
    for row in rows:
        bound_id = (row['spec_json'].get('naming') or {}).get('contract_id')
        row['bound_naming'] = conn.execute('SELECT version,contract_json FROM platform.naming_contract WHERE task_id=%s AND contract_id=%s', (task_id, bound_id)).fetchone() if bound_id else None
        valid = validate_specification(row['spec_json'], run, naming) if naming else {'status': 'INVALID'}
        row['reviewable'] = bool(row['is_current'] and latest and latest['specification_id'] == row['specification_id'] and valid['status'] == 'VALIDATED_NOT_APPROVED' and valid['specification_checksum'] == row['content_checksum'])
        row['approval_effective'] = bool(row['approval_id'] and row['reviewable'])
        row['execution_authorized'] = False
    return {'items': rows, 'execution_authorized': False}


def save(queue, conn, task_id, run_id, result):
    if result['status'] != 'VALIDATED_NOT_APPROVED':
        return result
    latest = conn.execute('SELECT * FROM platform.specification WHERE task_id=%s ORDER BY version DESC LIMIT 1 FOR UPDATE', (task_id,)).fetchone()
    # Only coalesce consecutive identical saves; never revive an older version.
    if latest and latest['run_id'] == run_id and latest['content_checksum'] == result['specification_checksum']:
        row = latest
    else:
        conn.execute('UPDATE platform.specification SET is_current=false WHERE task_id=%s AND is_current', (task_id,))
        row = conn.execute("INSERT INTO platform.specification(specification_id,task_id,version,spec_json,validation_status,is_current,run_id,content_checksum,naming_contract_id) VALUES(%s,%s,%s,%s,'VALIDATED_NOT_APPROVED',true,%s,%s,%s) RETURNING *",
                           (uuid4(), task_id, latest['version']+1 if latest else 1, Jsonb(result['specification']), run_id, result['specification_checksum'], result['specification']['naming']['contract_id'])).fetchone()
        queue.event(conn, run_id, 'SPECIFICATION_SAVED', 'SPEC_VALIDATION', {'specification_id': str(row['specification_id']), 'version': row['version'], 'checksum': row['content_checksum']})
    return {'specification_id': row['specification_id'], 'version': row['version'], 'content_checksum': row['content_checksum'],
            'status': 'SAVED_NOT_EXECUTABLE', 'execution_authorized': False}


def approve(queue, conn, task_id, run_id, specification_id, checksum):
    run, naming = context(queue, conn, task_id, run_id)
    row = conn.execute('SELECT * FROM platform.specification WHERE specification_id=%s AND task_id=%s AND run_id=%s FOR UPDATE', (specification_id, task_id, run_id)).fetchone()
    if not row:
        raise HTTPException(404, detail='找不到指定規格版本')
    latest = conn.execute('SELECT specification_id FROM platform.specification WHERE task_id=%s ORDER BY version DESC LIMIT 1', (task_id,)).fetchone()
    if row['content_checksum'] != checksum or not row['is_current'] or latest['specification_id'] != specification_id:
        raise HTTPException(409, detail='規格版本或 checksum 已變更，請重新檢視')
    if not naming:
        raise HTTPException(409, detail='缺少命名契約')
    validated = validate_specification(row['spec_json'], run, naming)
    if validated['status'] != 'VALIDATED_NOT_APPROVED' or validated['specification_checksum'] != checksum:
        raise HTTPException(409, detail='上游輸入、設定或命名已變更；舊規格不可核准')
    existing = conn.execute('SELECT * FROM platform.specification_approval WHERE specification_id=%s', (specification_id,)).fetchone()
    if not existing:
        operator = conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
        if not operator:
            raise HTTPException(409, detail='尚未設定操作人員')
        existing = conn.execute('INSERT INTO platform.specification_approval(approval_id,specification_id,operator_id,content_checksum) VALUES(%s,%s,%s,%s) RETURNING *', (uuid4(), specification_id, operator['operator_id'], checksum)).fetchone()
        queue.event(conn, run_id, 'SPECIFICATION_APPROVED', 'SPEC_VALIDATION', {'specification_id': str(specification_id), 'version': row['version'], 'checksum': checksum, 'approval_id': str(existing['approval_id']), 'operator_id': str(operator['operator_id'])})
    return {**existing, 'status': 'SPEC_APPROVED_NOT_EXECUTABLE', 'execution_authorized': False}
