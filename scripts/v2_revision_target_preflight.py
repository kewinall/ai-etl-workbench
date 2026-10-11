"""New revision case SELECT-only preflight; vault values stay inside API memory."""
import json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
state=json.loads((root/'runtime-temp/v2-revision-live-state.json').read_text(encoding='utf-8-sig'))
assert state['project_id']=='346e9419-4b0e-4ba7-ad29-1756ca7da833'
assert state['target'] in ('ui_accept_revision_20261011_v1','ui_accept_revision_20261011_v2')
if state['target'].endswith('_v2'):
 assert state['failure_closed'] and state['failed_execution']['target']=='ui_accept_revision_20261011_v1'
assert state.get('specification_id') and state.get('oracle_approved') is True
code=r'''
import json,os,sys
import vertica_python
from app.run_queue import RunQueue
from app.repository import PostgresRepository
from app.specification_store import context
from app.hop_connection_runtime import connection_runtime
data=json.loads(sys.argv[1]);q=RunQueue(os.environ['DATABASE_URL']);repo=PostgresRepository(os.environ['DATABASE_URL'])
with q.conn() as conn:
 run,_=context(q,conn,data['task_id'],data['run_id'])
 assert str(run['project_id'])==data['project_id'] and not run['write_started']
 assert run['input_snapshot']['target_config']['table']==data['target']
 assert run['input_snapshot']['source_config']['sources'][0]['checksum']==data['source_sha256']
 assert q.matches_current(conn,q.locked_task(conn,data['task_id']),run)
snapshot=run['settings_snapshot'];rows=[]
with connection_runtime(repo,snapshot,snapshot['checksum']) as runtime:
 config={k:snapshot['connection'][k] for k in ('host','port','database','user','tlsmode')}
 config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
 try:
  with vertica_python.connect(**config) as db:
   cur=db.cursor()
   for table in ['ui_accept_revision_20261011_v1','ui_accept_revision_20261011_v2']:
    cur.execute('SELECT COUNT(*) FROM v_catalog.tables WHERE table_schema=%s AND table_name=%s',('ai_sample',table))
    exists=cur.fetchone()[0]!=0
    if table==data['target'] or data['target'].endswith('_v1'):
     assert not exists,'NEW_TARGET_ALREADY_EXISTS'
    else:
     assert exists,'RETAINED_FAILURE_TARGET_MISSING'
     cur.execute('SELECT COUNT(*) FROM "ai_sample"."ui_accept_revision_20261011_v1"')
     assert cur.fetchone()[0]==0,'RETAINED_FAILURE_TARGET_CHANGED'
    rows.append(dict(target='ai_sample.'+table,exists=exists))
 finally:config.clear()
print(json.dumps(dict(task_id=data['task_id'],run_id=data['run_id'],target=data['target'],source_sha256=data['source_sha256'],targets=rows,write_started=False,status='PASS')))
'''
result=subprocess.run(['wsl.exe','-d','RockyLinux9','-u','root','--','docker','exec','-i',
 'ai-etl-stage-guidance-ui-api-1','python','-m','app.bootstrap','python','-c',code,json.dumps(state)],
 capture_output=True,text=True,encoding='utf-8')
if result.returncode:raise SystemExit('TARGET_PREFLIGHT_FAILED_NO_WRITE_NO_SECRET_OUTPUT')
proof=json.loads(result.stdout)
(root/'runtime-temp/v2-revision-target-preflight.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
