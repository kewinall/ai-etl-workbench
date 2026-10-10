"""5197 scoped intent consumer. No approval creation, retries or global claims."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
from urllib.request import urlopen
from uuid import UUID, uuid4
from .worker_presence import PresenceReporter

ROOT=Path(__file__).resolve().parents[2]
BASE='http://127.0.0.1:5197/api'
CONTAINER='ai-etl-stage-guidance-ui-api-1'

def get(path):
    with urlopen(BASE+path,timeout=15) as reply:return json.load(reply)

def docker(args,**kwargs):
    return subprocess.run(['wsl.exe','-d','RockyLinux9','-u','root','--','docker',*args],
        capture_output=True,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW,**kwargs)

def presence(project,kind,instance,activity):
    result=docker(['exec','-i',CONTAINER,'python','-m','app.bootstrap','python','-m','app.acceptance_presence'],
        input=json.dumps(dict(project_id=project,kind=kind,instance_id=instance,mode='EXECUTE',activity=activity)),timeout=25)
    if result.returncode:raise ValueError('ACCEPTANCE_PRESENCE_UNAVAILABLE')

def pending(tasks):
    """Only existing authorized queue states. Never infer authority from offers."""
    for task in tasks:
        runs=get(f"/tasks/{task['id']}/runs")['runs']
        run=runs[0] if runs else None
        if not run:continue
        task_id,run_id=task['id'],str(UUID(run['run_id']))
        base=f'/tasks/{task_id}/runs/{run_id}'
        for endpoint,role,status in [('sa-invocation','local_sa_worker','SA_QUEUED'),
                                     ('developer','local_developer_worker','DEVELOPER_RESERVED'),
                                     ('qa-review','local_qa_worker','QA_RESERVED')]:
            record=get(base+'/'+endpoint).get('invocation') or {}
            if record.get('status')==status:
                yield role,record['invocation_id'],task_id,run_id,None
        job=get(base+'/hop-dispatch').get('request') or {}
        if job.get('status')=='QUEUED':yield 'hop',job['request_id'],task_id,run_id,None
        release=get(base+'/release')
        candidate=release.get('candidate')
        if candidate and release.get('status')=='PORTABILITY_REQUIRED' and not release.get('portability'):
            yield 'replay',candidate['candidate_id'],task_id,run_id,candidate['candidate_id']

def launch(role,task,run,candidate,project):
    env={**os.environ,'WORKBENCH_LOCAL_API_CONTAINER':CONTAINER,'WORKBENCH_LOCAL_WSL_DISTRO':'RockyLinux9'}
    if role not in ('hop','replay'):
        args=[sys.executable,'-m','app.'+role,'--task-id',task,'--run-id',run]
        if role=='local_qa_worker':args.append('--website-authorized')
        return subprocess.run(args,env=env,capture_output=True,text=True,encoding='utf-8',timeout=240,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    env_args=['env','UI_ACCEPT_PROJECT_ID='+project,'docker','compose',
              '-f','/mnt/d/ChatGPT/ai_agents_v2/deploy/compose.stage-guidance.yml',
              '-f','/mnt/d/ChatGPT/ai_agents_v2/deploy/compose.ui-acceptance.yml',
              'run','--rm','--no-deps','acceptance-hop' if role=='hop' else 'acceptance-replay',
              'python','-m','app.pilot_hop_worker' if role=='hop' else 'app.release_replay_worker',
              '--task-id',task,'--run-id',run]
    env_args+=['--once'] if role=='hop' else ['--candidate-id',candidate]
    return subprocess.run(['wsl.exe','-d','RockyLinux9','-u','root','--',*env_args],
                          capture_output=True,text=True,encoding='utf-8',timeout=1200,
                          creationflags=subprocess.CREATE_NO_WINDOW)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project-id',required=True)
    args=parser.parse_args();project=str(UUID(args.project_id))
    projects=get('/projects')
    if not any(p['project_id']==project and p.get('default_ai_profile')=='ui-accept-native' for p in projects):
        raise ValueError('ACCEPTANCE_PROJECT_REQUIRED')
    attempts=ROOT/'runtime-temp'/'ui-accept-attempts';attempts.mkdir(exist_ok=True)
    stop_file=ROOT/'runtime-temp'/'ui-accept-worker.stop'
    with ExitStack() as stack:
        for kind in ('SA_COPILOT','DEVELOPER_COPILOT','QA_COPILOT','HOP','PORTABILITY'):
            instance=str(uuid4())
            stack.enter_context(PresenceReporter(lambda activity,k=kind,i=instance:presence(project,k,i,activity)))
        pause=Event()
        while not stop_file.exists():
            try:
                tasks=get(f'/projects/{project}/tasks')
                if any(t['project_id']!=project or not (t.get('target_config') or {}).get('table','').startswith('ui_accept_') for t in tasks):
                    raise ValueError('ACCEPTANCE_SCOPE_CHANGED')
                for role,identity,task,run,candidate in pending(tasks):
                    marker=attempts/(role+'-'+str(UUID(identity))+'.json')
                    try:
                        with marker.open('x',encoding='utf-8') as f:json.dump(dict(role=role,task_id=task,run_id=run,status='ATTEMPT_RESERVED_NO_RETRY'),f)
                    except FileExistsError:continue
                    result=launch(role,task,run,candidate,project)
                    # Metadata only; stdout/stderr may contain source/driver details.
                    marker.write_text(json.dumps(dict(role=role,task_id=task,run_id=run,exit_code=result.returncode,
                                                      status='READ_SERVER_RESULT_NO_RETRY')),encoding='utf-8')
                    print(json.dumps(dict(role=role,task_id=task,run_id=run,exit_code=result.returncode)),flush=True)
            except Exception:
                print('ACCEPTANCE_READ_OR_LAUNCH_FAILED_NO_RETRY',flush=True)
            pause.wait(5)

if __name__=='__main__':main()
