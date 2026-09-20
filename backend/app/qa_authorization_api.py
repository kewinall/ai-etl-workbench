"""Website QA authorization; provider invocation belongs to the native worker."""
import os
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .qa_context import load_qa_context
from .qa_contract import QAReviewV1
from .qa_gateway import PROMPT
from .qa_journal import QAJournal,can_reassess
from .sa_contract import digest


class AuthorizeQA(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: StrictBool
    comparison_id: UUID
    context_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    prompt_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    schema_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    model: str=Field(min_length=1,max_length=200)
    reassess_invocation_id: UUID | None=None


def offer(queue,task_id,run_id):
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        run=conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone()
        if not run:raise ValueError('RUN_NOT_FOUND')
        records=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa' ORDER BY created_at DESC,invocation_id DESC",(run_id,)).fetchall()
        existing=records[0] if records else None
        comparison=conn.execute('SELECT comparison_id FROM platform.task_run_result_comparison WHERE run_id=%s ORDER BY created_at DESC,comparison_id DESC LIMIT 1',(run_id,)).fetchone()
        captured=None
        if comparison:
            try:captured=load_qa_context(queue,task_id,run_id,comparison['comparison_id'],connection=conn)
            except ValueError:pass
        reassessment=bool(existing and captured
            and can_reassess(existing,len(records),captured['context'])
            and not conn.execute('SELECT 1 FROM platform.qa_review_approval WHERE run_id=%s',(run_id,)).fetchone())
    model=run['settings_snapshot'].get('model_routes',{}).get('qa_review')
    native=run['settings_snapshot']['ai']['provider_type']=='LOCAL_COPILOT' and bool(model and model.startswith('copilot/'))
    return {'eligible':bool(captured and native and (not existing or reassessment)),
        'reassess_invocation_id':str(existing['invocation_id']) if reassessment else None,
        'dispatch_enabled':os.getenv('WORKBENCH_QA_DISPATCH_ENABLED')=='true',
        'comparison_id':str(comparison['comparison_id']) if comparison else None,
        'context_checksum':captured['context']['context_checksum'] if captured else None,
        'model':model,'prompt_checksum':digest(PROMPT),'schema_checksum':digest(QAReviewV1.model_json_schema()),
        'invocation':{'invocation_id':str(existing['invocation_id']),'status':existing['status']} if existing else None,
        'qa_approved':False,'release_ready':False}


def create_qa_authorization_router(queue):
    router=APIRouter(prefix='/api/tasks',tags=['QA authorization'])
    def call(fn):
        try:return fn()
        except ValueError as error:
            if str(error) in ('TASK_NOT_FOUND','RUN_NOT_FOUND'):raise HTTPException(404,detail='找不到指定 Task 或版本') from None
            raise HTTPException(409,detail='QA 版本、證據或派發條件已變更，請重新載入') from None
    @router.get('/{task_id}/runs/{run_id}/qa-authorization')
    def get_offer(task_id:str,run_id:UUID):return call(lambda:offer(queue,task_id,run_id))
    @router.post('/{task_id}/runs/{run_id}/qa-authorization')
    def authorize(task_id:str,run_id:UUID,data:AuthorizeQA):
        def action():
            current=offer(queue,task_id,run_id)
            if not current['dispatch_enabled'] or not current['context_checksum'] or not data.confirmed:
                raise ValueError('QA_AUTHORIZATION_BLOCKED')
            if any(str(getattr(data,key))!=current[key] for key in
                ('comparison_id','context_checksum','prompt_checksum','schema_checksum','model')):
                raise ValueError('QA_AUTHORIZATION_CHANGED')
            if not data.model.startswith('copilot/'):raise ValueError('QA_NATIVE_PROFILE_REQUIRED')
            if data.reassess_invocation_id is not None:
                if not current['eligible'] or str(data.reassess_invocation_id)!=current.get('reassess_invocation_id'):
                    raise ValueError('QA_REASSESSMENT_NOT_ALLOWED')
                return QAJournal(queue).reserve(task_id,run_id,data.comparison_id,data.context_checksum,True,
                    reassess_invocation_id=data.reassess_invocation_id,expected_prompt_checksum=data.prompt_checksum)
            return QAJournal(queue).reserve(task_id,run_id,data.comparison_id,data.context_checksum,True)
        return call(action)
    return router
