"""GET-only API, credential-in-memory Vertica SELECT and persisted log readback."""
import json, subprocess, hashlib
from pathlib import Path
from collections import Counter
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
state=json.loads((ROOT/'runtime-temp/ui-accept-auto-state.json').read_text(encoding='utf-8'))
fixed=json.loads((ROOT/'examples/ui-acceptance/expected.json').read_text(encoding='utf-8'))
embedded=r'''
import json,os,sys
from decimal import Decimal
import vertica_python
from app.run_queue import RunQueue
from app.repository import PostgresRepository
from app.bound_comparison import capture_binding
from app.bound_result_query import execute_bound_result_query
from app.hop_connection_runtime import connection_runtime
from app.private_log_store import read_private_log
from app.hop_log_evidence import hop_log_evidence
from xml.etree import ElementTree as ET
from app.hpl_compiler import compile_hpl
from app.specification_store import context
cases=json.loads(sys.argv[1]);q=RunQueue(os.environ['DATABASE_URL']);repo=PostgresRepository(os.environ['DATABASE_URL']);out=[]
for key,c in cases.items():
 t,r=c['task_id'],c['run_id'];query,pin,snapshot,empty=capture_binding(q,repo,t,r)
 with connection_runtime(repo,snapshot,query['plan']['settings_checksum']) as runtime:
  config={k:snapshot['connection'][k] for k in ('host','port','database','user','tlsmode')}
  config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
  try:
   with vertica_python.connect(**config) as db:
    cur=db.cursor();execute_bound_result_query(cur,query,pin);rows=cur.fetchall()
  finally:config.clear()
 with q.conn() as conn:
  run,naming=context(q,conn,t,r)
  spec=conn.execute('SELECT spec_json FROM platform.specification WHERE run_id=%s AND content_checksum=%s',(r,query['plan']['specification_checksum'])).fetchone()['spec_json']
  compiled=compile_hpl(spec,{**run,'write_started':False},naming)
  events=conn.execute('SELECT event_type,event_context FROM platform.task_run_event WHERE run_id=%s ORDER BY event_id',(r,)).fetchall()
  comparisons=conn.execute('SELECT comparison_id,checksum,evidence FROM platform.task_run_result_comparison WHERE run_id=%s',(r,)).fetchall()
 log=read_private_log(q,t,r);names=[n.findtext('name') for n in ET.fromstring(compiled['hpl']).findall('transform')]
 metrics=hop_log_evidence({'started':True,'reason':'EXITED','exit_code':0,'output':log},names)
 assert metrics['complete_node_evidence'] and metrics['result']['status']=='COMPLETED'
 assert metrics['result']['log_checksum']==pin['hop_log_checksum']
 assert sum(e['event_type']=='WRITE_STARTED' for e in events)==1
 out.append(dict(key=key,task_id=t,run_id=r,target=c['target'],rows=rows,columns=query['plan']['columns'],sql_checksum=query['plan']['sql_checksum'],hop_log_bytes=len(log),hop=metrics,write_started_count=1,comparisons=comparisons))
print(json.dumps(out,default=lambda v:str(v) if isinstance(v,Decimal) else str(v),ensure_ascii=True))
'''
command=['wsl.exe','-d','RockyLinux9','-u','root','--','docker','exec','-i','ai-etl-stage-guidance-ui-api-1','python','-m','app.bootstrap','python','-c',embedded,json.dumps(state['cases'])]
r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
if r.returncode:
    # Driver output may contain secrets; never print it.
    raise SystemExit('READBACK_FAILED_REVIEW_LOCALLY_NO_RETRY')
records=json.loads(r.stdout)
for c in records:
    if c['key']=='join':expected=[(r['left_id'],r['left_value'],r['right_id'],r['right_value']) for r in fixed['join']['rows']]
    else:expected=[(r['category'],Decimal(r['sum_amount']),r['count_rows']) for r in fixed['csv_and_excel']['rows']]
    def norm(row):return tuple(Decimal(str(v)) if col['data_type'].startswith(('NUMERIC','DECIMAL')) and v is not None else v for v,col in zip(row,c['columns']))
    assert Counter(map(norm,c['rows']))==Counter(map(norm,expected)), 'FIXED_ANSWER_MISMATCH'
    assert len(c['comparisons'])==1 and c['comparisons'][0]['evidence']['status']=='MATCH','PLATFORM_MATCH_REQUIRED'
    c['independent_fixed_multiset_match']=True
proof={'scope':'Real three-case Vertica SELECT and immutable execution/log/comparison readback; no DDL, ETL replay or approval','expected_sha256':hashlib.sha256((ROOT/'examples/ui-acceptance/expected.json').read_bytes()).hexdigest(),'cases':records}
(ROOT/'docs/verification/ui-accept-auto-native-readback-2026-10-10.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps([{'key':c['key'],'actual_rows':len(c['rows']),'match':True,'nodes':len(c['hop']['nodes']),'write_count':1} for c in records]))

