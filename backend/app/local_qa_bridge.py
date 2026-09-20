"""Explicit single-Run Copilot QA bridge; never returns credentials or connection settings."""
import json
import os
import sys
from uuid import UUID
from .run_queue import RunQueue
from .qa_context import load_qa_context
from .qa_journal import QAJournal
from .qa_dispatch import claim_dispatch,check_claim


PUBLIC_ERRORS=frozenset({'QA_MODEL_CALL_CONSENT_REQUIRED','QA_DISPATCH_DISABLED',
    'QA_CONTEXT_VERSION_CHANGED','QA_NATIVE_PROFILE_REQUIRED','QA_CLAIM_SCOPE_MISMATCH',
    'QA_DISPATCH_ALREADY_CONSUMED','QA_NOT_DISPATCHABLE','QA_DISPATCH_CLAIM_EXPIRED_OR_LOST'})


def public_error(error):
    code=str(error)
    return code if type(error) is ValueError and code in PUBLIC_ERRORS else 'LOCAL_QA_REQUEST_FAILED'


def handle(queue,data):
    task=data['task_id'];run=UUID(data['run_id']);action=data['action']
    journal=QAJournal(queue)
    if action in ('claim','claim_authorized'):
        if action=='claim_authorized':
            if os.getenv('WORKBENCH_QA_DISPATCH_ENABLED')!='true':raise ValueError('QA_DISPATCH_DISABLED')
            with queue.conn() as conn:
                queue.locked_task(conn,task)
                pending=conn.execute("SELECT * FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND role='pilot_qa' ORDER BY created_at DESC,invocation_id DESC LIMIT 1",(task,run)).fetchone()
            if not pending:return {'status':'IDLE'}
            if pending['status']!='QA_RESERVED':return {'status':pending['status']}
            data={**data,'authorize_model_call':True,'comparison_id':pending['input_json']['comparison_id'],
                'context_checksum':pending['context_checksum']}
            from .qa_gateway import PROMPT,PROMPT_VERSION
            from .qa_contract import QAReviewV1
            from .sa_contract import digest
            if (pending['prompt_version']!=PROMPT_VERSION or pending['input_json']['prompt_checksum']!=digest(PROMPT)
                    or pending['input_json']['schema_checksum']!=digest(QAReviewV1.model_json_schema())):
                raise ValueError('QA_CONTEXT_VERSION_CHANGED')
        if data.get('authorize_model_call') is not True:
            raise ValueError('QA_MODEL_CALL_CONSENT_REQUIRED')
        if os.getenv('WORKBENCH_QA_DISPATCH_ENABLED')!='true':
            raise ValueError('QA_DISPATCH_DISABLED')
        captured=load_qa_context(queue,task,run,UUID(data['comparison_id']))
        context=captured['context'];snapshot=captured['run']['settings_snapshot']
        if context['context_checksum']!=data['context_checksum']:
            raise ValueError('QA_CONTEXT_VERSION_CHANGED')
        model=snapshot.get('model_routes',{}).get('qa_review')
        if snapshot['ai']['provider_type']!='LOCAL_COPILOT' or not model or not model.startswith('copilot/'):
            raise ValueError('QA_NATIVE_PROFILE_REQUIRED')
        saved=journal.reserve(task,run,data['comparison_id'],data['context_checksum'],True)
        if saved['status']!='QA_RESERVED':return saved
        token=claim_dispatch(queue,task,saved['invocation_id'])
        # All connection/profile secrets stay inside Docker.
        safe_run={key:captured['run'][key] for key in
            ('run_id','state','write_started','matches_current','lease_token','outcome_code')}
        safe_run['settings_snapshot']={'model_routes':{'qa_review':model}}
        return {'status':'DISPATCH_RESERVED','invocation_id':saved['invocation_id'],'claim_token':str(token),
            'run':safe_run,'context':context,
            'profile':{'enabled':True,'provider_type':'LOCAL_COPILOT','model_routes':{'qa_review':model}}}
    invocation=UUID(data['invocation_id']);token=UUID(data['claim_token'])
    with queue.conn() as conn:
        row=conn.execute('''SELECT a.* FROM platform.agent_invocation a
            JOIN platform.qa_dispatch_claim c USING(invocation_id)
            WHERE a.task_id=%s AND a.run_id=%s AND a.invocation_id=%s AND c.claim_token=%s
            AND a.role='pilot_qa' AND a.provider='LOCAL_COPILOT' ''',(task,run,invocation,token)).fetchone()
    if not row:raise ValueError('QA_CLAIM_SCOPE_MISMATCH')
    if action=='uncertain':
        journal.hold_uncertain(task,invocation)
        return {'status':'QA_OUTCOME_UNKNOWN'}
    check_claim(queue,invocation,token)
    if action=='check':
        if os.getenv('WORKBENCH_QA_DISPATCH_ENABLED')!='true':raise ValueError('QA_DISPATCH_DISABLED')
        current=load_qa_context(queue,task,run,row['input_json']['comparison_id'])
        if current['context']!=row['input_json']['context']:raise ValueError('QA_CONTEXT_VERSION_CHANGED')
        return {'status':'CLAIM_ACTIVE'}
    if action=='finish':
        return journal.finish(task,invocation,data['review'],data['trace'])
    raise ValueError('UNKNOWN_LOCAL_QA_ACTION')


def main():
    try:
        raw=sys.stdin.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('INPUT_TOO_LARGE')
        result=handle(RunQueue(os.environ['DATABASE_URL']),json.loads(raw))
        print(json.dumps(result,default=str,ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'status':'ERROR','code':public_error(error)}))
        raise SystemExit(1) from None


if __name__=='__main__':main()
