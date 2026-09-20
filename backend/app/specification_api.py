"""Read-only design preview on existing Task/Run/Naming storage; no new Task system."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from .etl_specification import EtlSpecificationV1, compilation_plan
from .delivery_compiler import compile_delivery_components
from . import specification_store
from .specification_editor import editor_context
from pydantic import BaseModel, ConfigDict, Field


class SpecificationApprovalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')


def create_specification_router(queue):
    router = APIRouter(prefix='/api/tasks', tags=['ETL specification preview'])

    def preview(task_id, run_id, specification, compiler, persist=False):
        if specification.run_id != run_id:
            raise HTTPException(409, detail='規格 Run ID 與路徑不一致')
        try:
            with queue.conn() as conn:
                run, naming = specification_store.context(queue, conn, task_id, run_id)
                # Require the latest contract, including a newer unconfirmed draft.
                # Never silently fall back to a previous confirmed version.
                if not naming:
                    return {'status': 'INVALID', 'issues': [{'code': 'SPEC_NAMING_MISSING', 'field_path': 'naming', 'message': '尚無此 Task 的命名契約'}], 'execution_authorized': False}
                result = compiler(specification.model_dump(mode='json'), run, naming)
                return specification_store.save(queue, conn, task_id, run_id, result) if persist else result
        except HTTPException:
            raise
        except ValueError as error:
            if str(error) == 'TASK_NOT_FOUND':
                raise HTTPException(404, detail='找不到指定 Task') from None
            raise HTTPException(422, detail='規格或保存的契約內容不合法') from None
        except Exception:
            raise HTTPException(503, detail='規格預覽服務不可用；未保存規格或派發工作') from None

    @router.post('/{task_id}/runs/{run_id}/specification/validate')
    def validate(task_id: str, run_id: UUID, specification: EtlSpecificationV1):
        return preview(task_id, run_id, specification, compilation_plan)

    @router.post('/{task_id}/runs/{run_id}/specification/compile-preview')
    def compile_preview(task_id: str, run_id: UUID, specification: EtlSpecificationV1):
        return preview(task_id, run_id, specification, compile_delivery_components)

    @router.post('/{task_id}/runs/{run_id}/specifications')
    def save(task_id: str, run_id: UUID, specification: EtlSpecificationV1):
        return preview(task_id, run_id, specification, compilation_plan, persist=True)

    @router.post('/{task_id}/runs/{run_id}/specifications/{specification_id}/approve')
    def approve(task_id: str, run_id: UUID, specification_id: UUID, request: SpecificationApprovalRequest):
        try:
            with queue.conn() as conn:
                return specification_store.approve(queue, conn, task_id, run_id, specification_id, request.content_checksum)
        except HTTPException:
            raise
        except ValueError as error:
            if str(error) == 'TASK_NOT_FOUND':
                raise HTTPException(404, detail='找不到指定 Task') from None
            raise HTTPException(422, detail='保存的規格內容不合法') from None
        except Exception:
            raise HTTPException(503, detail='規格核准服務不可用；未派發工作') from None

    @router.get('/{task_id}/runs/{run_id}/specifications')
    def history(task_id: str, run_id: UUID):
        try:
            with queue.conn() as conn:
                run, naming = specification_store.context(queue, conn, task_id, run_id)
                rows = conn.execute('SELECT s.specification_id,s.version,s.spec_json,s.content_checksum,s.is_current,s.created_at,a.approval_id,a.created_at AS approved_at FROM platform.specification s LEFT JOIN platform.specification_approval a USING(specification_id) WHERE s.task_id=%s AND s.run_id=%s ORDER BY s.version DESC', (task_id, run_id)).fetchall()
                latest = conn.execute('SELECT specification_id FROM platform.specification WHERE task_id=%s ORDER BY version DESC LIMIT 1', (task_id,)).fetchone()
                for row in rows:
                    valid = specification_store.validate_specification(row['spec_json'], run, naming) if naming else {'status': 'INVALID'}
                    row['reviewable'] = bool(row['is_current'] and latest['specification_id'] == row['specification_id'] and valid['status'] == 'VALIDATED_NOT_APPROVED' and valid['specification_checksum'] == row['content_checksum'])
                    row['approval_effective'] = bool(row['approval_id'] and row['reviewable'])
                    row['execution_authorized'] = False
                return {'items': rows, 'execution_authorized': False}
        except HTTPException:
            raise
        except ValueError as error:
            if str(error) == 'TASK_NOT_FOUND':
                raise HTTPException(404, detail='找不到指定 Task') from None
            raise HTTPException(422, detail='保存的規格內容不合法') from None
        except Exception:
            raise HTTPException(503, detail='規格歷史服務不可用') from None

    @router.get('/{task_id}/runs/{run_id}/specification/editor-context')
    def editor(task_id: str, run_id: UUID):
        try:
            with queue.conn() as conn:
                run, naming = specification_store.context(queue, conn, task_id, run_id)
                return editor_context(run, naming)
        except HTTPException:
            raise
        except ValueError as error:
            if str(error) == 'TASK_NOT_FOUND':
                raise HTTPException(404, detail='找不到指定 Task') from None
            raise HTTPException(422, detail='編輯欄位契約不合法') from None
        except Exception:
            raise HTTPException(503, detail='規格編輯資料不可用') from None

    @router.get('/{task_id}/runs/{run_id}/specifications/{specification_id}/sdm-preview')
    def sdm_preview(task_id:str,run_id:UUID,specification_id:UUID):
        from .sdm_preview import approved_sdm_preview
        try:
            return approved_sdm_preview(queue,task_id,run_id,specification_id)
        except HTTPException:raise
        except ValueError as error:
            if str(error)=='TASK_NOT_FOUND':raise HTTPException(404,detail='找不到指定 Task') from None
            raise HTTPException(409,detail='SDM 預覽需要目前有效且已核准的規格；請重新確認版本。') from None
        except Exception:
            raise HTTPException(503,detail='SDM 預覽服務不可用；未產生交付檔案。') from None

    def sdm_error(error):
        if isinstance(error, HTTPException):
            raise error
        if isinstance(error, ValueError):
            if str(error) in ('TASK_NOT_FOUND', 'SDM_NOT_FOUND'):
                raise HTTPException(404, detail='找不到指定 SDM 候選文件或 Task') from None
            raise HTTPException(409, detail='SDM 版本、檔案或儲存設定無效；請重新確認，未開放交付。') from None
        raise HTTPException(503, detail='SDM 候選文件服務不可用；未開放交付。') from None

    @router.post('/{task_id}/runs/{run_id}/specifications/{specification_id}/sdm-candidate')
    def save_sdm(task_id: str, run_id: UUID, specification_id: UUID, request: SpecificationApprovalRequest):
        from .sdm_store import save_candidate
        try:
            return save_candidate(queue, task_id, run_id, specification_id, request.content_checksum)
        except Exception as error:
            sdm_error(error)

    @router.get('/{task_id}/runs/{run_id}/sdm-candidates')
    def sdm_history(task_id: str, run_id: UUID):
        from .sdm_store import candidate_history
        try:
            return candidate_history(queue, task_id, run_id)
        except Exception as error:
            sdm_error(error)

    @router.get('/{task_id}/runs/{run_id}/sdm-candidates/{sdm_id}/download')
    def download_sdm(task_id: str, run_id: UUID, sdm_id: UUID):
        from .sdm_store import download_candidate
        try:
            metadata, content = download_candidate(queue, task_id, run_id, sdm_id)
            return Response(content, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': f'attachment; filename="SDM-candidate-{sdm_id}.xlsx"',
                         'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                         'X-SDM-Status': metadata['status'], 'X-Content-SHA256': metadata['checksum']})
        except Exception as error:
            sdm_error(error)

    return router
