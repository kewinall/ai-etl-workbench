"""Revision persistence on the existing specification table; no execution side effects."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from .etl_specification import validate_specification


def context(queue, conn, task_id, run_id):
    task = queue.locked_task(conn, task_id)
    run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s FOR SHARE', (run_id, task_id)).fetchone()
    if not run:
        raise HTTPException(404, detail='找不到指定版本')
    naming = conn.execute('SELECT * FROM platform.naming_contract WHERE task_id=%s ORDER BY version DESC LIMIT 1 FOR SHARE', (task_id,)).fetchone()
    approval = conn.execute('SELECT * FROM platform.task_run_approval WHERE run_id=%s', (run_id,)).fetchone()
    return {**run, 'approval': approval, 'matches_current': queue.matches_current(conn, task, run)}, naming


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
