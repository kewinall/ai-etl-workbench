"""Evidence-bound human QA approval. Never grants release permission."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from .qa_context import load_qa_context
from .qa_journal import public_record
from .sa_contract import digest


def approval_binding(run,record,current_context):
    reviewed=public_record(record)
    if (reviewed['status']!='VALIDATED_NOT_APPROVED' or not reviewed['review']
            or reviewed['review']['status']!='PASS'):
        raise ValueError('QA_PASS_REVIEW_REQUIRED')
    if reviewed['context']!=current_context:
        raise ValueError('QA_APPROVAL_CONTEXT_CHANGED')
    if (str(run['run_id'])!=str(record['run_id']) or run['task_id']!=record['task_id']
            or run['state']!='NEEDS_REVIEW' or run['write_started'] is not True
            or run['matches_current'] is not True or run['lease_token'] is not None
            or run['outcome_code']!='HOP_EXECUTED_QA_REQUIRED'):
        raise ValueError('QA_RUN_NOT_APPROVABLE')
    # Include both upstream and actual model output, not merely an arbitrary PASS flag.
    binding={'version':1,'run_id':str(run['run_id']),'task_id':run['task_id'],
        'project_id':str(run['project_id']),'input_checksum':run['input_checksum'],
        'settings_checksum':run['settings_snapshot']['checksum'],
        'invocation_id':str(record['invocation_id']),
        'context_checksum':current_context['context_checksum'],
        'specification_checksum':current_context['specification_checksum'],
        'review_checksum':record['output_json']['review_checksum']}
    return {**binding,'checksum':digest(binding)}


def load_approval_offer(queue,task_id,run_id,*,connection=None):
    from contextlib import nullcontext
    with nullcontext(connection) if connection is not None else queue.conn() as conn:
        queue.locked_task(conn,task_id)
        record=conn.execute("""SELECT * FROM platform.agent_invocation
            WHERE task_id=%s AND run_id=%s AND role='pilot_qa' ORDER BY created_at DESC,invocation_id DESC LIMIT 1""",(task_id,run_id)).fetchone()
        if not record:raise ValueError('QA_REVIEW_REQUIRED')
        captured=load_qa_context(queue,task_id,run_id,record['input_json']['comparison_id'],connection=conn)
        return approval_binding(captured['run'],record,captured['context'])


def approve_review(queue,task_id,run_id,expected_checksum,*,confirmed=False):
    if confirmed is not True:raise ValueError('QA_HUMAN_CONFIRMATION_REQUIRED')
    with queue.conn() as conn:
        binding=load_approval_offer(queue,task_id,run_id,connection=conn)
        if binding['checksum']!=expected_checksum:raise ValueError('QA_APPROVAL_VERSION_CONFLICT')
        existing=conn.execute('SELECT * FROM platform.qa_review_approval WHERE run_id=%s',(run_id,)).fetchone()
        if existing:
            if existing['binding']!=binding:raise ValueError('QA_APPROVAL_VERSION_CONFLICT')
            return {'approval_id':str(existing['approval_id']),'binding_checksum':expected_checksum,
                'qa_approved':True,'release_ready':False}
        operator=conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
        if not operator:raise ValueError('OPERATOR_NOT_CONFIGURED')
        identity=uuid4()
        conn.execute('''INSERT INTO platform.qa_review_approval
            (approval_id,run_id,invocation_id,operator_id,binding,binding_checksum)
            VALUES(%s,%s,%s,%s,%s,%s)''',
            (identity,run_id,binding['invocation_id'],operator['operator_id'],Jsonb(binding),expected_checksum))
        queue.event(conn,run_id,'QA_HUMAN_APPROVED','QA_REVIEW',
            {'approval_id':str(identity),'binding_checksum':expected_checksum,'release_ready':False})
        return {'approval_id':str(identity),'binding_checksum':expected_checksum,'qa_approved':True,'release_ready':False}


def approval_state(saved,current_binding):
    if not saved:
        return {'status':'AWAITING_CONFIRMATION' if current_binding else 'NOT_ELIGIBLE',
            'approval':None,'binding':current_binding,'qa_approved':False,'release_ready':False}
    binding=saved['binding']
    if (digest({key:value for key,value in binding.items() if key!='checksum'})!=saved['binding_checksum']
            or binding.get('checksum')!=saved['binding_checksum']
            or binding.get('run_id')!=str(saved['run_id'])
            or binding.get('invocation_id')!=str(saved['invocation_id'])):
        raise ValueError('QA_APPROVAL_INTEGRITY_ERROR')
    current=binding==current_binding
    return {'status':'APPROVED_CURRENT' if current else 'STALE_APPROVAL',
        'approval':{'approval_id':str(saved['approval_id']),'created_at':saved['created_at'],
            'binding_checksum':saved['binding_checksum']},
        'binding':current_binding,'qa_approved':current,'release_ready':False}


def read_approval(queue,task_id,run_id,*,connection=None):
    from contextlib import nullcontext
    with nullcontext(connection) if connection is not None else queue.conn() as conn:
        queue.locked_task(conn,task_id)
        run=conn.execute('SELECT run_id FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone()
        if not run:raise ValueError('RUN_NOT_FOUND')
        saved=conn.execute('SELECT * FROM platform.qa_review_approval WHERE run_id=%s',(run_id,)).fetchone()
        try:current=load_approval_offer(queue,task_id,run_id,connection=conn)
        except ValueError:current=None
        return approval_state(saved,current)
