"""Operator closes an uncertain/failed attempt; never certifies success or retries."""
import re
from uuid import uuid4
from psycopg.types.json import Jsonb
from .run_queue import RunConflict
from .sa_contract import digest


def offer(run):
    if (run['state']!='NEEDS_REVIEW' or run['phase']!='HOP_EXECUTION'
            or run['write_started'] is not True or run['lease_token'] is not None
            or run['outcome_code'] not in ('HOP_RESULT_UNKNOWN','HOP_EXECUTION_FAILED')):
        raise RunConflict('RECONCILIATION_NOT_ELIGIBLE')
    binding={'version':1,'run_id':str(run['run_id']),'task_id':run['task_id'],
        'project_id':str(run['project_id']),'input_checksum':run['input_checksum'],
        'settings_checksum':run['settings_snapshot']['checksum'],
        'outcome_code':run['outcome_code'],'updated_at':run['updated_at'].isoformat()}
    return {**binding,'checksum':digest(binding)}


def _load(queue,conn,task_id,run_id):
    queue.locked_task(conn,task_id)
    row=conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND run_id=%s FOR UPDATE',(task_id,run_id)).fetchone()
    if not row:raise ValueError('RUN_NOT_FOUND')
    saved=conn.execute('SELECT * FROM platform.execution_reconciliation WHERE run_id=%s',(run_id,)).fetchone()
    return row,saved


def _public(saved):
    return {'status':'CLOSED_WITHOUT_RETRY','reconciliation_id':str(saved['reconciliation_id']),
        'operator_id':str(saved['operator_id']),'created_at':saved['created_at'],
        'binding_checksum':saved['binding_checksum'],'evidence_sha256':saved['evidence_sha256'],
        'observed_row_count':saved['observed_row_count'],'original_outcome':saved['binding']['outcome_code'],
        'automatic_retry_allowed':False,'qa_approved':False,'release_ready':False}


def read(queue,task_id,run_id):
    with queue.conn() as conn:
        run,saved=_load(queue,conn,task_id,run_id)
        if saved:return _public(saved)
        try:binding=offer(run)
        except RunConflict:return {'status':'NOT_ELIGIBLE','release_ready':False}
        return {'status':'AWAITING_RECONCILIATION','binding':binding,'release_ready':False}


def close(queue,task_id,run_id,expected_checksum,evidence_sha256,observed_row_count,*,engine_stopped=False,target_checked=False,confirmed=False):
    if engine_stopped is not True or target_checked is not True or confirmed is not True:
        raise ValueError('RECONCILIATION_CONFIRMATION_REQUIRED')
    if (not isinstance(evidence_sha256,str) or not re.fullmatch('[a-f0-9]{64}',evidence_sha256)
            or type(observed_row_count) is not int or not 0<=observed_row_count<=9223372036854775807):
        raise ValueError('RECONCILIATION_EVIDENCE_REQUIRED')
    with queue.conn() as conn:
        run,saved=_load(queue,conn,task_id,run_id)
        if saved:
            if (saved['binding_checksum']!=expected_checksum or saved['evidence_sha256']!=evidence_sha256
                    or saved['observed_row_count']!=observed_row_count):
                raise RunConflict('RECONCILIATION_VERSION_CONFLICT')
            return _public(saved)
        binding=offer(run)
        if binding['checksum']!=expected_checksum:raise RunConflict('RECONCILIATION_VERSION_CONFLICT')
        operator=conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
        if not operator:raise ValueError('OPERATOR_NOT_CONFIGURED')
        saved=conn.execute('''INSERT INTO platform.execution_reconciliation
            (reconciliation_id,run_id,operator_id,binding,binding_checksum,evidence_sha256,observed_row_count)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (uuid4(),run_id,operator['operator_id'],Jsonb(binding),expected_checksum,evidence_sha256,observed_row_count)).fetchone()
        # Preserve original outcome, write marker, reservations, authorizations and
        # logs. Terminal FAILED is not a claim that the database rolled back.
        conn.execute("UPDATE platform.task_run SET state='FAILED',updated_at=clock_timestamp() WHERE run_id=%s",(run_id,))
        queue.event(conn,run_id,'OPERATOR_RECONCILED_WITHOUT_RETRY',run['phase'],
            {'reconciliation_id':str(saved['reconciliation_id']),'evidence_sha256':evidence_sha256,
             'observed_row_count':observed_row_count,'automatic_retry_allowed':False})
        return _public(saved)
