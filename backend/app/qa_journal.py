"""QA intent/result on the existing agent journal. No model calls or release authority."""
from uuid import uuid4
import re
from psycopg.types.json import Jsonb
from .qa_context import load_qa_context
from .qa_contract import QAReviewV1,validate_qa_review,build_qa_context
from .qa_gateway import PROMPT,PROMPT_VERSION
from .sa_contract import digest
from .invocation_usage import checked_usage


class QAJournal:
    def __init__(self,queue):self.queue=queue

    def read(self,task_id,run_id):
        with self.queue.conn() as conn:
            task=self.queue.locked_task(conn,task_id)
            run=conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s',(run_id,task_id)).fetchone()
            if not run:raise ValueError('RUN_NOT_FOUND')
            rows=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND task_id=%s AND role='pilot_qa' ORDER BY created_at DESC,invocation_id DESC",(run_id,task_id)).fetchall()
            row=rows[0] if rows else None
            current=self.queue.matches_current(conn,task,run)
            from .qa_approval import read_approval
            approval=read_approval(self.queue,task_id,run_id,connection=conn)
        return {'run_id':str(run_id),'matches_current':current,'invocation':public_record(row) if row else None,
            'history':[public_record(value) for value in rows],
            'dispatch_available':False,'approval_available':approval['status']=='AWAITING_CONFIRMATION',
            'human_approval':approval,'qa_approved':approval['qa_approved'],'release_ready':False}

    def reserve(self,task_id,run_id,comparison_id,context_checksum,consent,*,reassess_invocation_id=None,expected_prompt_checksum=None):
        if consent is not True:raise ValueError('QA_EXPLICIT_CONSENT_REQUIRED')
        with self.queue.conn() as conn:
            self.queue.locked_task(conn,task_id)
            captured=load_qa_context(self.queue,task_id,run_id,comparison_id,connection=conn)
            context=captured['context'];run=captured['run']
            if context['context_checksum']!=context_checksum:raise ValueError('QA_CONTEXT_VERSION_CHANGED')
            rows=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa' ORDER BY created_at DESC,invocation_id DESC FOR SHARE",(run_id,)).fetchall()
            existing=rows[0] if rows else None
            if expected_prompt_checksum is not None and expected_prompt_checksum!=digest(PROMPT):
                raise ValueError('QA_PROMPT_VERSION_CHANGED')
            if existing:
                if reassess_invocation_id is None:
                    if existing['context_checksum']!=context_checksum:raise ValueError('QA_ALREADY_RESERVED_NO_AUTOMATIC_RETRY')
                    return {'invocation_id':str(existing['invocation_id']),'status':existing['status']}
                if (str(existing['invocation_id'])!=str(reassess_invocation_id)
                        or expected_prompt_checksum is None or not can_reassess(existing,len(rows),context)
                        or conn.execute('SELECT 1 FROM platform.qa_review_approval WHERE run_id=%s',(run_id,)).fetchone()):
                    raise ValueError('QA_REASSESSMENT_NOT_ALLOWED')
            elif reassess_invocation_id is not None:
                raise ValueError('QA_REASSESSMENT_NOT_ALLOWED')
            settings=run['settings_snapshot'];model=(settings.get('model_routes') or {}).get('qa_review')
            if not model:raise ValueError('QA_MODEL_NOT_CONFIGURED')
            operator=conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
            if not operator:raise ValueError('OPERATOR_NOT_CONFIGURED')
            identity=uuid4()
            payload={'context':context,'comparison_id':str(comparison_id),'comparison_checksum':captured['comparison_checksum'],
                'operator_id':str(operator['operator_id']),'consent_recorded':True,
                'prompt':PROMPT,'prompt_checksum':digest(PROMPT),'schema':QAReviewV1.model_json_schema(),
                'schema_checksum':digest(QAReviewV1.model_json_schema())}
            if reassess_invocation_id is not None:
                payload['reassesses_invocation_id']=str(reassess_invocation_id)
            conn.execute("""INSERT INTO platform.agent_invocation(invocation_id,task_id,run_id,role,provider,model,prompt_version,context_checksum,input_json,status)
                VALUES(%s,%s,%s,'pilot_qa',%s,%s,%s,%s,%s,'QA_RESERVED')""",
                (identity,task_id,run_id,settings['ai']['provider_type'],model,PROMPT_VERSION,context_checksum,Jsonb(payload)))
            self.queue.event(conn,run_id,'QA_REASSESSMENT_AUTHORIZED' if reassess_invocation_id else 'QA_INTENT_RECORDED','QA_REVIEW',{'invocation_id':str(identity),'context_checksum':context_checksum,'automatic_retry':False,'reassesses_invocation_id':str(reassess_invocation_id) if reassess_invocation_id else None})
        return {'invocation_id':str(identity),'status':'QA_RESERVED'}

    def finish(self,task_id,invocation_id,output,trace):
        with self.queue.conn() as conn:
            self.queue.locked_task(conn,task_id)
            record=conn.execute("SELECT * FROM platform.agent_invocation WHERE invocation_id=%s AND task_id=%s AND role='pilot_qa' FOR UPDATE",(invocation_id,task_id)).fetchone()
            if not record or record['status']!='QA_RESERVED':raise ValueError('QA_RESULT_NOT_WRITABLE')
            raw=dict(output)
            for key,value in (('advisory_only',True),('qa_approved',False),('release_ready',False)):
                if key in raw and raw.pop(key) is not value:raise ValueError('QA_RESULT_FLAGS_INVALID')
            accepted=validate_qa_review(raw,record['input_json']['context'])
            safe_trace=checked_trace(trace,record)
            try:
                current=load_qa_context(self.queue,task_id,record['run_id'],record['input_json']['comparison_id'],connection=conn)
                fresh=current['context']['context_checksum']==record['context_checksum']
            except ValueError:
                fresh=False
            status='VALIDATED_NOT_APPROVED' if fresh else 'STALE_RESULT_NEEDS_REVIEW'
            conn.execute('UPDATE platform.agent_invocation SET status=%s,output_json=%s,duration_ms=%s WHERE invocation_id=%s',
                (status,Jsonb({'review':accepted,'review_checksum':digest(accepted),'trace':safe_trace,'qa_approved':False,'release_ready':False}),safe_trace['duration_ms'],invocation_id))
            self.queue.event(conn,record['run_id'],'QA_'+status,'QA_REVIEW',{'invocation_id':str(invocation_id),'qa_approved':False,'release_ready':False})
        return {'status':status,'qa_approved':False,'release_ready':False}

    def hold_uncertain(self,task_id,invocation_id):
        with self.queue.conn() as conn:
            self.queue.locked_task(conn,task_id)
            row=conn.execute("""UPDATE platform.agent_invocation SET status='QA_OUTCOME_UNKNOWN',output_json=%s
                WHERE invocation_id=%s AND task_id=%s AND role='pilot_qa' AND status='QA_RESERVED' RETURNING run_id""",
                (Jsonb({'error_code':'QA_OUTCOME_UNKNOWN','automatic_retry':False}),invocation_id,task_id)).fetchone()
            if not row:raise ValueError('QA_RESULT_NOT_WRITABLE')
            self.queue.event(conn,row['run_id'],'QA_OUTCOME_UNKNOWN','QA_REVIEW',{'invocation_id':str(invocation_id),'automatic_retry':False})


def can_reassess(record,count,context=None):
    """Bounded explicit clarification; new evidence may only enrich the same execution."""
    if count not in (1,2) or record['status']!='VALIDATED_NOT_APPROVED' or record['prompt_version']>=PROMPT_VERSION:
        return False
    previous=record['input_json'].get('context')
    if context is not None and previous!=context:
        if not same_execution_enrichment(previous,context):return False
    elif count==2:
        return False
    return (record['input_json'].get('prompt_checksum')!=digest(PROMPT)
        and public_record(record)['review']['status']=='NEEDS_REVIEW')


def same_execution_enrichment(previous,current):
    if not previous:return False
    # Removing only the new details must recover the entire old canonical context.
    from copy import deepcopy
    semantics=deepcopy(current.get('semantics') or {})
    if previous.get('version')==2 and current.get('version')==3:
        if not semantics.pop('execution_details',None):return False
    elif previous.get('version')==4 and current.get('version')==5:
        if not (semantics.get('execution_details') or {}).pop('runtime_options',None):return False
    else:return False
    try:
        canonical=build_qa_context(current['run_id'],current['specification_checksum'],current['evidence'],semantics)
        complete=build_qa_context(current['run_id'],current['specification_checksum'],current['evidence'],current['semantics'])
    except (ValueError,KeyError,TypeError):return False
    return canonical==previous and complete==current


def checked_trace(trace,record):
    expected={key:record[key] for key in ('provider','model','prompt_version','context_checksum')}
    expected.update(prompt_checksum=record['input_json']['prompt_checksum'],schema_checksum=record['input_json']['schema_checksum'],
        run_id=str(record['run_id']),status='VALIDATED_NOT_APPROVED')
    if any(trace.get(key)!=value for key,value in expected.items()):raise ValueError('QA_TRACE_BINDING_CHANGED')
    output=trace.get('output_checksum');duration=trace.get('duration_ms')
    if not isinstance(output,str) or not re.fullmatch('[a-f0-9]{64}',output) or type(duration) is not int or duration<0:
        raise ValueError('QA_TRACE_INVALID')
    try:safe_usage=checked_usage(trace.get('usage'))
    except ValueError:raise ValueError('QA_USAGE_INVALID') from None
    for key in ('input_tokens','output_tokens','total_tokens','attempts','transient_retries','output_corrections'):
        safe_usage.setdefault(key,None)
    return {**expected,'output_checksum':output,'duration_ms':duration,'usage':safe_usage,'qa_approved':False,'release_ready':False}


def public_record(row):
    context=row['input_json']['context']
    canonical=build_qa_context(context['run_id'],context['specification_checksum'],context['evidence'],context.get('semantics'))
    if (canonical!=context or context['context_checksum']!=row['context_checksum']
            or context['run_id']!=str(row['run_id'])):raise ValueError('QA_HISTORY_INTEGRITY_ERROR')
    if row['status'] not in ('QA_RESERVED','QA_OUTCOME_UNKNOWN','VALIDATED_NOT_APPROVED','STALE_RESULT_NEEDS_REVIEW'):
        raise ValueError('QA_HISTORY_STATUS_INVALID')
    review=None;trace=None
    if row['status'] in ('VALIDATED_NOT_APPROVED','STALE_RESULT_NEEDS_REVIEW'):
        output=row['output_json']
        stored=output['review']
        raw={key:value for key,value in stored.items() if key not in ('advisory_only','qa_approved','release_ready')}
        review=validate_qa_review(raw,context)
        if review!=stored or digest(review)!=output['review_checksum']:raise ValueError('QA_HISTORY_INTEGRITY_ERROR')
        trace=checked_trace(output['trace'],row)
    return {**{key:row[key] for key in ('status','provider','model','prompt_version','context_checksum','created_at')},
        'invocation_id':str(row['invocation_id']),'context':context,'review':review,
        'reassesses_invocation_id':row['input_json'].get('reassesses_invocation_id'),
        'usage':trace['usage'] if trace else None,'duration_ms':trace['duration_ms'] if trace else None,
        'qa_approved':False,'release_ready':False}
