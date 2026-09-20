"""Single-consumption reservation; never launches Hop or starts target writes."""
import os
from uuid import uuid4
from .execution_authorization import offer
from .run_queue import RunConflict


def reserve(queue, task_id, run_id, specification_id, authorization_id, prepared_binding):
    if os.getenv('WORKBENCH_EXECUTION_ENABLED') != 'true':
        raise RunConflict('EXECUTION_DISABLED')
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        consent=conn.execute('SELECT *,expires_at>clock_timestamp() AS valid FROM platform.task_run_execution_authorization WHERE authorization_id=%s AND run_id=%s AND specification_id=%s FOR UPDATE',(authorization_id,run_id,specification_id)).fetchone()
        if not consent or not consent['valid']:
            raise RunConflict('EXECUTION_AUTHORIZATION_MISSING_OR_EXPIRED')
        if conn.execute('SELECT 1 FROM platform.task_run_execution_reservation WHERE authorization_id=%s',(authorization_id,)).fetchone():
            raise RunConflict('EXECUTION_AUTHORIZATION_CONSUMED')
        current=offer(queue,conn,task_id,run_id,specification_id)
        if current['binding_checksum'] != consent['binding_checksum']:
            raise RunConflict('EXECUTION_BINDING_CHANGED')
        expected={key:current['binding'][key] for key in ('run_id','specification_id','specification_checksum','input_checksum','settings_checksum','hpl_checksum','source_checksum')}
        expected['approval_id']=current['binding']['specification_approval_id']
        if prepared_binding != expected:
            raise RunConflict('PREPARED_BINDING_CHANGED')
        reservation_id,lease=uuid4(),uuid4()
        conn.execute('INSERT INTO platform.task_run_execution_reservation(reservation_id,authorization_id,run_id,binding_checksum) VALUES(%s,%s,%s,%s)',(reservation_id,authorization_id,run_id,current['binding_checksum']))
        row=conn.execute("UPDATE platform.task_run SET state='RUNNING',phase='HOP_PREPARATION',lease_token=%s,lease_until=clock_timestamp()+interval '60 seconds',outcome_code=NULL,updated_at=now() WHERE run_id=%s AND state='NEEDS_REVIEW' AND NOT write_started RETURNING run_id",(lease,run_id)).fetchone()
        if not row:
            raise RunConflict('EXECUTION_RUN_NOT_RESERVABLE')
        queue.event(conn,run_id,'EXECUTION_RESERVED','HOP_PREPARATION',{'reservation_id':str(reservation_id),'authorization_id':str(authorization_id),'binding_checksum':current['binding_checksum'],'automatic_retry_allowed':False})
        return {'status':'RESERVED_NOT_STARTED','run_id':str(run_id),'reservation_id':str(reservation_id),'lease_token':lease,'external_write_started':False}
