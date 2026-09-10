import os,time,requests
from pathlib import Path
from dotenv import load_dotenv
from .task_uploads import cleanup_expired
ROOT=Path(__file__).resolve().parents[2];load_dotenv(ROOT/'.env')
API=os.getenv('WORKER_API','http://127.0.0.1:8765')
last_cleanup=0.0
def run_once():
 global last_cleanup
 try:
  if time.time()-last_cleanup>=3600:
   settings=requests.get(API+'/api/settings',timeout=5).json();cleanup_expired(int(settings.get('upload_policy',{}).get('retention_days',7)));last_cleanup=time.time()
  tasks=requests.get(API+'/api/tasks',timeout=5).json()
  for task in tasks:
   if task['status']=='CREATED': requests.post(f"{API}/api/tasks/{task['id']}/run",timeout=240)
 except Exception as e: print('worker:',e,flush=True)
if __name__=='__main__':
 while True:run_once();time.sleep(3)
