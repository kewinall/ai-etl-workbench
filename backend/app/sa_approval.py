"""Explicit human SA handoff. Input approval is not approval of model advice."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from .sa_contract import build_sa_context,validate_sa_review,digest
from .run_queue import RunConflict


def handoff_binding(run,record,*,require_pending=True):
    if (not record or record['status']!='VALIDATED_NOT_APPROVED'
            or record.get('role')!='pilot_sa' or str(record['run_id'])!=str(run['run_id'])
            or record['task_id']!=run['task_id'] or run.get('matches_current') is not True
            or (run.get('approval') or {}).get('decision')!='APPROVE'):
        raise RunConflict('SA_HANDOFF_NOT_ELIGIBLE')
    if require_pending and (run['state']!='NEEDS_REVIEW' or run['write_started'] is not False
            or run.get('outcome_code')!='SA_REVIEW_REQUIRES_APPROVAL'):
        raise RunConflict('SA_HANDOFF_NOT_ELIGIBLE')
    context=build_sa_context(run)
    if record['input_json']['context']!=context or record['context_checksum']!=context['context_checksum']:
        raise RunConflict('SA_HANDOFF_CONTEXT_CHANGED')
    output=record.get('output_json') or {}
    review=validate_sa_review(output.get('review'),context)
    if review['status']!='READY_FOR_REVIEW' or output.get('output_checksum')!=digest(review):
        raise RunConflict('SA_HANDOFF_REVIEW_REQUIRED')
    binding={'version':1,'run_id':str(run['run_id']),'task_id':run['task_id'],
        'project_id':str(run['project_id']),'invocation_id':str(record['invocation_id']),
        'input_checksum':run['input_checksum'],'settings_checksum':run['settings_snapshot']['checksum'],
        'context_checksum':context['context_checksum'],'review_checksum':digest(review)}
    return {**binding,'checksum':digest(binding)}


def load_binding(queue,conn,task_id,run_id,*,require_pending=True):
    from .specification_store import context
    queue.locked_task(conn,task_id)
    if not conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone():
        raise ValueError('RUN_NOT_FOUND')
    run,_=context(queue,conn,task_id,run_id)
    record=conn.execute("SELECT * FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND role='pilot_sa'",(task_id,run_id)).fetchone()
    return handoff_binding(run,record,require_pending=require_pending)


def read(queue,task_id,run_id):
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        run=conn.execute('SELECT state,write_started,outcome_code FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone()
        if not run:
            raise ValueError('RUN_NOT_FOUND')
        saved=conn.execute('SELECT * FROM platform.sa_handoff_approval WHERE run_id=%s',(run_id,)).fetchone()
        try:binding=load_binding(queue,conn,task_id,run_id,require_pending=not bool(saved))
        except (RunConflict,ValueError):binding=None
        current=bool(saved and binding and saved['binding']==binding)
        return {'status':('APPROVED_CURRENT' if current else 'STALE_APPROVAL') if saved else ('AWAITING_CONFIRMATION' if binding else 'NOT_ELIGIBLE'),
            'binding':binding,'approval_id':str(saved['approval_id']) if saved else None,
            'developer_authorized':bool(current and run['state']=='NEEDS_REVIEW' and not run['write_started']
                and run['outcome_code']=='SA_REVIEW_REQUIRES_APPROVAL'),
            'execution_authorized':False,'release_ready':False}


def approve(queue,task_id,run_id,expected_checksum,*,confirmed=False):
    if confirmed is not True:raise ValueError('SA_HUMAN_CONFIRMATION_REQUIRED')
    with queue.conn() as conn:
        binding=load_binding(queue,conn,task_id,run_id)
        if binding['checksum']!=expected_checksum:raise RunConflict('SA_HANDOFF_VERSION_CONFLICT')
        saved=conn.execute('SELECT * FROM platform.sa_handoff_approval WHERE run_id=%s',(run_id,)).fetchone()
        if saved and saved['binding']!=binding:raise RunConflict('SA_HANDOFF_VERSION_CONFLICT')
        if not saved:
            operator=conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
            if not operator:raise ValueError('OPERATOR_NOT_CONFIGURED')
            saved=conn.execute('''INSERT INTO platform.sa_handoff_approval
                (approval_id,run_id,invocation_id,operator_id,binding,binding_checksum)
                VALUES(%s,%s,%s,%s,%s,%s) RETURNING *''',
                (uuid4(),run_id,binding['invocation_id'],operator['operator_id'],Jsonb(binding),expected_checksum)).fetchone()
            queue.event(conn,run_id,'SA_HANDOFF_APPROVED','REQUIREMENT_GATE',
                {'approval_id':str(saved['approval_id']),'binding_checksum':expected_checksum})
        return {'approval_id':str(saved['approval_id']),'binding_checksum':expected_checksum,
            'developer_authorized':True,'execution_authorized':False,'release_ready':False}
