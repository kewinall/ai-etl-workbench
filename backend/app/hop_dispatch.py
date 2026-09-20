"""Durable single-consumption Hop request on the existing Run, never a new Task."""
import os
from uuid import uuid4
from psycopg.types.json import Jsonb
from . import execution_authorization, specification_store
from .approved_candidate import load_approved_candidate
from .delivery_compiler import compile_delivery_components
from .developer_contract import load_context
from .developer_journal import checked_trace
from .sa_contract import digest
from .invocation_usage import checked_usage


def require_sa_trace(sa):
    trace=(sa.get('output_json') or {}).get('trace') if sa else None
    if not isinstance(trace,dict):raise ValueError('REAL_SA_TRACE_REQUIRED')
    expected={key:sa[key] for key in ('provider','model','context_checksum')}
    expected.update(run_id=str(sa['run_id']),input_checksum=sa['input_json']['context']['input_checksum'],
        prompt_checksum=sa['input_json']['prompt_checksum'],schema_checksum=sa['input_json']['schema_checksum'])
    if any(trace.get(key)!=value for key,value in expected.items()):raise ValueError('SA_TRACE_BINDING_CHANGED')
    usage=checked_usage(trace.get('usage'))
    if sa['provider']=='LOCAL_COPILOT' and any(usage.get(key)!=value for key,value in
        (('cli_sessions',1),('automatic_retries',0),('tool_execution_count',0))):raise ValueError('SA_NATIVE_USAGE_INVALID')


def offer(queue,conn,task_id,run_id,specification_id):
    captured=load_context(queue,conn,task_id,run_id)
    sa=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_sa'",(run_id,)).fetchone()
    developer=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_developer'",(run_id,)).fetchone()
    require_sa_trace(sa)
    if not developer or developer['status']!='VALIDATED_NOT_APPROVED':raise ValueError('DEVELOPER_REVIEW_REQUIRED')
    output=developer['output_json']
    if developer['input_json']['context']!=captured['context'] or str((output.get('specification') or {}).get('specification_id'))!=str(specification_id):
        raise ValueError('DEVELOPER_SPECIFICATION_CHANGED')
    checked_trace(output['trace'],developer,output['proposal'])
    candidate=load_approved_candidate(queue,conn,task_id,run_id,specification_id)
    run,naming=specification_store.context(queue,conn,task_id,run_id)
    compiled=compile_delivery_components(candidate['compiled']['specification'],run,naming)
    if compiled['specification']['target_schema']!='ai_sample':raise ValueError('PILOT_TARGET_SCHEMA_REQUIRED')
    consent=execution_authorization.offer(queue,conn,task_id,run_id,specification_id)
    binding={'version':1,'run_id':str(run_id),'specification_id':str(specification_id),
        'execution_binding_checksum':consent['binding_checksum'],'ddl_checksum':compiled['ddl_checksum'],
        'sa_invocation_id':str(sa['invocation_id']),'developer_invocation_id':str(developer['invocation_id']),
        'developer_context_checksum':developer['context_checksum'],'target_policy':'CREATE_NEW_AI_SAMPLE_ONLY_NO_DROP'}
    return {'binding':binding,'binding_checksum':digest(binding),'ddl':compiled['ddl'],
        'specification':compiled['specification'],'execution_consent':consent,'run':run}


def enqueue(queue,task_id,run_id,specification_id,binding_checksum,confirmed):
    if confirmed is not True:raise ValueError('HOP_DISPATCH_CONSENT_REQUIRED')
    if os.getenv('WORKBENCH_EXECUTION_ENABLED')!='true':raise ValueError('EXECUTION_DISABLED')
    with queue.conn() as conn:
        current=offer(queue,conn,task_id,run_id,specification_id)
        if current['binding_checksum']!=binding_checksum:raise ValueError('HOP_DISPATCH_BINDING_CHANGED')
        existing=conn.execute('SELECT request_id,status,binding_checksum FROM platform.hop_dispatch_request WHERE run_id=%s',(run_id,)).fetchone()
        if existing:
            if existing['binding_checksum']!=binding_checksum:raise ValueError('HOP_DISPATCH_ALREADY_CONSUMED')
            return {'request_id':str(existing['request_id']),'status':existing['status'],'automatic_retry':False}
        consent=execution_authorization.authorize(queue,task_id,run_id,specification_id,
            current['execution_consent']['binding_checksum'],True,connection=conn)
        identity=uuid4()
        conn.execute('''INSERT INTO platform.hop_dispatch_request
            (request_id,run_id,authorization_id,specification_id,binding,binding_checksum,status)
            VALUES(%s,%s,%s,%s,%s,%s,'QUEUED')''',
            (identity,run_id,consent['authorization_id'],specification_id,Jsonb(current['binding']),binding_checksum))
        queue.event(conn,run_id,'HOP_DISPATCH_QUEUED','HOP_PREPARATION',{'request_id':str(identity),'automatic_retry':False})
    return {'request_id':str(identity),'status':'QUEUED','automatic_retry':False}


def claim(queue,task_id=None,run_id=None):
    if os.getenv('WORKBENCH_EXECUTION_ENABLED')!='true':raise ValueError('EXECUTION_DISABLED')
    if bool(task_id)!=bool(run_id):raise ValueError('HOP_SCOPE_REQUIRED')
    with queue.conn() as conn:
        rows=conn.execute('''SELECT r.request_id,r.run_id,t.task_id FROM platform.hop_dispatch_request r
            JOIN platform.task_run t USING(run_id) WHERE r.status='QUEUED'
            AND (%s::uuid IS NULL OR r.run_id=%s::uuid) AND (%s::text IS NULL OR t.task_id=%s)
            ORDER BY r.created_at LIMIT 20''',(run_id,run_id,task_id,task_id)).fetchall()
    for row in rows:
        with queue.conn() as conn:
            queue.locked_task(conn,row['task_id'])
            token=uuid4()
            saved=conn.execute("""UPDATE platform.hop_dispatch_request SET status='CLAIMED',claim_token=%s,claimed_at=clock_timestamp()
                WHERE request_id=%s AND status='QUEUED' RETURNING *""",(token,row['request_id'])).fetchone()
            if saved:
                queue.event(conn,row['run_id'],'HOP_DISPATCH_CLAIMED','HOP_PREPARATION',{'request_id':str(row['request_id'])})
                return {**saved,'task_id':row['task_id']}
    return None


def finish(queue,request,status,code):
    if status not in ('COMPLETED','NEEDS_REVIEW'):raise ValueError('HOP_DISPATCH_STATUS_INVALID')
    if code not in ('HOP_EXECUTED_QA_REQUIRED','HOP_FAILED_OR_UNKNOWN','HOP_PREPARATION_OR_COMPARISON_FAILED'):
        raise ValueError('HOP_DISPATCH_CODE_INVALID')
    with queue.conn() as conn:
        queue.locked_task(conn,request['task_id'])
        saved=conn.execute('''UPDATE platform.hop_dispatch_request SET status=%s,outcome_code=%s,finished_at=clock_timestamp()
            WHERE request_id=%s AND claim_token=%s AND status='CLAIMED' RETURNING run_id''',
            (status,code,request['request_id'],request['claim_token'])).fetchone()
        if not saved:raise ValueError('HOP_DISPATCH_CLAIM_LOST')
        queue.event(conn,saved['run_id'],'HOP_DISPATCH_'+status,'HOP_EXECUTION',{'request_id':str(request['request_id']),'outcome_code':code,'automatic_retry':False})
