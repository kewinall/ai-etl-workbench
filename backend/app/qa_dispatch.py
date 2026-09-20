"""Internal one-consumption QA dispatch. No public route or model fallback."""
import os
from uuid import uuid4
from .qa_context import load_qa_context
from .qa_journal import QAJournal
from .qa_gateway import complete_qa_review


def claim_dispatch(queue,task_id,invocation_id):
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        row=conn.execute("SELECT status FROM platform.agent_invocation WHERE invocation_id=%s AND task_id=%s AND role='pilot_qa' FOR UPDATE",(invocation_id,task_id)).fetchone()
        if not row or row['status']!='QA_RESERVED':raise ValueError('QA_NOT_DISPATCHABLE')
        token=uuid4()
        created=conn.execute('''INSERT INTO platform.qa_dispatch_claim(invocation_id,claim_token)
            VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING claim_token''',(invocation_id,token)).fetchone()
        if not created:raise ValueError('QA_DISPATCH_ALREADY_CONSUMED')
    return token


def check_claim(queue,invocation_id,token):
    with queue.conn() as conn:
        row=conn.execute('''SELECT 1 FROM platform.qa_dispatch_claim c JOIN platform.agent_invocation a USING(invocation_id)
            WHERE c.invocation_id=%s AND c.claim_token=%s AND c.expires_at>clock_timestamp()
            AND a.role='pilot_qa' AND a.status='QA_RESERVED' ''',(invocation_id,token)).fetchone()
    if not row:raise ValueError('QA_DISPATCH_CLAIM_EXPIRED_OR_LOST')


def dispatch_qa(queue,repo,task_id,run_id,comparison_id,context_checksum,*,authorize_model_call=False,completion=None):
    if authorize_model_call is not True:raise ValueError('QA_MODEL_CALL_CONSENT_REQUIRED')
    if os.getenv('WORKBENCH_QA_DISPATCH_ENABLED')!='true':raise ValueError('QA_DISPATCH_DISABLED')
    captured=load_qa_context(queue,task_id,run_id,comparison_id)
    if captured['context']['context_checksum']!=context_checksum:raise ValueError('QA_CONTEXT_VERSION_CHANGED')
    snapshot=captured['run']['settings_snapshot']
    profile=repo.ai_profile(snapshot['ai_profile_id'])
    if not profile:raise ValueError('QA_PROFILE_NOT_FOUND')
    # Windows Copilot login is not available in the Docker model worker.
    if profile['provider_type']=='LOCAL_COPILOT':raise ValueError('QA_NATIVE_COPILOT_WORKER_REQUIRED')
    secret=repo.read_secret_at_version(profile['secret_ref'],snapshot['credential_versions']['ai']) if profile.get('secret_ref') else None
    journal=QAJournal(queue)
    reserved=journal.reserve(task_id,run_id,comparison_id,context_checksum,True)
    if reserved['status']!='QA_RESERVED':return {**reserved,'qa_approved':False,'release_ready':False}
    identity=reserved['invocation_id'];token=claim_dispatch(queue,task_id,identity)
    try:
        def guarded_completion(**kwargs):
            check_claim(queue,identity,token)
            current=load_qa_context(queue,task_id,run_id,comparison_id)
            if current['context']!=captured['context'] or current['run']['settings_snapshot']!=snapshot:
                raise ValueError('QA_CONTEXT_VERSION_CHANGED')
            if completion is not None:return completion(**kwargs)
            from litellm import completion as provider
            return provider(**kwargs)
        review,trace=complete_qa_review(captured['run'],profile,captured['context'],secret=secret,completion=guarded_completion)
        check_claim(queue,identity,token)
        result=journal.finish(task_id,identity,review,trace)
        return {**result,'invocation_id':str(identity)}
    except Exception:
        # Persist uncertainty, never auto-submit a replacement request. If PG is
        # unavailable, the immutable claim still prevents another dispatch.
        try:journal.hold_uncertain(task_id,identity)
        except Exception:pass
        return {'invocation_id':str(identity),'status':'QA_OUTCOME_UNKNOWN','qa_approved':False,'release_ready':False}
    finally:
        secret=None
