"""SELECT-only independent readback of the authorized new missing-column case."""
import json, subprocess, urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[1]
state=json.loads((root/'runtime-temp/v2-revision-live-state.json').read_text(encoding='utf-8-sig'))
assert state['project_id']=='346e9419-4b0e-4ba7-ad29-1756ca7da833'
if state.get('failed_execution'):
    state={**state,**state['failed_execution']}
assert state['target']=='ui_accept_revision_20261011_v1'
base='http://127.0.0.1:5197/api/tasks/'+state['task_id']+'/runs/'+state['run_id']
with urllib.request.urlopen(base) as response: run=json.load(response)
assert run['write_started'] and run['outcome_code']=='HOP_EXECUTION_FAILED'
events=run['events']
assert sum(e['event_type']=='WRITE_STARTED' for e in events)==1
failed=[e['event_context'] for e in events if e['event_type']=='HOP_EXECUTION_FAILED']
assert len(failed)==1 and failed[0]['exit_code']==1
observed=[e['event_context'] for e in events if e['event_type']=='SYNTHETIC_FAILURE_TARGET_OBSERVED']
assert len(observed)==1 and observed[0]['engine_stopped'] is True and observed[0]['observed_row_count']==0
code=r'''
import json,os,sys,hashlib,vertica_python
from app.run_queue import RunQueue
from app.repository import PostgresRepository
from app.specification_store import context
from app.hop_connection_runtime import connection_runtime
from app.private_log_store import read_private_log
data=json.loads(sys.argv[1]);q=RunQueue(os.environ['DATABASE_URL']);repo=PostgresRepository(os.environ['DATABASE_URL'])
with q.conn() as conn:
 run,_=context(q,conn,data['task_id'],data['run_id'])
 assert str(run['project_id'])==data['project_id'] and run['write_started']
 assert run['input_snapshot']['target_config']['table']==data['target']
snapshot=run['settings_snapshot']
with connection_runtime(repo,snapshot,snapshot['checksum']) as runtime:
 config={k:snapshot['connection'][k] for k in ('host','port','database','user','tlsmode')}
 config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
 try:
  with vertica_python.connect(**config) as db:
   cur=db.cursor();cur.execute('SELECT COUNT(*) FROM "ai_sample"."ui_accept_revision_20261011_v1"');count=cur.fetchone()[0]
   cur.execute('SELECT column_name FROM v_catalog.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',('ai_sample',data['target']))
   columns=[r[0] for r in cur.fetchall()]
 finally:config.clear()
assert count==0 and columns==['record_key','label_missing_fault']
log=read_private_log(q,data['task_id'],data['run_id'])
text=log.decode('utf-8',errors='replace') if isinstance(log,bytes) else log
raw=log if isinstance(log,bytes) else log.encode('utf-8')
missing_column='label' in text and ('does not exist' in text or 'COLUMN_NOT_FOUND' in text)
assert missing_column
print(json.dumps(dict(observed_row_count=count,columns=columns,missing_column_observed=True,log_bytes=len(raw),log_sha256=hashlib.sha256(raw).hexdigest())))
'''
result=subprocess.run(['wsl.exe','-d','RockyLinux9','-u','root','--','docker','exec','-i','ai-etl-stage-guidance-ui-api-1','python','-m','app.bootstrap','python','-c',code,json.dumps(state)],capture_output=True,text=True,encoding='utf-8')
if result.returncode:raise SystemExit('INDEPENDENT_FAILURE_READBACK_FAILED_NO_SECRET_OUTPUT')
proof=dict(task_id=state['task_id'],run_id=state['run_id'],target=state['target'],source_sha256=state['source_sha256'],write_started_count=1,engine_stopped=True,log_checksum=failed[0]['log_checksum'],independent_select=json.loads(result.stdout),status='PASS')
(root/'runtime-temp/v2-revision-failure-readback.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
