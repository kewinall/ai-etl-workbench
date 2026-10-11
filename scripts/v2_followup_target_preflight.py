"""SELECT-only fresh-target existence check; credentials stay inside API memory."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
state = json.loads((ROOT / 'runtime-temp/v2-followup-live-state.json').read_text(encoding='utf-8'))
assert set(state['cases']) == {'csv', 'excel', 'join'}
for key, case in state['cases'].items():
    assert case['target'] == 'ai_sample.ui_accept_' + key + '_20261011_v2'
code = r'''
import json,os,sys
import vertica_python
from app.run_queue import RunQueue
from app.repository import PostgresRepository
from app.specification_store import context
from app.hop_connection_runtime import connection_runtime
q=RunQueue(os.environ['DATABASE_URL']);repo=PostgresRepository(os.environ['DATABASE_URL']);out=[]
for key,c in json.loads(sys.argv[1]).items():
 with q.conn() as conn:run,naming=context(q,conn,c['task_id'],c['run_id'])
 assert not run['write_started']
 snapshot=run['settings_snapshot'];schema,table=c['target'].split('.')
 with connection_runtime(repo,snapshot,snapshot['checksum']) as runtime:
  config={k:snapshot['connection'][k] for k in ('host','port','database','user','tlsmode')}
  config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
  try:
   with vertica_python.connect(**config) as db:
    cur=db.cursor();cur.execute('SELECT COUNT(*) FROM v_catalog.tables WHERE table_schema=%s AND table_name=%s',(schema,table));count=cur.fetchone()[0]
    assert count==0,'NEW_TARGET_ALREADY_EXISTS'
  finally:config.clear()
 out.append(dict(key=key,task_id=c['task_id'],run_id=c['run_id'],target=c['target'],table_exists=False,write_started=False))
print(json.dumps(out))
'''
r = subprocess.run(['wsl.exe', '-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'exec', '-i',
                    'ai-etl-stage-guidance-ui-api-1', 'python', '-m', 'app.bootstrap', 'python', '-c',
                    code, json.dumps(state['cases'])], capture_output=True, text=True, encoding='utf-8')
if r.returncode:
    raise SystemExit('TARGET_PREFLIGHT_FAILED_NO_EXECUTION_NO_SECRET_OUTPUT')
proof = json.loads(r.stdout)
(ROOT / 'runtime-temp/v2-followup-target-preflight.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
print(json.dumps(proof))
