from fastapi import APIRouter, HTTPException
from .worker_presence import WorkerRegistry


def create_runtime_router(queue):
    router = APIRouter(prefix='/api/runtime', tags=['Runtime status'])

    @router.get('/workers')
    def workers():
        try:
            return WorkerRegistry(queue).snapshot()
        except Exception:
            raise HTTPException(503, detail={'code': 'WORKER_STATUS_UNAVAILABLE', 'message': '無法確認 Worker 存活狀態；請檢查平台資料庫'}) from None

    return router
