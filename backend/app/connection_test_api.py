"""Explicit SELECT 1 against the saved ETL connection; never environment fallback."""
from time import monotonic
from fastapi import APIRouter, HTTPException
import vertica_python
from .hop_metadata import vertica_metadata_json


def saved_connection(repo, identity):
    group=repo.setting('data_connections_targets',{})
    value=group.get('etl_qa') if isinstance(group,dict) else None
    if not isinstance(value,dict) or value.get('connection_id')!=identity:
        raise ValueError('SAVED_CONNECTION_REQUIRED')
    connection={key:value.get(key) for key in ('connection_id','host','port','database','user','tlsmode')}
    if isinstance(connection['port'],str) and connection['port'].isdigit():connection['port']=int(connection['port'])
    connection['type']='VERTICA'
    vertica_metadata_json(connection)
    return connection


def probe(repo,identity):
    started=monotonic()
    connection=saved_connection(repo,identity)
    version=repo.secret_version('connection:'+identity)
    secret=repo.read_secret_at_version('connection:'+identity,version)
    if not isinstance(secret,str) or not secret or '\x00' in secret:raise ValueError('SAVED_SECRET_REQUIRED')
    config={key:connection[key] for key in ('host','port','database','user','tlsmode')}
    config.update(password=secret,connection_timeout=10)
    try:
        with vertica_python.connect(**config) as db:
            cursor=db.cursor();cursor.execute('SELECT 1')
            if list(cursor.fetchone())!=[1]:raise ValueError('PROBE_RESULT_INVALID')
        if saved_connection(repo,identity)!=connection or repo.secret_version('connection:'+identity)!=version:
            raise ValueError('SAVED_CONNECTION_CHANGED')
    finally:
        config.clear();secret=None
    return {'status':'CONNECTED','scope':'SAVED_CONNECTION_SELECT_1_ONLY',
            'duration_ms':round((monotonic()-started)*1000),'execution_authorized':False}


def create_connection_test_router(repo):
    router=APIRouter(prefix='/api/settings/connections',tags=['saved connection test'])
    @router.post('/{connection_id}/test')
    def test_saved(connection_id:str):
        try:return probe(repo,connection_id)
        except Exception:
            raise HTTPException(409,detail={'code':'SAVED_CONNECTION_TEST_FAILED',
                'message':'已保存連線測試未通過：請檢查連線、TLS、保管庫機密與網路；未改用環境預設。'}) from None
    return router
