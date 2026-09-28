"""Explicit website consent for new Pilot target creation and one Hop attempt."""
import os
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictBool
from .hop_dispatch import offer,enqueue


class DispatchHop(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: StrictBool
    specification_id: UUID
    binding_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')


class ReconcilePreparation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    binding_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    evidence_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    target_exists: StrictBool
    observed_row_count: int|None=Field(default=None,strict=True,ge=0,le=9223372036854775807)
    engine_stopped: StrictBool
    target_checked: StrictBool
    confirmed: StrictBool


class RecoverComparison(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: StrictBool
    binding_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')


def read(queue,task_id,run_id):
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        if not conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone():raise ValueError('RUN_NOT_FOUND')
        saved=conn.execute('''SELECT request_id,status,outcome_code,created_at,claimed_at,finished_at,
            (status='CLAIMED' AND claimed_at<clock_timestamp()-interval '15 minutes') AS overdue
            FROM platform.hop_dispatch_request WHERE run_id=%s''',(run_id,)).fetchone()
        candidate=None;reason='先完成 SA 人工交接、Developer 設計、規格與標準答案核准。'
        if not saved:
            latest=conn.execute('SELECT specification_id FROM platform.specification WHERE task_id=%s AND run_id=%s ORDER BY version DESC LIMIT 1',(task_id,run_id)).fetchone()
            if latest:
                try:
                    result=offer(queue,conn,task_id,run_id,latest['specification_id'])
                    candidate={'specification_id':str(latest['specification_id']),'binding_checksum':result['binding_checksum'],
                        'ddl':result['ddl'],'target_schema':result['specification']['target_schema'],'target_table':result['specification']['target_table']}
                    reason=None
                except ValueError:pass
    return {'request':saved,'offer':candidate,'blocked_reason':reason,
        'dispatch_enabled':os.getenv('WORKBENCH_EXECUTION_ENABLED')=='true','qa_approved':False,'release_ready':False}


def create_hop_dispatch_router(queue):
    router=APIRouter(prefix='/api/tasks',tags=['Hop dispatch'])
    def call(fn):
        try:return fn()
        except ValueError as error:
            if str(error) in ('TASK_NOT_FOUND','RUN_NOT_FOUND'):raise HTTPException(404,detail='找不到 Task 或執行版本') from None
            raise HTTPException(409,detail='執行條件或版本已變更，請重新核對；不會自動重跑') from None
    @router.get('/{task_id}/runs/{run_id}/hop-dispatch')
    def status(task_id:str,run_id:UUID):return call(lambda:read(queue,task_id,run_id))
    @router.post('/{task_id}/runs/{run_id}/hop-dispatch')
    def dispatch(task_id:str,run_id:UUID,data:DispatchHop):
        return call(lambda:enqueue(queue,task_id,run_id,data.specification_id,data.binding_checksum,data.confirmed))
    from . import comparison_recovery as recovery
    @router.get('/{task_id}/runs/{run_id}/comparison-recovery')
    def recovery_status(task_id:str,run_id:UUID):
        return call(lambda:recovery.read(queue,task_id,run_id))
    @router.post('/{task_id}/runs/{run_id}/comparison-recovery')
    def recover(task_id:str,run_id:UUID,data:RecoverComparison):
        return call(lambda:recovery.enqueue(queue,task_id,run_id,data.binding_checksum,data.confirmed))
    from . import hop_preparation_reconciliation as reconciliation
    @router.get('/{task_id}/runs/{run_id}/hop-preparation-reconciliation')
    def reconciliation_status(task_id:str,run_id:UUID):
        return call(lambda:reconciliation.read(queue,task_id,run_id))
    @router.post('/{task_id}/runs/{run_id}/hop-preparation-reconciliation')
    def reconcile(task_id:str,run_id:UUID,data:ReconcilePreparation):
        return call(lambda:reconciliation.close(queue,task_id,run_id,data.model_dump()))
    return router
