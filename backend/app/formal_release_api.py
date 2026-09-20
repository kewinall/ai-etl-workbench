"""Formal delivery gate. Portability results cannot be submitted over HTTP."""
from uuid import UUID
from fastapi import APIRouter,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field,StrictBool
from . import release_store


class PrepareRelease(BaseModel):
    model_config=ConfigDict(extra='forbid')
    qa_binding_checksum:str=Field(pattern=r'^[a-f0-9]{64}$')
    confirmed:StrictBool


class ApproveRelease(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_id:UUID
    binding_checksum:str=Field(pattern=r'^[a-f0-9]{64}$')
    confirmed:StrictBool


def create_formal_release_router(queue,repo):
    router=APIRouter(prefix='/api/tasks',tags=['Formal release'])
    def call(operation):
        try:return operation()
        except ValueError as error:
            if str(error) in ('TASK_NOT_FOUND','RUN_NOT_FOUND','RELEASE_NOT_FOUND'):
                raise HTTPException(404,detail='找不到指定版本或交付包') from None
            raise HTTPException(409,detail='交付條件、核准或證據已變更；請重新載入並核對') from None
    @router.get('/{task_id}/runs/{run_id}/release')
    def get_status(task_id:str,run_id:UUID):return call(lambda:release_store.status(queue,repo,task_id,run_id))
    @router.post('/{task_id}/runs/{run_id}/release/candidate')
    def prepare(task_id:str,run_id:UUID,data:PrepareRelease):
        if not data.confirmed:raise HTTPException(409,detail='請確認候選封裝及隔離驗證範圍')
        return call(lambda:release_store.prepare(queue,repo,task_id,run_id,data.qa_binding_checksum))
    @router.post('/{task_id}/runs/{run_id}/release/approve')
    def approve(task_id:str,run_id:UUID,data:ApproveRelease):
        return call(lambda:release_store.approve(queue,repo,task_id,run_id,data.candidate_id,data.binding_checksum,data.confirmed))
    @router.get('/{task_id}/runs/{run_id}/release/{release_id}/download')
    def download(task_id:str,run_id:UUID,release_id:UUID):
        content=call(lambda:release_store.download(queue,repo,task_id,run_id,release_id))
        return Response(content,media_type='application/zip',headers={
            'Content-Disposition':f'attachment; filename="release-{release_id}.zip"','Cache-Control':'no-store',
            'X-Content-Type-Options':'nosniff'})
    return router
