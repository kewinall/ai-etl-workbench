"""Fixed original Pilot, fixed accepted Tasks, GET only. Never forwards writes."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.encoders import jsonable_encoder
from .workflow_status import summarize

TASKS={'TASK-20260917-0007':'8d423121-2125-422c-830f-2d882e973b4b',
       'TASK-20260928-0001':'7974a406-4f6b-4fa7-801b-7204dbf3b4d7'}
PREFIX='/api/evidence/pilot'

def allowed(path):
    parts=path.split('/')
    if path in ('projects','tasks','health','ready'):return True
    if len(parts)>=2 and parts[0]=='tasks':return parts[1] in TASKS and all(p not in ('.','..','') for p in parts)
    if len(parts)>=2 and parts[0]=='projects':return parts[1] in TASKS.values() and (len(parts)==2 or parts[2]=='tasks')
    return False

def origin():
    value=os.getenv('WORKBENCH_EVIDENCE_ORIGIN')
    if value not in ('http://evidence-bridge:8080','http://127.0.0.1:5183'):
        raise HTTPException(503,detail='既有真實證據來源未設定；未以合成資料替代。')
    return value

def fetch(path):
    if not allowed(path):raise HTTPException(404,detail='此唯讀來源僅開放已驗收的 CSV／Excel 案例。')
    try:
        with urlopen(Request(origin()+'/api/'+path,method='GET'),timeout=15) as reply:
            headers={key:reply.headers[key] for key in ('Content-Disposition','X-Content-SHA256','X-SDM-Status') if key in reply.headers}
            return reply.read(),reply.headers.get('Content-Type','application/json'),headers
    except HTTPError as exc:
        raise HTTPException(404 if exc.code==404 else 503,detail='原始證據不可確認，操作停用。') from None
    except (URLError,OSError):
        raise HTTPException(503,detail='原始證據來源不可用；未以合成資料替代。') from None

def document(path):return json.loads(fetch(path)[0])

def urls(value):
    if isinstance(value,list):return [urls(item) for item in value]
    if isinstance(value,dict):
        return {key:(PREFIX+item[4:] if key.endswith('_url') and isinstance(item,str) and item.startswith('/api/') else urls(item)) for key,item in value.items()}
    return value

def workflow(task_id,run_id):
    base=f'tasks/{task_id}/runs/{run_id}'
    run=document(base);runs=document(f'tasks/{task_id}/runs')['runs']
    sa=document(base+'/sa-invocation');qa=document(base+'/qa-authorization')
    qa['invocation']=document(base+'/qa-review').get('invocation')
    result=summarize(run,latest_run_id=runs[0]['run_id'],sa=sa,
        sa_approval=document(base+'/sa-approval'),developer=document(base+'/developer'),
        specifications=document(base+'/specifications')['items'],hop=document(base+'/hop-dispatch'),
        qa=qa,qa_approval=document(base+'/qa-approval'),release=document(base+'/release'))
    result.update(matches_current=False,waiting=False,read_only_source=True,
                  source_scope_note='既有真實 CSV／Excel 執行證據；只讀來源，不能替代 5197 新版操作驗收。')
    for stage in result['stages']:
        stage.update(can_operate=False,blocked_reason='既有真實證據只讀檢視；所有核准、模型及執行入口停用。')
    # Source eligibility describes its original environment, not this GET-only view.
    # Keep genuine downloads available, but never advertise writable operations.
    for operation in result['operation_qualifications'].values():
        if operation['type'] != 'DOWNLOAD':
            operation.update(enabled=False,blocked_reason='既有真實證據只讀檢視；所有核准、模型及執行入口停用。')
    if result['next_action']['type'] != 'DOWNLOAD':
        result['next_action']['operation_enabled']=False
    return result

def create_evidence_router():
    router=APIRouter(prefix=PREFIX,tags=['Fixed read-only historical evidence'])
    @router.get('/{path:path}')
    def read(path:str):
        if not allowed(path):raise HTTPException(404,detail='證據入口不在允許清單。')
        parts=path.split('/')
        if len(parts)==5 and parts[0]=='tasks' and parts[2]=='runs' and parts[4]=='workflow-status':
            return JSONResponse(jsonable_encoder(urls(workflow(parts[1],parts[3]))),headers={'Cache-Control':'no-store'})
        raw,kind,saved_headers=fetch(path)
        headers={'Cache-Control':'no-store','X-Evidence-Mode':'GET_ONLY_ORIGINAL_PILOT'}
        headers.update(saved_headers)
        if 'json' not in kind:return Response(raw,media_type=kind,headers=headers)
        data=json.loads(raw)
        if path=='projects':data=[p for p in data if p['project_id'] in TASKS.values()]
        if path=='tasks' or path.endswith('/tasks') and path.startswith('projects/'):
            data=[t for t in data if t['id'] in TASKS]
        return JSONResponse(urls(data),headers=headers)
    return router
