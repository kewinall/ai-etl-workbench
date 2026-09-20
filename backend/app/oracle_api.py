"""Version-scoped answers; explicit no-store review, never encryption secrets."""
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from . import oracle_store


class OracleSaveRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    document: str=Field(min_length=1,max_length=8*1024*1024)


class OracleApprovalRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    document_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: StrictBool


def create_oracle_router(queue):
    router=APIRouter(prefix='/api/tasks',tags=['Expected result oracle'])
    def call(function,*args):
        try:return function(queue,*args)
        except HTTPException:raise
        except ValueError:
            raise HTTPException(409,detail={'code':'ORACLE_REVIEW_REQUIRED','message':'答案格式、型別或版本不符，或上游核准已失效；請重新核對。'}) from None
        except Exception:
            # A response/connection failure may occur after commit; do not claim rollback.
            raise HTTPException(503,detail={'code':'ORACLE_SERVICE_UNAVAILABLE','message':'答案服務暫時不可用，保存結果可能需要重新核對；未派發 ETL。'}) from None

    @router.get('/{task_id}/runs/{run_id}/specifications/{specification_id}/oracle-editor-context')
    def editor_context(task_id:str,run_id:UUID,specification_id:UUID):
        return call(oracle_store.oracle_editor_context,task_id,run_id,specification_id)

    @router.get('/{task_id}/runs/{run_id}/specifications/{specification_id}/oracles')
    def history(task_id:str,run_id:UUID,specification_id:UUID):
        return call(oracle_store.list_oracles,task_id,run_id,specification_id)

    @router.get('/{task_id}/runs/{run_id}/specifications/{specification_id}/oracles/{oracle_id}/review')
    def review(task_id:str,run_id:UUID,specification_id:UUID,oracle_id:UUID,
               offset:int=Query(default=0,ge=0),limit:int=Query(default=50,ge=1,le=100)):
        result=call(oracle_store.review_oracle,task_id,run_id,specification_id,oracle_id,offset,limit)
        return JSONResponse(result,headers={'Cache-Control':'no-store','Pragma':'no-cache','X-Content-Type-Options':'nosniff'})

    @router.post('/{task_id}/runs/{run_id}/specifications/{specification_id}/oracles',status_code=201)
    def save(task_id:str,run_id:UUID,specification_id:UUID,data:OracleSaveRequest):
        try:content=data.document.encode('utf-8')
        except UnicodeError:raise HTTPException(422,detail='答案必須是有效 UTF-8 文字') from None
        return call(oracle_store.save_oracle,task_id,run_id,specification_id,content)

    @router.post('/{task_id}/runs/{run_id}/specifications/{specification_id}/oracles/{oracle_id}/approve')
    def approve(task_id:str,run_id:UUID,specification_id:UUID,oracle_id:UUID,data:OracleApprovalRequest):
        if data.confirmed is not True:
            raise HTTPException(422,detail={'code':'ORACLE_CONFIRMATION_REQUIRED','message':'請先確認指定版本的標準答案。'})
        return call(oracle_store.approve_oracle,task_id,run_id,specification_id,oracle_id,data.document_checksum)
    return router
