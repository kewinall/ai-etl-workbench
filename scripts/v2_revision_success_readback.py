"""Reuse SELECT-only receipt readers, binding them to the new corrected case."""
import ast,json,subprocess,sys
from pathlib import Path
from collections import Counter

root=Path(__file__).resolve().parents[1]
state=json.loads((root/'runtime-temp/v2-revision-live-state.json').read_text(encoding='utf-8-sig'))
assert state['project_id']=='346e9419-4b0e-4ba7-ad29-1756ca7da833'
assert state['target']=='ui_accept_revision_20261011_v2' and state['failure_closed']
phase=sys.argv[1]
assert phase in ('native','portable')
source=root/'scripts'/('v2_followup_native_readback.py' if phase=='native' else 'v2_followup_portability_readback.py')
key='embedded' if phase=='native' else 'code'
tree=ast.parse(source.read_text(encoding='utf-8-sig'))
code=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in node.targets))
cases={'revision':dict(task_id=state['task_id'],run_id=state['run_id'],target=state['target'])}
if phase=='native':
 args=['wsl.exe','-d','RockyLinux9','-u','root','--','docker','exec','-i','ai-etl-stage-guidance-ui-api-1','python','-m','app.bootstrap','python','-c',code,json.dumps(cases)]
else:
 args=['wsl.exe','-d','RockyLinux9','-u','root','--','env','UI_ACCEPT_PROJECT_ID='+state['project_id'],'docker','compose','-f','/mnt/d/ChatGPT/ai_agents_v2/deploy/compose.stage-guidance.yml','-f','/mnt/d/ChatGPT/ai_agents_v2/deploy/compose.ui-acceptance.yml','run','--rm','--no-deps','acceptance-replay','python','-c',code,json.dumps(cases)]
result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
if result.returncode:raise SystemExit('REVISION_READBACK_FAILED_NO_RETRY_NO_SECRET_OUTPUT')
items=json.loads(result.stdout);assert len(items)==1 and items[0]['run_id']==state['run_id']
proof=items[0]
if phase=='native':
 assert [c['name'] for c in proof['columns']]==['record_key','label']
 assert Counter(map(tuple,proof['rows']))==Counter([('A','alpha'),('B','beta')])
 assert len(proof['comparisons'])==1 and proof['comparisons'][0]['evidence']['status']=='MATCH'
 proof['independent_fixed_multiset_match']=True
else:
 assert proof['status']=='PASS' and proof['original_destination_separate'] and proof['workflow']['workflow_completed']
 assert proof['independent_isolated_read']['status']=='MATCH' and proof['independent_isolated_read']['actual_count']==2
proof['status']='PASS'
(root/('runtime-temp/v2-revision-'+phase+'-readback.json')).write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(phase=phase,run_id=state['run_id'],status='PASS')))
