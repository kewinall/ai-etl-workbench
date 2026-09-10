from __future__ import annotations
import csv, json, os, re, shutil, subprocess, time, uuid, zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Any
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from .repository import PostgresRepository
from .execution import build_hpl,execute_hop,persist_artifact,persist_validation,semantic_validate,static_validate
from .etl_analyzer import AnalyzerError, analyze_file, discover_files, resolve_source
from .requirement_engine import canonicalize, copilot_prompt, plan, requirement_gate
from .source_profiler import profile_task
from .sample_data import ensure_query_target, ensure_sample_target, materialize_samples, materialize_stage_server_sample, rebuild_managed_sample
from .task_uploads import cleanup_expired, save_and_profile
from .platform_harness import checksum, encrypt_secret, litellm_complete, naming_suggestions, requirement_issues
from .release import create_release, create_sdm, sha as artifact_sha

ROOT=Path(__file__).resolve().parents[2];load_dotenv(ROOT/'.env');DB=os.environ['DATABASE_URL'];repo=PostgresRepository(DB)
app=FastAPI(title='AI Hop Workflow Platform',version='0.2.0');app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5173','http://localhost:5173'],allow_methods=['*'],allow_headers=['*'])
class TaskCreate(BaseModel):
 project_id:str|None=None
 name:str=Field(min_length=2,max_length=120);requirement:str=Field(min_length=5);operation:str='NEW';category:str='STAGE';source_type:str='CSV';source_config:dict[str,Any]=Field(default_factory=dict);target_type:str='VERTICA';target_schema:str='etl_output';target_table:str='validation_output';target_config:dict[str,Any]=Field(default_factory=dict);model:str='copilot';error_test_config:dict[str,Any]=Field(default_factory=dict)
class TaskUpdate(TaskCreate):pass
class RequirementSupplement(BaseModel):
 values:dict[str,Any]=Field(default_factory=dict)
 note:str=''
class ProjectPayload(BaseModel):
 project_name:str=Field(min_length=2,max_length=120);description:str='';default_ai_profile:str='nova-default';default_connection:str='vertica-default';naming_rules:dict[str,Any]=Field(default_factory=dict)
class NamingContractInput(BaseModel):
 columns:list[dict[str,Any]]=Field(default_factory=list)
class SecretInput(BaseModel):
 secret_value:str=Field(min_length=1,max_length=10000)
class AnalyzeRequest(BaseModel):
 path:str=Field(min_length=1,max_length=1000)
class AnalyzeBatchRequest(BaseModel):
 paths:list[str]=Field(min_length=1)
 ai_provider:str|None=None
 task_name:str|None=None

def analyzer_root():
 configured=os.getenv('ANALYZER_SCAN_ROOT','').strip()
 return Path(configured).resolve() if configured else (ROOT/'scan').resolve()

def analyzer_ai_summary(model:dict,provider:str):
 if provider not in ('codex_cli','copilot'):raise AnalyzerError('AI Provider 只支援 codex_cli 或 copilot')
 compact={'process':model['process'],'sources':model['sources'],'targets':model['targets'],'dependencies':model['dependencies'],'parameters':model['parameters'],'variables':model['variables'],'warnings':model['warnings'],'logic':[{'node':x['node'],'type':x['type'],'category':x['category'],'detail':{k:v for k,v in x.get('detail',{}).items() if k in ('table','file','condition','sql_tables')}} for x in model['logic'][:40]],'column_lineage':[{**x,'expression':str(x.get('expression',''))[:180]} for x in model['column_lineage'][:50]]}
 prompt='''你是企業 ETL 架構分析師。根據 Canonical ETL Model 產生繁體中文商業邏輯摘要。只回傳 JSON，欄位必須為 purpose、business_flow（字串陣列）、data_inputs、data_outputs、business_rules、risks、assumptions。禁止臆測；無法由 metadata 證明的內容放 assumptions。\nMODEL='''+json.dumps(compact,ensure_ascii=False,default=str)[:5500]
 started=time.monotonic()
 if provider=='codex_cli':
  command,env=codex_command('exec','--json','--skip-git-repo-check','--sandbox','read-only','--ephemeral','-');run=subprocess.run(command,cwd=ROOT,input=prompt.encode('utf-8'),capture_output=True,text=False,timeout=180,env=env)
  stdout=decode_cli_output(run.stdout);stderr=decode_cli_output(run.stderr)
  events=[]
  for line in stdout.splitlines():
   try:events.append(json.loads(line))
   except json.JSONDecodeError:pass
  messages=[e.get('item',{}).get('text') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
  raw=messages[-1] if messages else stdout
  usage_events=[e.get('usage',{}) for e in events if e.get('type')=='turn.completed'];usage=usage_events[-1] if usage_events else {}
  model_name=os.getenv('CODEX_MODEL') or 'Codex CLI default'
 else:
  command,env=copilot_command('--no-custom-instructions','--no-remote','--no-remote-export','--allow-all-tools','--no-ask-user','--output-format','json','-p',' '.join(prompt.splitlines()));run=subprocess.run(command,cwd=ROOT,capture_output=True,text=False,timeout=180,env=env);stdout=decode_cli_output(run.stdout);stderr=decode_cli_output(run.stderr)
  events=[]
  for line in stdout.splitlines():
   try:events.append(json.loads(line))
   except json.JSONDecodeError:pass
  messages=[e.get('data',{}) for e in events if e.get('type')=='assistant.message' and e.get('data',{}).get('content')]
  results=[e for e in events if e.get('type')=='result'];checkpoints=[e.get('data',{}) for e in events if e.get('type')=='session.usage_checkpoint' and e.get('data')];result_usage=(results[-1].get('usage') or {}) if results else {};nano_aiu=checkpoints[-1].get('totalNanoAiu') if checkpoints else None
  raw=messages[-1]['content'] if messages else stdout;model_name=messages[-1].get('model') if messages else 'Copilot CLI';usage={'input_tokens':None,'cached_input_tokens':None,'output_tokens':messages[-1].get('outputTokens') if messages else None,'total_tokens':None,'premium_requests':result_usage.get('premiumRequests'),'nano_aiu':nano_aiu,'ai_credits':nano_aiu/1_000_000_000 if nano_aiu is not None else None,'usage_type':'PARTIAL','usage_source':'copilot_json_events'}
 if run.returncode!=0:raise AnalyzerError(f'AI 摘要產生失敗：{(stderr or stdout)[-1000:]}')
 raw=raw.strip();raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip() if raw.startswith('```') else raw
 if not raw.startswith('{'):
  start,end=raw.find('{'),raw.rfind('}')
  if start>=0 and end>start:raw=raw[start:end+1]
 try:summary=json.loads(raw)
 except json.JSONDecodeError as e:raise AnalyzerError(f'AI 摘要不是有效 JSON：{e}')
 if provider=='codex_cli':usage={**usage,'usage_type':'EXACT' if usage.get('total_tokens') is not None else 'UNAVAILABLE','usage_source':'codex_json_events'}
 return {'summary':summary,'provider':provider,'model':model_name,'usage':{**usage,'duration_ms':round((time.monotonic()-started)*1000)}}

def decode_cli_output(value:bytes)->str:
 for encoding in ('utf-8','cp950','mbcs'):
  try:return value.decode(encoding)
  except (UnicodeDecodeError,LookupError):pass
 return value.decode('utf-8',errors='replace')

def run_analyzer_batch(batch_id:uuid.UUID,root:Path,paths:list[str],provider:str|None,cleanup_root:Path|None=None):
 succeeded=failed=0
 try:
  for relative in paths:
   repo.update_etl_batch_item(batch_id,relative,'RUNNING')
   try:
    path=resolve_source(root,relative);model=analyze_file(path,root);ai=analyzer_ai_summary(model,provider) if provider else None
    analysis_id=repo.save_etl_analysis(model,batch_id,ai);repo.update_etl_batch_item(batch_id,relative,'SUCCEEDED',analysis_id);succeeded+=1
   except Exception as e:
    code='AI_SUMMARY_FAILED' if 'AI' in str(e) or 'model' in str(e).lower() else 'ETL_ANALYSIS_FAILED';repo.update_etl_batch_item(batch_id,relative,'FAILED',error_code=code,error_message=str(e));failed+=1
   repo.update_etl_batch_progress(batch_id,succeeded,failed)
  repo.complete_etl_batch(batch_id,succeeded,failed)
 finally:
  if cleanup_root and cleanup_root.is_dir():shutil.rmtree(cleanup_root,ignore_errors=True)

def safe_upload_name(name:str)->str:
 value=Path(name.replace('\\','/')).name
 if not value or value in ('.','..'):raise AnalyzerError('上傳檔案名稱無效')
 return value

def extract_uploaded_etl(upload_path:Path,target:Path)->list[str]:
 allowed={'.ktr','.kjb','.hpl','.hwf'};paths=[]
 if upload_path.suffix.lower()!='.zip':
  if upload_path.suffix.lower() not in allowed:raise AnalyzerError('只接受 ZIP、KTR、KJB、HPL 或 HWF')
  destination=target/upload_path.name;shutil.move(str(upload_path),destination);return [destination.name]
 with zipfile.ZipFile(upload_path) as archive:
  for info in archive.infolist():
   if info.is_dir() or Path(info.filename).suffix.lower() not in allowed:continue
   relative=Path(info.filename.replace('\\','/'))
   if relative.is_absolute() or '..' in relative.parts:raise AnalyzerError('ZIP 包含不安全的路徑')
   destination=(target/relative).resolve()
   if target.resolve() not in destination.parents:raise AnalyzerError('ZIP 解壓路徑超出暫存目錄')
   destination.parent.mkdir(parents=True,exist_ok=True)
   with archive.open(info) as source,destination.open('wb') as output:shutil.copyfileobj(source,output)
   paths.append(relative.as_posix())
 if not paths:raise AnalyzerError('ZIP 中沒有可分析的 ETL 檔案')
 return paths

def cli_probe(provider):
 if provider=='codex_cli':
  configured=os.getenv('CODEX_CLI_PATH','').strip();exe=configured or shutil.which('codex')
  if not exe:return {'id':provider,'status':'NOT_INSTALLED','installed':False,'detail':'codex is not configured or on PATH'}
  cmd=[exe,'--version']
  if os.name=='nt' and Path(exe).suffix.lower() in ('.cmd','.bat'):
   cmd=[os.environ.get('COMSPEC',r'C:\Windows\System32\cmd.exe'),'/d','/c',exe,'--version']
 else:
  configured=os.getenv('COPILOT_CLI_PATH','').strip();exe=configured or shutil.which('copilot')
  if not exe:return {'id':provider,'status':'NOT_INSTALLED','installed':False,'detail':'copilot is not configured or on PATH'}
  cmd=[exe,'version']
  if os.name=='nt' and Path(exe).suffix.lower() in ('.cmd','.bat'):
   cmd=[os.environ.get('COMSPEC',r'C:\Windows\System32\cmd.exe'),'/d','/c',exe,'version']
 run_env=os.environ.copy();node_dir=os.getenv('CODEX_NODE_DIR','').strip()
 if node_dir:run_env['PATH']=node_dir+os.pathsep+run_env.get('PATH','')
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=10,env=run_env);return {'id':provider,'status':'AVAILABLE' if p.returncode==0 else 'ATTENTION','installed':True,'detail':(p.stdout or p.stderr).strip()[:800]}
 except Exception as e:return {'id':provider,'status':'ERROR','installed':True,'detail':str(e)}

def codex_command(*args:str):
 exe=os.getenv('CODEX_CLI_PATH','').strip() or shutil.which('codex') or 'codex'
 command=[exe,*args]
 if os.name=='nt' and Path(exe).suffix.lower() in ('.cmd','.bat'):
  command=[os.environ.get('COMSPEC',r'C:\Windows\System32\cmd.exe'),'/d','/c',exe,*args]
 env=os.environ.copy();node_dir=os.getenv('CODEX_NODE_DIR','').strip()
 if node_dir:env['PATH']=node_dir+os.pathsep+env.get('PATH','')
 return command,env

def copilot_command(*args:str):
 exe=os.getenv('COPILOT_CLI_PATH','').strip() or shutil.which('copilot') or 'copilot'
 command=[exe,*args]
 if os.name=='nt' and Path(exe).suffix.lower() in ('.cmd','.bat'):
  # npm's .cmd shim forwards %* through cmd.exe. SQL operators, parentheses and
  # percent signs inside prompts are then interpreted as shell syntax. Invoke
  # the Copilot JavaScript entry point with node.exe so every prompt stays one
  # literal argv value and never passes through cmd.exe.
  loader=Path(exe).parent/'node_modules'/'@github'/'copilot'/'npm-loader.js'
  node_dir=os.getenv('CODEX_NODE_DIR','').strip();node=(Path(node_dir)/'node.exe') if node_dir else None
  node_exe=str(node) if node and node.is_file() else (shutil.which('node') or '')
  command=[node_exe,str(loader),*args] if node_exe and loader.is_file() else [os.environ.get('COMSPEC',r'C:\Windows\System32\cmd.exe'),'/d','/s','/c',exe,*args]
 env=os.environ.copy();node_dir=os.getenv('CODEX_NODE_DIR','').strip()
 if node_dir:env['PATH']=node_dir+os.pathsep+env.get('PATH','')
 return command,env

def validate_read_only_query(value:str):
 query=value.strip().rstrip(';').strip()
 if not re.match(r'(?is)^(select|with)\b',query):raise ValueError('Join/query logic must begin with SELECT or WITH')
 if ';' in query or re.search(r'(?is)\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|call|do)\b',query):raise ValueError('Only one read-only SELECT query is allowed')
 return query

def validate_query_sources(query:str,sources:list[dict]):
 allowed={f"{s['schema'].lower()}.{(s.get('object') or s.get('table')).lower()}" for s in sources}
 referenced={f"{m.group(1).lower()}.{m.group(2).lower()}" for m in re.finditer(r'(?is)\b(?:from|join)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\."?([A-Za-z_][A-Za-z0-9_]*)"?',query)}
 unexpected=referenced-allowed
 if unexpected:raise ValueError(f"SQL references sources outside the Task: {', '.join(sorted(unexpected))}")
 if len(sources)>1 and not allowed.issubset(referenced):raise ValueError('Generated SQL must reference every configured source table')
 return query

def validate_vertica_query(query:str,sources:list[dict]):
 query=validate_query_sources(validate_read_only_query(query),sources)
 import vertica_python
 cfg={'host':os.getenv('VERTICA_HOST','127.0.0.1'),'port':int(os.getenv('VERTICA_PORT','5433')),'user':os.getenv('VERTICA_USER','dbadmin'),'password':os.getenv('VERTICA_PASSWORD',''),'database':os.getenv('VERTICA_DATABASE','VMart'),'tlsmode':os.getenv('VERTICA_TLSMODE','disable')}
 with vertica_python.connect(**cfg) as conn:
  cur=conn.cursor();cur.execute('EXPLAIN '+query);explain='\n'.join(str(row[0]) for row in cur.fetchall())
  cur.execute(f'SELECT * FROM ({query}) generated_preview LIMIT 10');rows=cur.fetchall();columns=[x[0] for x in cur.description]
 return query,columns,[dict(zip(columns,row)) for row in rows],explain[:12000]

def sa_prompt(task:dict,sample:list[dict],columns:list[str]):
 if task.get('model')=='copilot' or task.get('source') in ('EXCEL','VERTICA','MIXED'):
  return copilot_prompt(task,{'sources':task.get('source_config',{}).get('sources') or [],'columns':columns,'masked_sample':sample[:3]})
 multi=task['source']=='POSTGRESQL_TABLE' and len(task.get('source_config',{}).get('sources') or [])>1
 sql_instruction=f"Generate sql_query as one PostgreSQL read-only SELECT using only the configured sources. Natural-language Join/calculation request: {task['source_config'].get('logic_description','')}" if multi else 'Set sql_query to null.'
 return f'''You are the Requirement and Solution Architecture agent for an Apache Hop POC.
Return only one valid JSON object, without markdown fences. Do not edit files or run commands.
Task name: {task['name']}
Requirement: {task['requirement']}
Source type: {task['source']}
Configured PostgreSQL sources: {json.dumps(task.get('source_config',{}).get('sources') or [],ensure_ascii=False,default=str)}
Source columns: {json.dumps(columns,ensure_ascii=False,default=str)}
Sample rows: {json.dumps(sample,ensure_ascii=False,default=str)}
Target: {json.dumps(task['target_config'],ensure_ascii=False)}
Validation policy: FIRST_10_VALID_ROWS, maximum 10 writes, followed by post-write count.
{sql_instruction}
JSON keys required: summary, source_fields, target_fields, transformations, validations, write_policy, acceptance_criteria, warnings, sql_query.'''

def run_codex_sa(task:dict,sample:list[dict],columns:list[str]):
 prompt=sa_prompt(task,sample,columns)
 command,env=codex_command('exec','--json','--skip-git-repo-check','--sandbox','read-only','--ephemeral','-')
 started=time.monotonic()
 result=subprocess.run(command,cwd=ROOT,input=prompt,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,env=env)
 elapsed=round((time.monotonic()-started)*1000)
 stdout=result.stdout.strip();stderr=result.stderr.strip()
 if result.returncode!=0:raise RuntimeError(json.dumps({'return_code':result.returncode,'stdout':stdout[-4000:],'stderr':stderr[-4000:]},ensure_ascii=False))
 events=[]
 for line in stdout.splitlines():
  try:events.append(json.loads(line))
  except json.JSONDecodeError:pass
 messages=[e.get('item',{}).get('text') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message' and e.get('item',{}).get('text')]
 usage_events=[e.get('usage',{}) for e in events if e.get('type')=='turn.completed' and e.get('usage')]
 usage=usage_events[-1] if usage_events else {}
 raw=messages[-1] if messages else stdout
 if raw.startswith('```'):
  raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
 try: specification=json.loads(raw)
 except json.JSONDecodeError as e:raise RuntimeError(json.dumps({'code':'MODEL_OUTPUT_INVALID_JSON','error':str(e),'stdout':stdout[-6000:],'stderr':stderr[-2000:]},ensure_ascii=False))
 model_match=re.search(r'(?m)^model:\s*(\S+)',stderr);token_match=re.search(r'tokens used\s*\r?\n\s*([\d,]+)',stderr,re.IGNORECASE)
 configured_model=os.getenv('CODEX_MODEL','').strip()
 if not configured_model:
  try:
   config_text=(Path.home()/'.codex'/'config.toml').read_text(encoding='utf-8')
   config_match=re.search(r'(?m)^model\s*=\s*["\']([^"\']+)["\']',config_text)
   configured_model=config_match.group(1) if config_match else ''
  except OSError:pass
 input_tokens=usage.get('input_tokens');cached_tokens=usage.get('cached_input_tokens');output_tokens=usage.get('output_tokens');total_tokens=usage.get('total_tokens')
 if total_tokens is None and input_tokens is not None:total_tokens=int(input_tokens or 0)+int(output_tokens or 0)
 if total_tokens is None and token_match:total_tokens=int(token_match.group(1).replace(',',''))
 return specification,{'provider':'codex_cli','model':model_match.group(1) if model_match else (configured_model or 'Codex CLI default'),'duration_ms':elapsed,'input_tokens':input_tokens,'cached_input_tokens':cached_tokens,'output_tokens':output_tokens,'total_tokens':total_tokens,'usage_type':'EXACT' if total_tokens is not None else 'UNAVAILABLE','usage_source':'codex_json_events' if usage else 'codex_cli_stderr','stdout':raw[-6000:],'stderr':stderr[-6000:]}

def run_copilot_sa(task:dict,sample:list[dict],columns:list[str]):
 prompt=' '.join(sa_prompt(task,sample,columns).splitlines())
 command,env=copilot_command('--no-custom-instructions','--no-remote','--no-remote-export','--allow-all-tools','--no-ask-user','--output-format','json','-p',prompt)
 started=time.monotonic();result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,env=env)
 elapsed=round((time.monotonic()-started)*1000);stdout=result.stdout.strip();stderr=result.stderr.strip()
 if result.returncode!=0:raise RuntimeError(json.dumps({'return_code':result.returncode,'stdout':stdout[-4000:],'stderr':stderr[-4000:]},ensure_ascii=False))
 events=[]
 for line in stdout.splitlines():
  try:events.append(json.loads(line))
  except json.JSONDecodeError:pass
 messages=[e.get('data',{}) for e in events if e.get('type')=='assistant.message' and e.get('data',{}).get('content')]
 results=[e for e in events if e.get('type')=='result']
 if not messages:raise RuntimeError(json.dumps({'code':'MODEL_OUTPUT_MISSING','stdout':stdout[-6000:]},ensure_ascii=False))
 message=messages[-1];raw=message['content'].strip()
 if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
 try:specification=json.loads(raw)
 except json.JSONDecodeError as e:raise RuntimeError(json.dumps({'code':'MODEL_OUTPUT_INVALID_JSON','error':str(e),'output':raw[-6000:]},ensure_ascii=False))
 usage=(results[-1].get('usage') or {}) if results else {};output_tokens=message.get('outputTokens')
 checkpoints=[e.get('data',{}) for e in events if e.get('type')=='session.usage_checkpoint' and e.get('data')]
 nano_aiu=checkpoints[-1].get('totalNanoAiu') if checkpoints else None
 ai_credits=(nano_aiu/1_000_000_000) if nano_aiu is not None else None
 return specification,{'provider':'copilot','model':message.get('model'),'duration_ms':elapsed,'input_tokens':None,'cached_input_tokens':None,'output_tokens':output_tokens,'total_tokens':None,'usage_type':'PARTIAL','usage_source':'copilot_json_events','premium_requests':usage.get('premiumRequests'),'nano_aiu':nano_aiu,'ai_credits':ai_credits,'api_duration_ms':usage.get('totalApiDurationMs'),'session_duration_ms':usage.get('sessionDurationMs'),'stdout':raw[-6000:],'stderr':stderr[-6000:]}

@app.get('/api/health')
def health():
 try: ms=repo.migration_status();return {'status':'ok','mode':'postgres','database':'configured','migration':ms,'time':datetime.now(timezone.utc).isoformat()}
 except Exception as e: raise HTTPException(503,str(e))
@app.get('/api/dashboard')
def dashboard():return repo.dashboard()
@app.get('/api/analyzer/files')
def analyzer_files():
 root=analyzer_root();files=discover_files(root)
 counts={ext:sum(1 for item in files if item['extension']==ext) for ext in ('.ktr','.kjb','.hpl','.hwf')}
 return {'root':str(root),'files':files,'counts':counts,'total':len(files),'storage_note':'來源檔只讀取，不複製；遮蔽敏感值後的 XML 與解析結果存入 PostgreSQL。'}
@app.get('/api/analyzer/analyses')
def analyzer_analyses():return repo.list_etl_analyses()
@app.get('/api/analyzer/analyses/{analysis_id}')
def analyzer_analysis(analysis_id:str):
 try:d=repo.get_etl_analysis(analysis_id)
 except Exception:raise HTTPException(400,'Invalid analysis id')
 if not d:raise HTTPException(404,'ETL analysis not found')
 return d
@app.get('/api/analyzer/batches')
def analyzer_batches():return repo.list_etl_batches()
@app.post('/api/analyzer/analyze-batch-async',status_code=202)
def analyzer_analyze_batch_async(data:AnalyzeBatchRequest,background_tasks:BackgroundTasks):
 root=analyzer_root();paths=list(dict.fromkeys(data.paths));batch_id=uuid.uuid4()
 for relative in paths:resolve_source(root,relative)
 repo.create_etl_batch(batch_id,len(paths),data.ai_provider,data.task_name,'SCAN');repo.queue_etl_batch_items(batch_id,paths)
 background_tasks.add_task(run_analyzer_batch,batch_id,root,paths,data.ai_provider)
 return repo.get_etl_batch(batch_id)
@app.post('/api/analyzer/upload',status_code=202)
async def analyzer_upload(background_tasks:BackgroundTasks,files:list[UploadFile]=File(...),task_name:str=Form(''),ai_provider:str=Form('')):
 provider=ai_provider or None
 if provider not in (None,'codex_cli','copilot'):raise HTTPException(422,'不支援的 AI Provider')
 batch_id=uuid.uuid4();work_root=ROOT/'runtime-temp'/'etl-upload'/str(batch_id);incoming=work_root/'incoming';extracted=work_root/'files';incoming.mkdir(parents=True,exist_ok=True);extracted.mkdir(parents=True,exist_ok=True);paths=[]
 try:
  for upload in files:
   name=safe_upload_name(upload.filename or '');temporary=incoming/name
   with temporary.open('wb') as output:
    while chunk:=await upload.read(1024*1024):output.write(chunk)
   paths.extend(extract_uploaded_etl(temporary,extracted))
  paths=list(dict.fromkeys(paths))
  repo.create_etl_batch(batch_id,len(paths),provider,task_name.strip() or None,'UPLOAD');repo.queue_etl_batch_items(batch_id,paths)
  background_tasks.add_task(run_analyzer_batch,batch_id,extracted,paths,provider,work_root)
  return repo.get_etl_batch(batch_id)
 except Exception as e:
  shutil.rmtree(work_root,ignore_errors=True)
  raise HTTPException(422,str(e))
@app.get('/api/analyzer/batches/{batch_id}')
def analyzer_batch(batch_id:str):
 try:d=repo.get_etl_batch(batch_id)
 except Exception:raise HTTPException(400,'Invalid batch id')
 if not d:raise HTTPException(404,'Batch not found')
 return d
@app.post('/api/analyzer/analyze',status_code=201)
def analyzer_analyze(data:AnalyzeRequest):
 root=analyzer_root()
 try:
  path=resolve_source(root,data.path);model=analyze_file(path,root);analysis_id=repo.save_etl_analysis(model)
 except AnalyzerError as e:raise HTTPException(422,str(e))
 except Exception as e:raise HTTPException(500,f'ETL 分析失敗：{e}')
 return repo.get_etl_analysis(analysis_id)
@app.post('/api/analyzer/analyze-batch',status_code=201)
def analyzer_analyze_batch(data:AnalyzeBatchRequest):
 root=analyzer_root();batch_id=uuid.uuid4();results=[];repo.create_etl_batch(batch_id,len(dict.fromkeys(data.paths)),data.ai_provider)
 for relative in dict.fromkeys(data.paths):
  try:
   path=resolve_source(root,relative);model=analyze_file(path,root);ai=analyzer_ai_summary(model,data.ai_provider) if data.ai_provider else None
   analysis_id=repo.save_etl_analysis(model,batch_id,ai);repo.add_etl_batch_item(batch_id,relative,'SUCCEEDED',analysis_id);results.append({'path':relative,'status':'SUCCEEDED','analysis':repo.get_etl_analysis(analysis_id)})
  except Exception as e:
   code='AI_SUMMARY_FAILED' if 'AI' in str(e) or 'model' in str(e).lower() else 'ETL_ANALYSIS_FAILED';repo.add_etl_batch_item(batch_id,relative,'FAILED',error_code=code,error_message=str(e));results.append({'path':relative,'status':'FAILED','error_code':code,'error':str(e)})
 succeeded=sum(x['status']=='SUCCEEDED' for x in results);failed=len(results)-succeeded;repo.complete_etl_batch(batch_id,succeeded,failed)
 return {'batch_id':str(batch_id),'total':len(results),'succeeded':succeeded,'failed':failed,'results':results}
@app.get('/api/projects')
def projects():return repo.list_projects()
@app.post('/api/projects',status_code=201)
def create_project(data:ProjectPayload):
 try:return repo.create_project(data.model_dump())
 except Exception as exc:raise HTTPException(422,str(exc)) from exc
@app.put('/api/projects/{project_id}')
def update_project(project_id:str,data:ProjectPayload):
 if not repo.get_project(project_id):raise HTTPException(404,'Project not found')
 try:return repo.update_project(project_id,data.model_dump())
 except Exception as exc:raise HTTPException(422,str(exc)) from exc
@app.post('/api/projects/{project_id}/tasks',status_code=201)
def create_project_task(project_id:str,data:TaskCreate):
 if not repo.get_project(project_id):raise HTTPException(404,'Project not found')
 return create(TaskCreate(**{**data.model_dump(),'project_id':project_id}))

@app.get('/api/tasks')
def tasks():return repo.list_tasks()
@app.post('/api/tasks',status_code=201)
def create(data:TaskCreate):
 payload=data.model_dump()
 if payload.get('project_id') and not repo.get_project(payload['project_id']):raise HTTPException(422,'Project not found')
 category=payload['category'];sources=(payload.get('source_config') or {}).get('sources') or []
 if category not in ('STAGE','ODS','DW_DM'):raise HTTPException(422,'不支援的正常建立類型')
 if payload['operation']=='ERROR_TEST' and not (repo.setting('feature_flags',{}) or {}).get('test_mode_enabled',False):raise HTTPException(403,'系統測試模式尚未開啟')
 if payload['operation']=='NEW':
  if category=='STAGE' and (len(sources)!=1 or sources[0].get('type') not in ('CSV','EXCEL','JSON')):raise HTTPException(422,'Stage 必須使用一個 CSV、Excel 或 JSON 來源')
  stage_mode=str((payload.get('target_config') or {}).get('stage_mode','NORMAL')).upper()
  if category=='STAGE' and stage_mode not in ('NORMAL','EXTERNAL','FLEX'):raise HTTPException(422,'Stage 匯入模式只支援 NORMAL、EXTERNAL、FLEX')
  if category=='STAGE' and stage_mode in ('EXTERNAL','FLEX'):
   for key in ('data_path','reject_path','exception_path'):
    if not str((payload.get('target_config') or {}).get(key,'')).startswith('/'):raise HTTPException(422,f'{key} 必須使用 Vertica Server 絕對路徑')
  if category=='ODS' and (len(sources)!=1 or sources[0].get('type') not in ('CSV','EXCEL','VERTICA')):raise HTTPException(422,'ODS 必須使用一個檔案或 Vertica Table 來源')
  if category=='DW_DM' and (len(sources)<2 or any(x.get('type')!='VERTICA' for x in sources)):raise HTTPException(422,'DW/DM 必須使用至少兩個 Vertica Table 來源')
 return repo.create_task(payload)
@app.post('/api/tasks/{task_id}/requirements/validate')
def validate_requirements(task_id:str):
 task=repo.get_task(task_id)
 if not task:raise HTTPException(404,'Task not found')
 issues=requirement_issues(task);revision=repo.save_requirement_issues(task_id,issues)
 if issues:repo.pause_task(task_id,'NEEDS_INPUT','router',{'code':'REQUIREMENT_ISSUES','issues':issues,'revision':revision},'需求缺漏、矛盾或不安全；請補正後重跑')
 return {'task_id':task_id,'valid':not issues,'revision':revision,'issues':issues}
@app.post('/api/tasks/{task_id}/requirements/revise')
def revise_requirements(task_id:str,data:RequirementSupplement):
 current=repo.get_task(task_id)
 if not current:raise HTTPException(404,'Task not found')
 config=dict(current.get('source_config') or {});config['requirement_supplement']={'values':data.values,'note':data.note,'submitted_at':datetime.now(timezone.utc).isoformat()}
 repo.update_source_config(task_id,config);repo.resolve_requirement_issues(task_id);repo.reset_task(task_id)
 return {'status':'CREATED','task_id':task_id,'resume_from':'REQUIREMENT_GATE'}
@app.post('/api/tasks/{task_id}/naming-contract/suggest')
def suggest_naming_contract(task_id:str):
 task=repo.get_task(task_id)
 if not task:raise HTTPException(404,'Task not found')
 try:
  profile=profile_task(task);project=repo.get_project(task['project_id']) or {};contract=naming_suggestions(profile,project.get('naming_rules') or {})
  return {'task_id':task_id,'profile':{'columns':profile['columns'],'issues':profile['issues']},'contract':contract}
 except Exception as exc:raise HTTPException(422,str(exc)) from exc
@app.post('/api/tasks/{task_id}/naming-contract/confirm')
def confirm_naming_contract(task_id:str,data:NamingContractInput):
 task=repo.get_task(task_id)
 if not task:raise HTTPException(404,'Task not found')
 columns=data.columns
 if not columns:raise HTTPException(422,'至少需要一個欄位命名')
 names=[str(x.get('english_name') or '') for x in columns]
 if len(names)!=len(set(names)) or any(not re.fullmatch(r'[a-z_][a-z0-9_]*',x) for x in names):raise HTTPException(422,'英文欄位必須為唯一 snake_case identifier')
 contract={'contract_type':'NamingContractV1','status':'CONFIRMED','columns':columns,'checksum':__import__('hashlib').sha256(json.dumps(columns,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
 return repo.confirm_naming_contract(task_id,contract)
@app.post('/api/tasks/{task_id}/sample-source/rebuild')
def rebuild_sample_source(task_id:str):
 task=repo.get_task(task_id)
 if not task:raise HTTPException(404,'Task not found')
 source=((task.get('source_config') or {}).get('sources') or [task.get('source_config') or {}])[0]
 if source.get('type')!='VERTICA' or source.get('has_actual_data',True) is not False:raise HTTPException(422,'僅無既有資料的 Vertica 範例來源可重建')
 schema=str(source.get('schema') or 'ai_sample');table=str(source.get('object') or source.get('table') or f"sample_{task_id.lower().replace('-','_')}")
 if schema!='ai_sample':raise HTTPException(403,'範例表只能建立於 ai_sample')
 owner=repo.managed_sample_table(task['project_id'],schema,table)
 if owner and owner['project_id']!=task['project_id']:raise HTTPException(403,'此表不屬於目前 Project')
 try:
  result=rebuild_managed_sample(schema,table,source.get('fields') or [],source.get('sample_rows') or None,allow_replace=bool(owner));result=repo.register_sample_table(task['project_id'],task_id,result)
  config=dict(task['source_config']);config['sources']=[{**source,'schema':schema,'object':table,'has_actual_data':True}];repo.update_source_config(task_id,config)
  return result
 except Exception as exc:raise HTTPException(422,str(exc)) from exc
@app.post('/api/task-sources/upload')
async def upload_task_source(file:UploadFile=File(...)):
 policy=repo.setting('upload_policy',{}) or {};cleanup_expired(int(policy.get('retention_days',7)))
 try:return save_and_profile(file.filename or '',await file.read(),int(policy.get('retention_days',7)),int(policy.get('max_file_mb',50)))
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@app.get('/api/tasks/{task_id}')
def task(task_id:str):
 d=repo.get_task(task_id)
 if not d:raise HTTPException(404,'Task not found')
 return d
@app.get('/api/tasks/{task_id}/hpl-view')
def hpl_view(task_id:str):
 d=repo.get_task(task_id)
 if not d:raise HTTPException(404,'Task not found')
 executor=next((n for n in d.get('nodes',[]) if n['key']=='executor'),None)
 if not executor or executor['status']!='SUCCEEDED':raise HTTPException(409,'HPL preview is available after Hop Executor succeeds')
 artifact=repo.current_hpl(task_id)
 if not artifact:raise HTTPException(404,'Current HPL artifact not found')
 root_path=(ROOT/'hop-project').resolve();path=Path(artifact['file_path']).resolve()
 if path.suffix.lower()!='.hpl' or root_path not in path.parents:raise HTTPException(400,'Registered HPL path is outside hop-project')
 if not path.is_file():raise HTTPException(404,'HPL file is missing')
 xml=path.read_text(encoding='utf-8');root=ET.fromstring(xml)
 transforms=[]
 for item in root.findall('transform'):
  transforms.append({'name':item.findtext('name') or 'Unnamed','type':item.findtext('type') or 'Unknown','x':int(item.findtext('GUI/xloc') or 0),'y':int(item.findtext('GUI/yloc') or 0)})
 hops=[{'from':h.findtext('from'),'to':h.findtext('to'),'enabled':h.findtext('enabled')=='Y'} for h in root.findall('order/hop')]
 return {'task_id':task_id,**artifact,'transforms':sorted(transforms,key=lambda x:(x['x'],x['y'])),'hops':hops,'xml':xml}
@app.get('/api/tasks/{task_id}/history-assets')
def task_history_assets(task_id:str):
 d=repo.get_task(task_id)
 if not d:raise HTTPException(404,'Task not found')
 assets=repo.task_history_assets(task_id);root_path=(ROOT/'hop-project').resolve();jobs=[];sql=[]
 for artifact in assets['artifacts']:
  path=Path(artifact['file_path']).resolve();content='';transforms=[];hops=[]
  if path.is_file() and root_path in path.parents:
   content=path.read_text(encoding='utf-8',errors='replace')
   try:
    xml_root=ET.fromstring(content)
    for node in xml_root.findall('transform'):
     name=node.findtext('name') or 'Unnamed';kind=node.findtext('type') or 'Unknown';transforms.append({'name':name,'type':kind})
     for tag in ('sql','query','sql_statement'):
      statement=node.findtext(tag)
      if statement and statement.strip():sql.append({'artifact_id':artifact['artifact_id'],'artifact':path.name,'node':name,'sql':statement.strip()})
    if xml_root.tag=='workflow':
     for node in xml_root.findall('actions/action'):
      name=node.findtext('name') or 'Unnamed';kind=node.findtext('type') or 'Unknown';transforms.append({'name':name,'type':kind});statement=node.findtext('sql')
      if statement and statement.strip():sql.append({'artifact_id':artifact['artifact_id'],'artifact':path.name,'node':name,'sql':statement.strip()})
     hops=[{'from':x.findtext('from'),'to':x.findtext('to'),'enabled':x.findtext('enabled')=='Y'} for x in xml_root.findall('hops/hop')]
    else:hops=[{'from':x.findtext('from'),'to':x.findtext('to'),'enabled':x.findtext('enabled')=='Y'} for x in xml_root.findall('order/hop')]
   except ET.ParseError:pass
  jobs.append({**artifact,'name':path.name,'content':content,'transforms':transforms,'hops':hops,'download_url':f"/api/tasks/{task_id}/artifacts/{artifact['artifact_id']}/download"})
 return {**assets,'jobs':jobs,'sql':sql,'download_enabled':d['status']=='SUCCEEDED'}
@app.get('/api/tasks/{task_id}/artifacts/{artifact_id}/download')
def download_task_artifact(task_id:str,artifact_id:str):
 d=repo.get_task(task_id)
 if not d:raise HTTPException(404,'Task not found')
 if d['status']!='SUCCEEDED':raise HTTPException(409,'Only successful tasks can download artifacts')
 assets=repo.task_history_assets(task_id);artifact=next((x for x in assets['artifacts'] if x['artifact_id']==artifact_id),None)
 if not artifact:raise HTTPException(404,'Artifact not found')
 root_path=(ROOT/'hop-project').resolve();path=Path(artifact['file_path']).resolve()
 if root_path not in path.parents or path.suffix.lower() not in ('.hpl','.hwf'):raise HTTPException(400,'Artifact path is not allowed')
 if not path.is_file():raise HTTPException(404,'Artifact file is missing')
 return FileResponse(path,filename=path.name,media_type='application/xml')
@app.put('/api/tasks/{task_id}')
def update_task(task_id:str,data:TaskUpdate):
 d=repo.get_task(task_id)
 if not d:raise HTTPException(404,'Task not found')
 if d['status']=='RUNNING':raise HTTPException(409,'Running task cannot be edited')
 return repo.update_task(task_id,data.model_dump())
@app.post('/api/tasks/{task_id}/rerun')
def rerun(task_id:str):
 if not repo.reset_task(task_id):raise HTTPException(404,'Task not found')
 return {'status':'CREATED','task_id':task_id}
@app.post('/api/tasks/{task_id}/supplement')
def supplement(task_id:str,data:RequirementSupplement):
 current=repo.get_task(task_id)
 if not current:raise HTTPException(404,'Task not found')
 if current['status'] not in ('NEEDS_INPUT','REVIEW_REQUIRED'):raise HTTPException(409,'Task is not waiting for supplemental input')
 config=dict(current.get('source_config') or {});config['requirement_supplement']={'values':data.values,'note':data.note,'submitted_at':datetime.now(timezone.utc).isoformat()}
 repo.update_source_config(task_id,config)
 if not repo.reset_task(task_id):raise HTTPException(404,'Task not found')
 return {'status':'CREATED','task_id':task_id,'resume_from':'Requirement Gate','source_profile_reuse':'checksum_or_metadata_match'}
@app.post('/api/tasks/{task_id}/run')
def run_task(task_id:str):
 t=repo.get_task(task_id)
 if not t:raise HTTPException(404,'Task not found')
 issues=requirement_issues(t)
 if issues:
  revision=repo.save_requirement_issues(task_id,issues);repo.pause_task(task_id,'NEEDS_INPUT','router',{'code':'REQUIREMENT_ISSUES','issues':issues,'revision':revision},'Requirement Gate 發現缺漏、矛盾或不安全設定；請補正後重跑');return repo.get_task(task_id)
 if t['source'] in ('CSV','EXCEL','JSON'):
  contract=repo.naming_contract(task_id)
  if not contract or contract['status']!='CONFIRMED':
   repo.pause_task(task_id,'NEEDS_INPUT','router',{'code':'NAMING_CONFIRMATION_REQUIRED','action':'呼叫 /naming-contract/suggest，確認後再重跑'},'檔案來源必須先確認中英欄位與型別 NamingContract');return repo.get_task(task_id)
 if not repo.claim_task(task_id):raise HTTPException(409,'Task is already running or must be reset before execution')
 t=repo.get_task(task_id)
 cfg=t.get('error_test_config') or {}
 def inject(node_key:str):
  if not cfg.get('enabled') or cfg.get('node')!=node_key:return None
  code=cfg.get('expected_error_code') or 'INJECTED_TEST_ERROR';detail={'code':code,'error_test':True,'test_passed':True,'scenario':cfg.get('scenario'),'description':cfg.get('description'),'action':f'錯誤情境測試 PASSED：系統已在指定步驟攔截 {code}'}
  repo.update_node(task_id,node_key,'FAILED',detail,f"Error scenario test triggered at {node_key}: {code}")
  repo.set_error_test_result(task_id,{'passed':True,'expected_error_code':code,'actual_error_code':code,'node':node_key,'scenario':cfg.get('scenario'),'message':'系統成功攔截預期錯誤'})
  return repo.get_task(task_id)
 repo.update_node(task_id,'router','RUNNING',message='Rule Router started')
 injected=inject('router')
 if injected:return injected
 operation=t['type']
 repo.update_node(task_id,'router','SUCCEEDED',{'operation':operation},f'Rule Router selected {operation}')
 repo.update_node(task_id,'profiler','RUNNING',message='Source Profiler started')
 injected=inject('profiler')
 if injected:return injected
 if t['source'] in ('CSV','EXCEL','JSON','VERTICA','MIXED'):
  try:
   configured=(t.get('source_config',{}) or {}).get('sources') or []
   if t.get('source_config',{}).get('has_actual_data') is False or any(x.get('has_actual_data') is False for x in configured):
    t['source_config']=materialize_samples(task_id,t['source_config']);repo.update_source_config(task_id,t['source_config'])
    if len(t['source_config']['sources'])==1:t['source_config']={**t['source_config'],**t['source_config']['sources'][0]};repo.update_source_config(task_id,t['source_config'])
   if str(t['target_config'].get('stage_mode','NORMAL')).upper() in ('EXTERNAL','FLEX'):
    server_source=((t.get('source_config',{}) or {}).get('sources') or [t.get('source_config',{})])[0];t['target_config']=materialize_stage_server_sample(task_id,t['target_config'],server_source);repo.update_target_config(task_id,t['target_config'])
   source_profile=profile_task(t);sample=source_profile['samples'];columns=source_profile['columns']
   if t['source']=='EXCEL':
    execution_dir=ROOT/'runtime-temp'/'generated-sources'/task_id;execution_dir.mkdir(parents=True,exist_ok=True);execution_path=execution_dir/'excel-execution.csv'
    with execution_path.open('w',encoding='utf-8-sig',newline='') as stream:
     writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows([{name:row.get(name) for name in columns} for row in sample[:10]])
    t['source_config']={**t['source_config'],'file_path':str(execution_path),'execution_source_type':'CSV','delimiter':',','encoding':'utf-8-sig'};repo.update_source_config(task_id,t['source_config'])
   if len(source_profile['sources'])==1 and str(t['target_config'].get('stage_mode','NORMAL')).upper()=='NORMAL':
    configured_fields=(t.get('source_config') or {}).get('fields') or []
    fields=configured_fields if configured_fields and all(x.get('name') and x.get('type') for x in configured_fields) else source_profile['sources'][0].get('fields') or []
    ensure_sample_target(t['target_config'],fields)
    if fields is not configured_fields:
     t['source_config']={**t['source_config'],'fields':fields};repo.update_source_config(task_id,t['source_config'])
   class ProfileReader:fieldnames=columns
   reader=ProfileReader()
   repo.save_source_profile(task_id,source_profile)
   repo.update_node(task_id,'profiler','SUCCEEDED',{'sources':source_profile['sources'],'columns':columns,'sample_rows':len(sample),'fingerprint':source_profile['fingerprint'],'issues':source_profile['issues']},f"Source profile completed for {len(source_profile['sources'])} source(s)")
  except Exception as e:
   repo.update_node(task_id,'profiler','FAILED',{'code':'SOURCE_PROFILE_ERROR','error':str(e)},'Source profiling failed');return repo.get_task(task_id)
 else:
  configured=t['source_config'].get('sources') or [{'alias':'src','schema':t['source_config'].get('schema') or 'poc_source','table':t['source_config'].get('table') or 'demo_customer_orders','fields':[]}]
  try:
   if not isinstance(configured,list) or not configured:raise ValueError('At least one PostgreSQL source is required')
   profiles=[]
   with repo.conn() as conn:
    for source in configured:
     schema=source.get('schema','');table=source.get('table','');alias=source.get('alias','')
     if not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',x or '') for x in (schema,table,alias)):raise ValueError(f'Invalid source identifier: {source}')
     actual=conn.execute("select column_name,data_type from information_schema.columns where table_schema=%s and table_name=%s order by ordinal_position",(schema,table)).fetchall()
     if not actual:raise ValueError(f'Source table {schema}.{table} does not exist or has no columns')
     actual_fields=[{'name':x['column_name'],'type':x['data_type']} for x in actual]
     provided=source.get('fields') or []
     if isinstance(provided,str):provided=[{'name':part.split(':',1)[0].strip(),'type':part.split(':',1)[1].strip() if ':' in part else ''} for part in provided.split(',') if part.strip()]
     missing=[x.get('name') for x in provided if x.get('name') not in {a['name'] for a in actual_fields}]
     if missing:raise ValueError(f"Configured fields not found in {schema}.{table}: {', '.join(missing)}")
     profiles.append({'alias':alias,'schema':schema,'table':table,'provided_fields':provided,'actual_fields':actual_fields})
     preview=conn.execute(f'SELECT * FROM "{schema}"."{table}" LIMIT 3');profiles[-1]['sample']=[dict(x) for x in preview.fetchall()]
    raw_query=t['source_config'].get('query','').strip()
    if raw_query:
     query=validate_query_sources(validate_read_only_query(raw_query),configured);rows=conn.execute(f'SELECT * FROM ({query}) AS source_preview LIMIT 10');columns=[x.name for x in rows.description];sample=[dict(x) for x in rows.fetchall()]
    elif len(configured)==1:
     query=f'SELECT * FROM "{configured[0]["schema"]}"."{configured[0]["table"]}"';rows=conn.execute(f'SELECT * FROM ({query}) AS source_preview LIMIT 10');columns=[x.name for x in rows.description];sample=[dict(x) for x in rows.fetchall()]
    else:
     query='';columns=[f"{p['alias']}.{f['name']}" for p in profiles for f in p['actual_fields']];sample=[{'source':p['alias'],'rows':p['sample']} for p in profiles]
   t['source_config']['sources']=configured
   if query:t['source_config']['query']=query
   repo.update_node(task_id,'profiler','SUCCEEDED',{'sources':profiles,'source_count':len(profiles),'columns':columns,'sample_rows':sum(len(p['sample']) for p in profiles),'query':query or None,'query_pending':not bool(query)},f'PostgreSQL source profile completed for {len(profiles)} source(s); SQL generation {"not required" if query else "pending SA Agent"}')
  except Exception as e:
   repo.update_node(task_id,'profiler','FAILED',{'code':'POSTGRESQL_PROFILE_ERROR','error':str(e),'sources':configured},'PostgreSQL multi-source profiling failed');return repo.get_task(task_id)
 project=repo.get_project(t['project_id']) or {};profile_id=project.get('default_ai_profile','nova-default');ai_profile=repo.ai_profile(profile_id)
 repo.update_node(task_id,'sa','RUNNING',message='Requirement / SA Agent preflight started')
 injected=inject('sa')
 if injected:return injected
 if not ai_profile or not ai_profile.get('enabled'):
  repo.pause_task(task_id,'MODEL_RETRY_REQUIRED','sa',{'code':'MODEL_PROFILE_UNAVAILABLE','profile_id':profile_id,'action':'檢查平台設定中心的 AI Provider Profile'},'AI Profile 不可用；Task 已停止');return repo.get_task(task_id)
 try:
  columns_for_model=(reader.fieldnames or []) if t['source']=='CSV' else columns
  model_input={'task_id':task_id,'requirement':t['requirement'],'source_columns':columns_for_model};raw_specification,model_run=litellm_complete(ai_profile,'etl_specification',[{'role':'system','content':'你是企業 ETL Specification Agent。只能回傳有效 JSON，不可執行工具或修改檔案。'},{'role':'user','content':sa_prompt(t,sample,columns_for_model)}])
  repo.record_harness_invocation(task_id,'ETL_SPECIFICATION','litellm_bedrock',model_run['model'],1,checksum(model_input),model_input,raw_specification,'SUCCEEDED',model_run['duration_ms'])
  profile=profile_task(t) if t['source'] in ('CSV','EXCEL','VERTICA','MIXED') else {'sources':t['source_config'].get('sources') or [],'samples':sample,'columns':columns_for_model,'issues':[]}
  repo.save_source_profile(task_id,profile)
  specification=canonicalize(raw_specification,t,profile)
  specification.update(plan(specification))
  gate=requirement_gate(t,specification,profile)
  specification['missing_items']=[x for x in gate['issues'] if x.get('severity')=='BLOCKING']
  specification['warnings'].extend(x for x in gate['issues'] if x.get('severity') in ('WARNING','INFERRED'))
  repo.save_specification(task_id,specification,'VALIDATED' if gate['valid'] else gate['status'])
  if not gate['valid']:
   repo.record_agent_usage(task_id,'REQUIREMENT_SA',t['requirement'],{'source_config':t['source_config'],'target_config':t['target_config']},specification,model_run)
   repo.pause_task(task_id,gate['status'],'sa',{'code':gate['status'],'issues':gate['issues'],'editable_fields':[x['field'] for x in gate['issues']]},'需求需補充或人工確認後，將從 Requirement Gate 重新執行');return repo.get_task(task_id)
  vertica_sources=[s for s in profile['sources'] if s.get('type')=='VERTICA']
  if vertica_sources and not t['source_config'].get('query'):
   candidate=specification.get('sql_query') or ''
   if len(vertica_sources)==1 and not candidate.strip():
    source=vertica_sources[0];names=[f['name'] for f in source.get('fields') or []]
    candidate='SELECT '+','.join(f'"{name}"' for name in names)+f' FROM "{source["schema"]}"."{source.get("object") or source.get("table")}"'
   generated,columns,sample,explain=validate_vertica_query(candidate,vertica_sources)
   t['source_config']['sources']=profile['sources'];t['source_config']['query']=generated;t['source_config']['output_fields']=columns
   repo.update_source_config(task_id,t['source_config']);specification.update({'sql_query':generated,'generated_query_preview_rows':len(sample),'vertica_explain':explain})
   repo.save_specification(task_id,specification,'VALIDATED')
  if t['source']=='POSTGRESQL_TABLE' and len(t['source_config'].get('sources') or [])>1 and not t['source_config'].get('query'):
   generated=validate_query_sources(validate_read_only_query(specification.get('sql_query') or ''),t['source_config']['sources'])
   with repo.conn() as conn:
    preview=conn.execute(f'SELECT * FROM ({generated}) AS generated_preview LIMIT 10');columns=[x.name for x in preview.description];sample=[dict(x) for x in preview.fetchall()]
   t['source_config']['query']=generated;repo.update_source_config(task_id,t['source_config']);specification['sql_query']=generated;specification['generated_query_preview_rows']=len(sample)
  repo.record_agent_usage(task_id,'REQUIREMENT_SA',t['requirement'],{'source_config':t['source_config'],'target_config':t['target_config']},specification,model_run)
  repo.update_node(task_id,'sa','SUCCEEDED',{'specification':specification,'model_run':model_run},f"Requirement / SA Agent completed through {model_run['model']}")
 except subprocess.TimeoutExpired:
  repo.pause_task(task_id,'MODEL_RETRY_REQUIRED','sa',{'code':'MODEL_TIMEOUT','profile_id':profile_id,'timeout_seconds':180,'action':'重試 AI Profile'},'模型逾時；Task 已停止');return repo.get_task(task_id)
 except Exception as e:
  repo.pause_task(task_id,'MODEL_RETRY_REQUIRED','sa',{'code':'MODEL_OUTPUT_OR_SCHEMA_INVALID','profile_id':profile_id,'error':str(e)[:4000],'action':'檢查 Bedrock/LiteLLM 設定後重試'},'模型輸出或設定無效；Task 已停止');return repo.get_task(task_id)
 repo.update_node(task_id,'developer','RUNNING',message='Developer Agent started HPL generation')
 injected=inject('developer')
 if injected:return injected
 try:
  artifact=build_hpl(t,(reader.fieldnames or []) if t['source']=='CSV' else columns)
  if artifact.get('sql_pushdown') and artifact.get('query'):ensure_query_target(t['target_config'],artifact['query'])
  artifact_id=persist_artifact(DB,task_id,artifact)
  repo.update_node(task_id,'developer','SUCCEEDED',{**artifact,'artifact_id':artifact_id},f"Developer Agent generated {artifact.get('artifact_type','HPL')} v{artifact['version']}")
 except Exception as e:
  repo.update_node(task_id,'developer','FAILED',{'code':'HPL_GENERATION_FAILED','error':str(e)},'Developer Agent failed to generate HPL');return repo.get_task(task_id)
 repo.update_node(task_id,'static','RUNNING',message='Programmatic Static Validator started')
 injected=inject('static')
 if injected:return injected
 try:
  static_result=static_validate(artifact);persist_validation(DB,task_id,'STATIC',static_result)
  if not static_result['valid']:
   repo.update_node(task_id,'static','FAILED',{'code':'STATIC_VALIDATION_FAILED',**static_result},'HPL static validation failed');return repo.get_task(task_id)
  repo.update_node(task_id,'static','SUCCEEDED',static_result,'HPL XML and required transforms passed static validation')
 except Exception as e:
  repo.update_node(task_id,'static','FAILED',{'code':'STATIC_VALIDATION_ERROR','error':str(e)},'Static Validator raised an error');return repo.get_task(task_id)
 repo.update_node(task_id,'semantic','RUNNING',message='Semantic Validator started')
 injected=inject('semantic')
 if injected:return injected
 semantic_result=semantic_validate(t,artifact);persist_validation(DB,task_id,'SEMANTIC',semantic_result)
 if not semantic_result['valid']:
  repo.update_node(task_id,'semantic','FAILED',{'code':'SEMANTIC_VALIDATION_FAILED',**semantic_result},'HPL semantic validation failed');return repo.get_task(task_id)
 repo.update_node(task_id,'semantic','SUCCEEDED',semantic_result,'HPL matches source, target and validation policy')
 repo.update_node(task_id,'executor','RUNNING',message='Independent Hop Executor started hop-run.bat')
 injected=inject('executor')
 if injected:return injected
 try:
  hop_result=execute_hop(DB,t,artifact,artifact_id)
  if hop_result['exit_code']!=0:
   repo.update_node(task_id,'executor','FAILED',{'code':'HOP_EXECUTION_FAILED',**hop_result},'Apache Hop returned a non-zero exit code');return repo.get_task(task_id)
  repo.update_node(task_id,'executor','SUCCEEDED',hop_result,f"Apache Hop completed and wrote {hop_result['rows_written']} rows")
 except Exception as e:
  repo.update_node(task_id,'executor','FAILED',{'code':'HOP_EXECUTION_ERROR','error':str(e)},'Hop Executor raised an error');return repo.get_task(task_id)
 repo.update_node(task_id,'postwrite','RUNNING',message='Post-write count validation started')
 injected=inject('postwrite')
 if injected:return injected
 if hop_result['rows_written']<1 or hop_result['rows_written']>10:
  repo.update_node(task_id,'postwrite','FAILED',{'code':'POST_WRITE_COUNT_MISMATCH',**hop_result},'Post-write count is outside the expected 1..10 range');return repo.get_task(task_id)
 repo.set_rows(task_id,hop_result['rows_written'])
 repo.update_node(task_id,'postwrite','SUCCEEDED',{'rows_written':hop_result['rows_written'],'post_write_count':hop_result['after_count'],'policy':'FIRST_10_VALID_ROWS'},'Post-write count validation passed')
 return repo.get_task(task_id)
@app.get('/api/models')
def models():return {'providers':[cli_probe('codex_cli'),cli_probe('copilot')],'ai_profiles':repo.ai_profiles(),'usage':repo.usage(),'task_usage':repo.task_usage(),'analyzer_usage':repo.analyzer_usage()}
@app.post('/api/models/{provider}/health')
def model_health(provider:str):
 if provider not in ('codex_cli','copilot'):raise HTTPException(404,'Provider not found')
 return cli_probe(provider)
@app.get('/api/database/status')
def database_status():
 try:
  result={'status':'CONNECTED','host':'127.0.0.1','port':5432,'database':'ai_agents',**repo.migration_status()}
  try:
   import vertica_python
   cfg={'host':os.getenv('VERTICA_HOST','127.0.0.1'),'port':int(os.getenv('VERTICA_PORT','5433')),'user':os.getenv('VERTICA_USER','dbadmin'),'password':os.getenv('VERTICA_PASSWORD',''),'database':os.getenv('VERTICA_DATABASE',''),'tlsmode':os.getenv('VERTICA_TLSMODE','disable')}
   with vertica_python.connect(**cfg) as conn:
    cur=conn.cursor();cur.execute('select current_database(), version()');database,version=cur.fetchone()
   result['vertica']={'status':'CONNECTED','host':cfg['host'],'port':cfg['port'],'database':database,'user':cfg['user'],'version':version}
  except Exception as e:result['vertica']={'status':'ERROR','detail':str(e)}
  return result
 except Exception as e:return {'status':'ERROR','detail':str(e)}
@app.post('/api/database/test')
def database_test():return database_status()
@app.get('/api/settings')
def settings():return {'mode':'postgres','hop_run':os.getenv('HOP_RUN_PATH'),'sample_policy':'FIRST_10_VALID_ROWS','max_rows':10,'temp_cleanup':True,'feature_flags':repo.setting('feature_flags',{'test_mode_enabled':False}),'upload_policy':repo.setting('upload_policy',{'retention_days':7,'max_file_mb':50}),'vertica_stage_paths':repo.setting('vertica_stage_paths',{}),'stored':repo.settings(),'groups':settings_groups(),'ai_profiles':repo.ai_profiles()}
def settings_groups():
 return {'AI 供應商與模型策略':'ai_provider_model_strategy','資料連線與目標':'data_connections_targets','執行環境與工具路徑':'execution_tool_paths','資料治理與命名規則':'data_governance_naming_rules','驗證與交付策略':'validation_release_policy','安全密鑰保管庫':'security_secret_vault'}
@app.get('/api/settings/groups')
def get_setting_groups():return {'groups':settings_groups(),'values':{key:repo.setting(key,{}) for key in settings_groups().values()}}
@app.put('/api/settings/groups/{group_key}')
def update_setting_group(group_key:str,value:dict[str,Any]):
 if group_key not in settings_groups().values():raise HTTPException(404,'Setting group not found')
 try:return {'key':group_key,'value':repo.update_setting(group_key,value)}
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@app.put('/api/settings/ai-profiles/{profile_id}')
def put_ai_profile(profile_id:str,value:dict[str,Any]):
 try:return repo.upsert_ai_profile({**value,'profile_id':profile_id})
 except Exception as exc:raise HTTPException(422,str(exc)) from exc
@app.post('/api/settings/ai-profiles/{profile_id}/secret')
def put_ai_profile_secret(profile_id:str,data:SecretInput):
 if not repo.ai_profile(profile_id):raise HTTPException(404,'AI profile not found')
 try:
  cipher,nonce=encrypt_secret(data.secret_value);secret_ref=f'ai-profile:{profile_id}';repo.save_secret(secret_ref,cipher,nonce);return repo.upsert_ai_profile({**repo.ai_profile(profile_id),'secret_ref':secret_ref})
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@app.post('/api/settings/connections/{connection_id}/secret')
def put_connection_secret(connection_id:str,data:SecretInput):
 if not re.fullmatch(r'[A-Za-z0-9_-]{2,80}',connection_id):raise HTTPException(422,'Invalid connection id')
 try:
  cipher,nonce=encrypt_secret(data.secret_value);repo.save_secret(f'connection:{connection_id}',cipher,nonce)
  return {'connection_id':connection_id,'secret_configured':True}
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@app.post('/api/settings/ai-profiles/{profile_id}/test')
def test_ai_profile(profile_id:str):
 profile=repo.ai_profile(profile_id)
 if not profile:raise HTTPException(404,'AI profile not found')
 routes=profile.get('model_routes') or {}
 return {'profile_id':profile_id,'status':'CONFIGURED' if profile.get('enabled') and routes else 'ATTENTION','provider_type':profile.get('provider_type'),'models':routes,'secret_configured':bool(profile.get('secret_ref')),'detail':'呼叫測試需在設定 LiteLLM 與 AWS credentials 後執行；此檢查不會洩露機密。'}
@app.get('/api/tasks/{task_id}/trace')
def task_trace(task_id:str):
 if not repo.get_task(task_id):raise HTTPException(404,'Task not found')
 return repo.trace(task_id)
@app.post('/api/tasks/{task_id}/release')
def build_release(task_id:str):
 task=repo.get_task(task_id)
 if not task:raise HTTPException(404,'Task not found')
 if task['status']!='SUCCEEDED':raise HTTPException(409,'Release requires a successful Task')
 contract=repo.naming_contract(task_id)
 if not contract or contract['status']!='CONFIRMED':raise HTTPException(409,'Release requires a confirmed NamingContract')
 assets=repo.task_history_assets(task_id)
 if not assets['artifacts']:raise HTTPException(409,'Release requires registered Hop artifacts')
 try:
  sdm=create_sdm(task,contract);repo.save_sdm(task_id,sdm,artifact_sha(sdm));release_path,manifest=create_release(task,contract,assets,sdm);return repo.save_release(task_id,release_path,manifest)
 except Exception as exc:raise HTTPException(422,str(exc)) from exc
@app.get('/api/tasks/{task_id}/release/{release_id}/download')
def download_release(task_id:str,release_id:str):
 release=repo.release(task_id,release_id)
 if not release:raise HTTPException(404,'Release not found')
 path=Path(release['file_path']).resolve();root=(ROOT/'outputs'/'releases').resolve()
 if root not in path.parents or not path.is_file():raise HTTPException(404,'Release file is missing')
 return FileResponse(path,filename=path.name,media_type='application/zip')
@app.put('/api/settings/{key}')
def update_setting(key:str,value:dict[str,Any]):
 try:
  if key=='vertica_stage_paths':
   normalized=dict(value)
   for field in ('external_data_path','flex_data_path','reject_path','exception_path'):
    path=str(normalized.get(field,'')).rstrip('/')
    if not path.startswith('/') or '*' in path or '?' in path:raise ValueError(f'{field} 必須是 Vertica Server 絕對資料夾，不可包含檔名或萬用字元')
    normalized[field]=path
   value=normalized
  return {'key':key,'value':repo.update_setting(key,value)}
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
