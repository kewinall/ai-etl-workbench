"""Inspect completed isolated replay receipts/logs and SELECT its outputs only."""
import json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
state=json.loads((ROOT/'runtime-temp/v2-followup-live-state.json').read_text(encoding='utf-8'))
code=r'''
import json,os,sys
from pathlib import Path
from hashlib import sha256
from xml.etree import ElementTree as ET
import vertica_python
from app.run_queue import RunQueue
from app.repository import PostgresRepository
from app.release_replay_worker import destination,replay_context
from app.release_store import storage_root
from app.bound_result_query import load_bound_result_query,execute_bound_result_query
from app.workflow_log_evidence import workflow_log_evidence
from app.result_reader import read_result_rows
from app.expected_result import ResultColumn
from app.result_oracle import compare_oracle_document
from app.release_bundle import MEMBERS
from app.sa_contract import digest
q=RunQueue(os.environ['DATABASE_URL']);repo=PostgresRepository(os.environ['DATABASE_URL']);root=storage_root(None)
target,secret=destination();config={k:target[k] for k in ('host','port','database','user','tlsmode')};config.update(password=secret,connection_timeout=10)
out=[]
try:
 for key,c in json.loads(sys.argv[1]).items():
  t,r=c['task_id'],c['run_id'];query,oracle=load_bound_result_query(q,t,r)
  with q.conn() as conn:
   candidate=conn.execute('SELECT candidate_id FROM platform.release_candidate_record WHERE run_id=%s',(r,)).fetchone()
   candidate,parts,run,spec=replay_context(q,repo,conn,t,r,candidate['candidate_id'],root)
   receipt=conn.execute('SELECT * FROM platform.release_portability_check WHERE candidate_id=%s',(candidate['candidate_id'],)).fetchone()
  assert receipt['status']=='PASS' and digest(receipt['evidence'])==receipt['checksum']
  original=run['settings_snapshot']['connection'];assert not all(str(target[k]).lower()==str(original[k]).lower() for k in ('host','port','database'))
  log=(Path(root)/'portability-private'/r/(str(receipt['check_id'])+'.log')).read_bytes()
  assert sha256(log).hexdigest()==receipt['evidence']['hop_log_checksum']
  nodes=[n.findtext('name') for n in ET.fromstring(parts[MEMBERS['HPL']]).findall('transform')]
  wf=ET.fromstring(parts[MEMBERS['HWF']]).findtext('name')
  metrics=workflow_log_evidence({'started':True,'reason':'EXITED','exit_code':receipt['evidence']['exit_code'],'output':log},nodes,wf)
  assert metrics['workflow_completed'] and metrics['complete_node_evidence'] and metrics['result']['status']=='COMPLETED'
  document=json.loads(oracle['content'])
  with vertica_python.connect(**config) as db:
   cur=db.cursor();execute_bound_result_query(cur,query,oracle);rows=read_result_rows(cur,[ResultColumn(**col) for col in document['columns']])
  compare=compare_oracle_document(oracle['content'],rows,document_checksum=oracle['document_checksum'],specification_checksum=digest(spec),naming_checksum=spec['naming']['checksum'])
  assert compare['status']=='MATCH' and compare['actual_checksum']==receipt['evidence']['result_actual_checksum']
  out.append(dict(key=key,run_id=r,check_id=str(receipt['check_id']),status='PASS',checksum=receipt['checksum'],evidence=receipt['evidence'],log_bytes=len(log),workflow=metrics,independent_isolated_read=compare,original_destination_separate=True))
finally:config.clear();secret=None
print(json.dumps(out,default=str))
'''
args=['wsl.exe','-d','RockyLinux9','-u','root','--','env','UI_ACCEPT_PROJECT_ID='+state['project_id'],'docker','compose','-f','/mnt/d/ChatGPT/ai_agents_v2/deploy/compose.stage-guidance.yml','-f','/mnt/d/ChatGPT/ai_agents_v2/deploy/compose.ui-acceptance.yml','run','--rm','--no-deps','acceptance-replay','python','-c',code,json.dumps(state['cases'])]
r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
if r.returncode:raise SystemExit('PORTABILITY_READBACK_FAILED_NO_REPLAY')
items=json.loads(r.stdout)
(ROOT/'docs/verification/v2-followup-portability-2026-10-11.json').write_text(json.dumps({'scope':'Completed receipts, immutable candidate bytes, private HWF logs and independent isolated DB SELECT only; no Hop/DDL rerun','cases':items},indent=2)+'\n',encoding='utf-8')
print(json.dumps([{'case':i['key'],'workflow_completed':i['workflow']['workflow_completed'],'actual':i['independent_isolated_read']['actual_count'],'match':i['independent_isolated_read']['status']} for i in items]))
