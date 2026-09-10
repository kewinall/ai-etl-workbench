from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import psycopg
from psycopg.rows import dict_row

STEPS=[('router','Rule Router'),('profiler','Source Profiler'),('sa','Requirement / SA Agent'),('developer','Developer Agent'),('static','Static Validator'),('semantic','Semantic Validator'),('executor','Hop Executor'),('postwrite','Post-write Count')]

class PostgresRepository:
 def __init__(self,url:str): self.url=url
 def conn(self): return psycopg.connect(self.url,row_factory=dict_row)
 def migration_status(self):
  with self.conn() as c:
   tables=c.execute("select table_name from information_schema.tables where table_schema='platform' order by table_name").fetchall()
   return {'schema':'platform','tables':[r['table_name'] for r in tables],'count':len(tables),'runtime_ready':any(r['table_name']=='task_event' for r in tables)}
 def dashboard(self):
  with self.conn() as c:
   s=c.execute("select count(*) total,count(*) filter(where status in ('CREATED','RUNNING')) active,count(*) filter(where status='SUCCEEDED') succeeded,count(*) filter(where status='FAILED') failed,coalesce(sum(rows_written),0) rows_written from platform.task").fetchone()
   recent=c.execute(self._task_sql()+" order by t.created_at desc limit 5").fetchall()
  done=s['succeeded']+s['failed']; rate=round(s['succeeded']*100/done) if done else 0
  return {**dict(s),'success_rate':rate,'tasks':[self._shape(r) for r in recent]}
 def _task_sql(self):
  return """select t.task_id id,t.project_id,t.task_name name,t.task_type type,t.task_category category,t.requirement_text requirement,t.source_type source,t.target_type target,t.status,t.current_step,t.progress,t.rows_written rows,t.model_provider model,t.source_config,t.target_config,t.last_error,t.error_test_config,t.error_test_result,t.created_at,t.updated_at from platform.task t"""
 def _shape(self,r):
  d=dict(r); d['project_id']=str(d['project_id']) if d.get('project_id') else None; d['created_at']=d['created_at'].isoformat() if d.get('created_at') else None; d['updated_at']=d['updated_at'].isoformat() if d.get('updated_at') else None; return d
 def list_tasks(self):
  with self.conn() as c: rows=c.execute(self._task_sql()+" order by t.created_at desc").fetchall()
  return [self._shape(r) for r in rows]
 def get_task(self,task_id):
  with self.conn() as c:
   r=c.execute(self._task_sql()+" where t.task_id=%s",(task_id,)).fetchone()
   if not r:return None
   nodes=c.execute("select node_key key,node_label label,status,duration_ms,detail from platform.task_node_run where task_id=%s order by sequence_no",(task_id,)).fetchall()
   events=c.execute("select level,node_key,message,detail,created_at from platform.task_event where task_id=%s order by created_at,event_id",(task_id,)).fetchall()
  d=self._shape(r);d['nodes']=[dict(x) for x in nodes];d['logs']=[{'level':x['level'],'node':x['node_key'],'message':x['message'],'time':x['created_at'].isoformat(),'detail':x['detail']} for x in events];return d
 def next_id(self):
  prefix=datetime.now().strftime('TASK-%Y%m%d-')
  with self.conn() as c:
   vals=c.execute("select task_id from platform.task where task_id like %s order by task_id desc limit 1",(prefix+'%',)).fetchone()
  n=int(vals['task_id'].rsplit('-',1)[1])+1 if vals else 1; return prefix+f'{n:04d}'
 def create_task(self,data):
  task_id=self.next_id(); source=(data.get('source_type') or 'CSV').upper();source_config=dict(data.get('source_config') or {});operation=(data.get('operation') or 'NEW').upper()
  if operation not in ('NEW','ERROR_TEST'):raise ValueError('Operation only supports NEW or ERROR_TEST')
  configured=source_config.get('sources') or []
  if configured:
   source='MIXED' if len(configured)>1 else str(configured[0].get('type') or source).upper()
   if len(configured)==1 and configured[0].get('has_actual_data',source_config.get('has_actual_data',True)) is not False:
    source_config={**configured[0],**{k:v for k,v in source_config.items() if k!='sources'}}
    if source=='CSV':source_config['file_path']=source_config.get('path') or source_config.get('file_path')
  target=(data.get('target_type') or 'VERTICA').upper()
  if target not in ('POSTGRESQL','VERTICA'):raise ValueError('Unsupported target database')
  with self.conn() as c:
   target_config={**(data.get('target_config') or {}),'type':target,'schema':data['target_schema'],'table':data['target_table']}
   project_id=data.get('project_id') or '00000000-0000-0000-0000-000000000010'
   c.execute("insert into platform.task(task_id,project_id,task_name,task_type,task_category,requirement_text,status,current_step,source_type,source_config,target_type,target_config,model_provider,progress,error_test_config) values(%s,%s,%s,%s,%s,%s,'CREATED','router',%s,%s,%s,%s,%s,0,%s)",(task_id,project_id,data['name'],operation,data.get('category','STAGE'),data['requirement'],source,json.dumps(source_config),target,json.dumps(target_config),data['model'],json.dumps(data.get('error_test_config') or {})))
   for i,(key,label) in enumerate(STEPS): c.execute("insert into platform.task_node_run(node_run_id,task_id,node_key,node_label,sequence_no,status) values(%s,%s,%s,%s,%s,'PENDING')",(uuid.uuid4(),task_id,key,label,i+1))
   c.execute("insert into platform.task_event(task_id,level,node_key,message) values(%s,'INFO','router','Task created and persisted in PostgreSQL')",(task_id,))
  return self.get_task(task_id)
 def reset_task(self,task_id):
  with self.conn() as c:
   exists=c.execute("select 1 from platform.task where task_id=%s",(task_id,)).fetchone()
   if not exists:return False
   c.execute("update platform.task set status='CREATED',current_step='router',progress=0,rows_written=0,last_error=null,error_test_result=null,updated_at=now() where task_id=%s",(task_id,));c.execute("update platform.task_node_run set status='PENDING',started_at=null,ended_at=null,duration_ms=null,detail='{}' where task_id=%s",(task_id,));c.execute("delete from platform.task_event where task_id=%s",(task_id,));c.execute("insert into platform.task_event(task_id,level,node_key,message) values(%s,'INFO','router','Task reset for rerun')",(task_id,))
  return True
 def claim_task(self,task_id):
  with self.conn() as c:
   claimed=c.execute("update platform.task set status='RUNNING',updated_at=now() where task_id=%s and status in ('CREATED','MODEL_RETRY_REQUIRED') returning task_id",(task_id,)).fetchone()
  return bool(claimed)
 def update_task(self,task_id,data):
  source=(data.get('source_type') or 'CSV').upper();source_config=dict(data.get('source_config') or {});configured=source_config.get('sources') or [];operation=(data.get('operation') or 'NEW').upper()
  if operation not in ('NEW','ERROR_TEST'):raise ValueError('Operation only supports NEW or ERROR_TEST')
  if configured:
   source='MIXED' if len(configured)>1 else str(configured[0].get('type') or source).upper()
   if len(configured)==1 and configured[0].get('has_actual_data',source_config.get('has_actual_data',True)) is not False:
    source_config={**configured[0],**{k:v for k,v in source_config.items() if k!='sources'}}
    if source=='CSV':source_config['file_path']=source_config.get('path') or source_config.get('file_path')
  target=(data.get('target_type') or 'VERTICA').upper()
  if target not in ('POSTGRESQL','VERTICA'):raise ValueError('Unsupported target database')
  with self.conn() as c:
   target_config={**(data.get('target_config') or {}),'type':target,'schema':data['target_schema'],'table':data['target_table']}
   c.execute("update platform.task set task_name=%s,task_type=%s,task_category=%s,requirement_text=%s,source_type=%s,source_config=%s,target_type=%s,target_config=%s,model_provider=%s,error_test_config=%s,error_test_result=null,updated_at=now() where task_id=%s",(data['name'],operation,data.get('category','STAGE'),data['requirement'],source,json.dumps(source_config),target,json.dumps(target_config),data['model'],json.dumps(data.get('error_test_config') or {}),task_id))
   c.execute("insert into platform.task_event(task_id,level,node_key,message,detail) values(%s,'INFO',%s,'Task settings updated before rerun',%s)",(task_id,data['operation'].lower() if data['operation'].lower() in [s[0] for s in STEPS] else 'router',json.dumps({'source_type':source,'target':{'type':target,'schema':data['target_schema'],'table':data['target_table']},'model':data['model']})))
  return self.get_task(task_id)
 def update_source_config(self,task_id,source_config):
  with self.conn() as c:c.execute("update platform.task set source_config=%s,updated_at=now() where task_id=%s",(json.dumps(source_config),task_id))
 def update_target_config(self,task_id,target_config):
  with self.conn() as c:c.execute("update platform.task set target_config=%s,updated_at=now() where task_id=%s",(json.dumps(target_config),task_id))
 def pause_task(self,task_id,status,key,detail,message):
  if status not in ('NEEDS_INPUT','REVIEW_REQUIRED','MODEL_RETRY_REQUIRED'):raise ValueError('Invalid paused status')
  with self.conn() as c:
   c.execute("update platform.task_node_run set status='FAILED',ended_at=now(),detail=%s where task_id=%s and node_key=%s",(json.dumps(detail,default=str),task_id,key))
   c.execute("update platform.task set status=%s,current_step=%s,last_error=%s,updated_at=now() where task_id=%s",(status,key,json.dumps(detail,default=str),task_id))
   c.execute("insert into platform.task_event(task_id,level,node_key,message,detail) values(%s,'WARNING',%s,%s,%s)",(task_id,key,message,json.dumps(detail,default=str)))
 def save_source_profile(self,task_id,profile):
  safe={k:v for k,v in profile.items() if k!='samples'}
  with self.conn() as c:
   version=c.execute("select coalesce(max(profile_version),0)+1 version from platform.source_profile where task_id=%s",(task_id,)).fetchone()['version']
   c.execute("insert into platform.source_profile(profile_id,task_id,profile_version,profile_result,warning_detail) values(%s,%s,%s,%s,%s)",(uuid.uuid4(),task_id,version,json.dumps(safe,default=str),json.dumps(safe.get('issues') or [],default=str)))
 def save_specification(self,task_id,spec,status='VALIDATED'):
  with self.conn() as c:
   version=c.execute("select coalesce(max(version),0)+1 version from platform.specification where task_id=%s",(task_id,)).fetchone()['version']
   c.execute("update platform.specification set is_current=false where task_id=%s",(task_id,))
   c.execute("insert into platform.specification(specification_id,task_id,version,validation_status,spec_json,is_current) values(%s,%s,%s,%s,%s,true)",(uuid.uuid4(),task_id,version,status,json.dumps(spec,default=str)))
 def update_node(self,task_id,key,status,detail=None,message=None):
  now=datetime.now(timezone.utc); idx=next(i for i,s in enumerate(STEPS) if s[0]==key); progress=round(((idx+(1 if status=='SUCCEEDED' else 0))/len(STEPS))*100)
  with self.conn() as c:
   if status=='RUNNING': c.execute("update platform.task_node_run set status=%s,started_at=%s,detail=%s where task_id=%s and node_key=%s",(status,now,json.dumps(detail or {},default=str),task_id,key))
   else: c.execute("update platform.task_node_run set status=%s,ended_at=%s,duration_ms=extract(epoch from (%s-started_at))*1000,detail=%s where task_id=%s and node_key=%s",(status,now,now,json.dumps(detail or {},default=str),task_id,key))
   task_status='FAILED' if status=='FAILED' else ('SUCCEEDED' if key=='postwrite' and status=='SUCCEEDED' else 'RUNNING')
   c.execute("update platform.task set status=%s,current_step=%s,progress=%s,last_error=%s,updated_at=now() where task_id=%s",(task_status,key,progress,json.dumps(detail,default=str) if status=='FAILED' else None,task_id))
   if message:c.execute("insert into platform.task_event(task_id,level,node_key,message,detail) values(%s,%s,%s,%s,%s)",(task_id,'ERROR' if status=='FAILED' else 'INFO',key,message,json.dumps(detail or {},default=str)))
 def usage(self):
  with self.conn() as c: rows=c.execute("""with calls as (
   select ar.provider,ar.status,ar.duration_ms,mu.input_tokens,mu.cached_input_tokens,mu.output_tokens,mu.total_tokens,mu.premium_requests,mu.ai_credits,mu.nano_aiu,mu.usage_type from platform.agent_run ar left join platform.model_usage mu using(agent_run_id)
   union all
   select ai_provider,'SUCCEEDED',nullif(ai_usage->>'duration_ms','')::bigint,nullif(ai_usage->>'input_tokens','')::bigint,nullif(ai_usage->>'cached_input_tokens','')::bigint,nullif(ai_usage->>'output_tokens','')::bigint,nullif(ai_usage->>'total_tokens','')::bigint,nullif(ai_usage->>'premium_requests','')::numeric,nullif(ai_usage->>'ai_credits','')::numeric,nullif(ai_usage->>'nano_aiu','')::bigint,coalesce(ai_usage->>'usage_type','PARTIAL') from platform.etl_analysis where ai_provider is not null
  ) select provider,count(*) runs,count(*) filter(where status='SUCCEEDED') success,round(avg(duration_ms)/1000.0,2) latency,coalesce(sum(input_tokens),0) input_tokens,coalesce(sum(cached_input_tokens),0) cached_input_tokens,coalesce(sum(output_tokens),0) output_tokens,coalesce(sum(total_tokens),0) tokens,coalesce(sum(premium_requests),0) premium_requests,coalesce(sum(ai_credits),0) ai_credits,coalesce(sum(nano_aiu),0) nano_aiu,max(usage_type) usage_type from calls group by provider order by provider""").fetchall()
  return [dict(r) for r in rows]
 def task_usage(self):
  with self.conn() as c:rows=c.execute("select mu.usage_id,t.task_id,t.task_name,t.task_type,ar.agent_type,mu.provider,mu.model,ar.status,mu.input_tokens,mu.cached_input_tokens,mu.output_tokens,mu.total_tokens,mu.nano_aiu,mu.ai_credits,mu.premium_requests,mu.usage_type,mu.raw_usage,ar.started_at,ar.ended_at,ar.duration_ms from platform.model_usage mu left join platform.agent_run ar using(agent_run_id) left join platform.task t on t.task_id=coalesce(mu.task_id,ar.task_id) order by mu.created_at desc").fetchall()
  return [{**dict(r),'usage_id':str(r['usage_id']),'started_at':r['started_at'].isoformat() if r['started_at'] else None,'ended_at':r['ended_at'].isoformat() if r['ended_at'] else None} for r in rows]
 def analyzer_usage(self):
  with self.conn() as c:rows=c.execute("""select a.analysis_id,a.batch_id,b.task_name,a.source_name,a.source_relative_path,a.process_name,a.ai_provider provider,a.ai_model model,a.ai_usage,a.created_at
   from platform.etl_analysis a left join platform.etl_analysis_batch b using(batch_id) where a.ai_provider is not null order by a.created_at desc""").fetchall()
  return [{**dict(r),'analysis_id':str(r['analysis_id']),'batch_id':str(r['batch_id']) if r['batch_id'] else None,'created_at':r['created_at'].isoformat()} for r in rows]
 def current_hpl(self,task_id):
  with self.conn() as c:r=c.execute("select artifact_id,version,file_path,checksum,file_size,created_at from platform.hop_artifact where task_id=%s and artifact_type='HPL' and parent_artifact_id is null and is_current=true order by version desc limit 1",(task_id,)).fetchone()
  if not r:return None
  d=dict(r);d['artifact_id']=str(d['artifact_id']);d['created_at']=d['created_at'].isoformat();return d
 def task_history_assets(self,task_id):
  with self.conn() as c:
   artifacts=c.execute("select artifact_id,artifact_type,version,parent_artifact_id,file_path,checksum,file_size,is_current,created_at from platform.hop_artifact where task_id=%s order by version desc,parent_artifact_id nulls first,file_path",(task_id,)).fetchall()
   runs=c.execute("select hop_run_id,status,command_line,parameters,exit_code,rows_read,rows_valid,rows_written,rows_rejected,post_write_count,started_at,ended_at,duration_ms,error_detail from platform.hop_run where task_id=%s order by started_at desc nulls last",(task_id,)).fetchall()
   logs=c.execute("select l.hop_run_id,l.log_type,l.sequence_no,l.log_content,l.created_at from platform.hop_run_log l join platform.hop_run r using(hop_run_id) where r.task_id=%s order by l.created_at,l.sequence_no",(task_id,)).fetchall()
  def shaped(row):
   d=dict(row)
   for key in ('artifact_id','parent_artifact_id','hop_run_id'):
    if d.get(key) is not None:d[key]=str(d[key])
   for key in ('created_at','started_at','ended_at'):
    if d.get(key) is not None:d[key]=d[key].isoformat()
   return d
  return {'artifacts':[shaped(x) for x in artifacts],'hop_runs':[shaped(x) for x in runs],'hop_logs':[shaped(x) for x in logs]}
 def set_rows(self,task_id,rows):
  with self.conn() as c:c.execute("update platform.task set rows_written=%s,updated_at=now() where task_id=%s",(rows,task_id))
 def set_error_test_result(self,task_id,result):
  with self.conn() as c:c.execute("update platform.task set error_test_result=%s,updated_at=now() where task_id=%s",(json.dumps(result),task_id))
 def record_agent_usage(self,task_id,agent_type,prompt,structured_input,structured_output,run):
  agent_run_id=uuid.uuid4();usage_id=uuid.uuid4();duration=int(run.get('duration_ms') or 0);model=run.get('model');total=run.get('total_tokens');usage_type=run.get('usage_type','UNAVAILABLE');provider=run.get('provider') or 'unknown'
  with self.conn() as c:
   c.execute("insert into platform.agent_run(agent_run_id,task_id,agent_type,provider,model,status,input_prompt,structured_input,raw_output,structured_output,started_at,ended_at,duration_ms) values(%s,%s,%s,%s,%s,'SUCCEEDED',%s,%s,%s,%s,now()-(%s * interval '1 millisecond'),now(),%s)",(agent_run_id,task_id,agent_type,provider,model,prompt,json.dumps(structured_input),run.get('stdout',''),json.dumps(structured_output),duration,duration))
   c.execute("insert into platform.model_usage(usage_id,task_id,agent_run_id,provider,model,input_tokens,cached_input_tokens,output_tokens,total_tokens,nano_aiu,ai_credits,premium_requests,usage_type,raw_usage) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(usage_id,task_id,agent_run_id,provider,model,run.get('input_tokens'),run.get('cached_input_tokens'),run.get('output_tokens'),total,run.get('nano_aiu'),run.get('ai_credits'),run.get('premium_requests'),usage_type,json.dumps({'input_tokens':run.get('input_tokens'),'cached_input_tokens':run.get('cached_input_tokens'),'output_tokens':run.get('output_tokens'),'total_tokens':total,'source':run.get('usage_source'),'breakdown_available':run.get('input_tokens') is not None,'premium_requests':run.get('premium_requests'),'nano_aiu':run.get('nano_aiu'),'ai_credits':run.get('ai_credits'),'ai_credit_source':'copilot_cli_usage_checkpoint' if run.get('nano_aiu') is not None else None,'api_duration_ms':run.get('api_duration_ms'),'session_duration_ms':run.get('session_duration_ms')})))
 def settings(self):
  with self.conn() as c: rows=c.execute("select setting_key,setting_value,updated_at from platform.system_setting order by setting_key").fetchall()
  return [{'key':r['setting_key'],'value':r['setting_value'],'updated_at':r['updated_at'].isoformat()} for r in rows]
 def setting(self,key,default=None):
  with self.conn() as c:r=c.execute("select setting_value from platform.system_setting where setting_key=%s",(key,)).fetchone()
  return r['setting_value'] if r else default
 def update_setting(self,key,value):
  allowed={'feature_flags','upload_policy','validation_policy','storage_policy','vertica_stage_paths','ai_provider_model_strategy','data_connections_targets','execution_tool_paths','data_governance_naming_rules','validation_release_policy','security_secret_vault'}
  if key not in allowed:raise ValueError('Setting is not editable')
  with self.conn() as c:c.execute("insert into platform.system_setting(setting_key,setting_value,updated_at) values(%s,%s,now()) on conflict(setting_key) do update set setting_value=excluded.setting_value,updated_at=now()",(key,json.dumps(value)))
  return self.setting(key)
 def list_projects(self):
  with self.conn() as c:rows=c.execute("select project_id,project_name,description,default_ai_profile,default_connection,naming_rules,created_at,updated_at from platform.project order by project_name").fetchall()
  return [{**dict(r),'project_id':str(r['project_id']),'created_at':r['created_at'].isoformat(),'updated_at':r['updated_at'].isoformat()} for r in rows]
 def get_project(self,project_id):
  with self.conn() as c:r=c.execute("select project_id,project_name,description,default_ai_profile,default_connection,naming_rules,created_at,updated_at from platform.project where project_id=%s",(project_id,)).fetchone()
  if not r:return None
  return {**dict(r),'project_id':str(r['project_id']),'created_at':r['created_at'].isoformat(),'updated_at':r['updated_at'].isoformat()}
 def create_project(self,data):
  project_id=uuid.uuid4()
  with self.conn() as c:
   c.execute("insert into platform.project(project_id,project_name,description,default_ai_profile,default_connection,naming_rules) values(%s,%s,%s,%s,%s,%s)",(project_id,data['project_name'],data.get('description',''),data.get('default_ai_profile','nova-default'),data.get('default_connection','vertica-default'),json.dumps(data.get('naming_rules') or {})))
   c.execute("insert into platform.project_member(project_id,operator_id) values(%s,'00000000-0000-0000-0000-000000000001')",(project_id,))
  return self.get_project(project_id)
 def update_project(self,project_id,data):
  with self.conn() as c:c.execute("update platform.project set project_name=%s,description=%s,default_ai_profile=%s,default_connection=%s,naming_rules=%s,updated_at=now() where project_id=%s",(data['project_name'],data.get('description',''),data.get('default_ai_profile','nova-default'),data.get('default_connection','vertica-default'),json.dumps(data.get('naming_rules') or {}),project_id))
  return self.get_project(project_id)
 def save_requirement_issues(self,task_id,issues):
  with self.conn() as c:
   revision=c.execute("select coalesce(max(revision),0)+1 revision from platform.requirement_issue where task_id=%s",(task_id,)).fetchone()['revision']
   for issue in issues:c.execute("insert into platform.requirement_issue(issue_id,task_id,revision,issue_type,field_path,message,suggestion) values(%s,%s,%s,%s,%s,%s,%s)",(uuid.uuid4(),task_id,revision,issue['issue_type'],issue['field_path'],issue['message'],json.dumps(issue.get('suggestion') or {})))
  return revision
 def requirement_issues(self,task_id):
  with self.conn() as c:rows=c.execute("select issue_id,revision,issue_type,field_path,message,suggestion,resolved,created_at from platform.requirement_issue where task_id=%s order by revision desc,created_at",(task_id,)).fetchall()
  return [{**dict(r),'issue_id':str(r['issue_id']),'created_at':r['created_at'].isoformat()} for r in rows]
 def resolve_requirement_issues(self,task_id):
  with self.conn() as c:c.execute("update platform.requirement_issue set resolved=true where task_id=%s and not resolved",(task_id,))
 def save_naming_contract(self,task_id,contract,confirmed=False):
  with self.conn() as c:
   version=c.execute("select coalesce(max(version),0)+1 version from platform.naming_contract where task_id=%s",(task_id,)).fetchone()['version'];contract_id=uuid.uuid4();status='CONFIRMED' if confirmed else 'DRAFT'
   c.execute("insert into platform.naming_contract(contract_id,task_id,version,status,contract_json,checksum,confirmed_at) values(%s,%s,%s,%s,%s,%s,case when %s then now() else null end)",(contract_id,task_id,version,status,json.dumps(contract),contract['checksum'],confirmed))
   for ordinal,column in enumerate(contract['columns'],1):c.execute("insert into platform.naming_contract_column(contract_id,ordinal,source_name,english_name,vertica_type,confidence,reason) values(%s,%s,%s,%s,%s,%s,%s)",(contract_id,ordinal,column['source_name'],column['english_name'],column['vertica_type'],column['confidence'],column['reason']))
  return self.naming_contract(task_id)
 def naming_contract(self,task_id):
  with self.conn() as c:r=c.execute("select contract_id,version,status,contract_json,checksum,created_at,confirmed_at from platform.naming_contract where task_id=%s order by version desc limit 1",(task_id,)).fetchone()
  if not r:return None
  return {**dict(r),'contract_id':str(r['contract_id']),'created_at':r['created_at'].isoformat(),'confirmed_at':r['confirmed_at'].isoformat() if r['confirmed_at'] else None}
 def confirm_naming_contract(self,task_id,contract):
  return self.save_naming_contract(task_id,contract,True)
 def ai_profiles(self):
  with self.conn() as c:rows=c.execute("select profile_id,display_name,provider_type,endpoint,region,model_routes,enabled,secret_ref,updated_at from platform.ai_provider_profile order by profile_id").fetchall()
  return [{**dict(r),'secret_configured':bool(r['secret_ref']),'secret_ref':None,'updated_at':r['updated_at'].isoformat()} for r in rows]
 def ai_profile(self,profile_id):
  with self.conn() as c:r=c.execute("select profile_id,display_name,provider_type,endpoint,region,model_routes,enabled,secret_ref,updated_at from platform.ai_provider_profile where profile_id=%s",(profile_id,)).fetchone()
  return dict(r) if r else None
 def upsert_ai_profile(self,data):
  with self.conn() as c:c.execute("insert into platform.ai_provider_profile(profile_id,display_name,provider_type,endpoint,region,model_routes,enabled,secret_ref,updated_at) values(%s,%s,%s,%s,%s,%s,%s,%s,now()) on conflict(profile_id) do update set display_name=excluded.display_name,provider_type=excluded.provider_type,endpoint=excluded.endpoint,region=excluded.region,model_routes=excluded.model_routes,enabled=excluded.enabled,secret_ref=coalesce(excluded.secret_ref,platform.ai_provider_profile.secret_ref),updated_at=now()",(data['profile_id'],data['display_name'],data.get('provider_type','LITELLM_BEDROCK'),data.get('endpoint'),data.get('region'),json.dumps(data.get('model_routes') or {}),data.get('enabled',True),data.get('secret_ref')))
  return self.ai_profile(data['profile_id'])
 def save_secret(self,secret_ref,cipher,nonce):
  with self.conn() as c:c.execute("insert into platform.secret_vault_entry(secret_ref,cipher_text,nonce,updated_at) values(%s,%s,%s,now()) on conflict(secret_ref) do update set cipher_text=excluded.cipher_text,nonce=excluded.nonce,updated_at=now()",(secret_ref,cipher,nonce))
 def trace(self,task_id):
  with self.conn() as c:
   agents=c.execute("select role,provider,model,prompt_version,context_checksum,status,duration_ms,created_at from platform.agent_invocation where task_id=%s order by created_at",(task_id,)).fetchall();tools=c.execute("select tool_name,input_checksum,status,detail,created_at from platform.tool_invocation where task_id=%s order by created_at",(task_id,)).fetchall()
  return {'agents':[ {**dict(r),'created_at':r['created_at'].isoformat()} for r in agents],'tools':[ {**dict(r),'created_at':r['created_at'].isoformat()} for r in tools]}
 def record_harness_invocation(self,task_id,role,provider,model,prompt_version,context_checksum,input_json,output_json,status,duration_ms=None):
  with self.conn() as c:c.execute("insert into platform.agent_invocation(invocation_id,task_id,role,provider,model,prompt_version,context_checksum,input_json,output_json,status,duration_ms) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(uuid.uuid4(),task_id,role,provider,model,prompt_version,context_checksum,json.dumps(input_json,default=str),json.dumps(output_json,default=str) if output_json is not None else None,status,duration_ms))
 def record_tool_invocation(self,task_id,tool_name,input_checksum,status,detail):
  with self.conn() as c:c.execute("insert into platform.tool_invocation(tool_invocation_id,task_id,tool_name,input_checksum,status,detail) values(%s,%s,%s,%s,%s,%s)",(uuid.uuid4(),task_id,tool_name,input_checksum,status,json.dumps(detail,default=str)))
 def managed_sample_table(self,project_id,schema,table):
  with self.conn() as c:r=c.execute("select project_id,schema_name,table_name,task_id,ddl_checksum,row_count,created_at,rebuilt_at from platform.platform_sample_table where project_id=%s and schema_name=%s and table_name=%s",(project_id,schema,table)).fetchone()
  return dict(r) if r else None
 def register_sample_table(self,project_id,task_id,result):
  import hashlib
  ddl_checksum=hashlib.sha256(result['ddl'].encode()).hexdigest()
  with self.conn() as c:
   c.execute("insert into platform.sample_table_definition(definition_id,task_id,schema_name,table_name,fields,sample_rows,ddl) values(%s,%s,%s,%s,%s,%s,%s)",(uuid.uuid4(),task_id,result['schema'],result['table'],json.dumps(result['fields']),json.dumps(result['sample_rows'],default=str),result['ddl']))
   c.execute("insert into platform.platform_sample_table(project_id,schema_name,table_name,task_id,ddl_checksum,row_count,rebuilt_at) values(%s,%s,%s,%s,%s,%s,now()) on conflict(project_id,schema_name,table_name) do update set task_id=excluded.task_id,ddl_checksum=excluded.ddl_checksum,row_count=excluded.row_count,rebuilt_at=now()",(project_id,result['schema'],result['table'],task_id,ddl_checksum,result['row_count']))
  return {**result,'ddl_checksum':ddl_checksum}
 def save_sdm(self,task_id,path,checksum):
  with self.conn() as c:c.execute("insert into platform.sdm_artifact(sdm_id,task_id,file_path,checksum) values(%s,%s,%s,%s)",(uuid.uuid4(),task_id,str(path),checksum))
 def save_release(self,task_id,path,manifest):
  release_id=uuid.uuid4()
  with self.conn() as c:
   c.execute("insert into platform.release(release_id,task_id,status,file_path,manifest) values(%s,%s,'RELEASE_READY',%s,%s)",(release_id,task_id,str(path),json.dumps(manifest)))
   for item in manifest['artifacts']:c.execute("insert into platform.release_artifact(release_id,artifact_name,artifact_type,checksum) values(%s,%s,%s,%s)",(release_id,item['name'],item['type'],item['checksum']))
  return self.release(task_id,release_id)
 def release(self,task_id,release_id=None):
  with self.conn() as c:r=c.execute("select release_id,status,file_path,manifest,created_at from platform.release where task_id=%s "+("and release_id=%s " if release_id else "")+"order by created_at desc limit 1",(task_id,release_id) if release_id else (task_id,)).fetchone()
  if not r:return None
  return {**dict(r),'release_id':str(r['release_id']),'created_at':r['created_at'].isoformat()}
 def save_etl_analysis(self,model,batch_id=None,ai=None):
  analysis_id=uuid.uuid4();process=model['process']
  ai=ai or {}
  with self.conn() as c:
   c.execute("""insert into platform.etl_analysis(
    analysis_id,source_name,source_type,source_relative_path,source_checksum,source_size,source_content,status,
    process_name,process_type,platform_type,node_count,edge_count,source_count,target_count,logic_count,
    canonical_model,summary_text,warning_detail,batch_id,ai_summary,ai_provider,ai_model,ai_usage,column_lineage_count
   ) values(%s,%s,%s,%s,%s,%s,%s,'SUCCEEDED',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(
    analysis_id,Path(process['source_file']).name,Path(process['source_file']).suffix.lstrip('.').upper(),process['source_file'],
    model['checksum'],model['source_size'],model['redacted_source'],process['name'],process['type'],process['platform'],
    len(model['nodes']),len(model['edges']),len(model['sources']),len(model['targets']),len(model['logic']),
    json.dumps({k:v for k,v in model.items() if k!='redacted_source'},ensure_ascii=False),model['summary'],json.dumps(model['warnings'],ensure_ascii=False),
    batch_id,json.dumps(ai.get('summary'),ensure_ascii=False) if ai.get('summary') else None,ai.get('provider'),ai.get('model'),json.dumps(ai.get('usage') or {}),len(model.get('column_lineage') or [])))
  return str(analysis_id)
 def list_etl_analyses(self):
  with self.conn() as c:rows=c.execute("""select analysis_id,source_name,source_type,source_relative_path,status,process_name,process_type,
   platform_type,node_count,edge_count,source_count,target_count,logic_count,column_lineage_count,summary_text,warning_detail,ai_summary,ai_provider,ai_model,batch_id,created_at
   from platform.etl_analysis order by created_at desc limit 100""").fetchall()
  return [{**dict(r),'analysis_id':str(r['analysis_id']),'created_at':r['created_at'].isoformat()} for r in rows]
 def get_etl_analysis(self,analysis_id):
  with self.conn() as c:r=c.execute("select * from platform.etl_analysis where analysis_id=%s",(analysis_id,)).fetchone()
  if not r:return None
  d=dict(r);d['analysis_id']=str(d['analysis_id']);d['created_at']=d['created_at'].isoformat();return d
 def create_etl_batch(self,batch_id,count,provider,task_name=None,source_mode='SCAN'):
  with self.conn() as c:c.execute("insert into platform.etl_analysis_batch(batch_id,requested_count,ai_provider,status,task_name,source_mode) values(%s,%s,%s,'RUNNING',%s,%s)",(batch_id,count,provider,task_name or f'ETL 分析 {str(batch_id)[:8]}',source_mode))
 def queue_etl_batch_items(self,batch_id,paths):
  with self.conn() as c:
   for path in paths:c.execute("insert into platform.etl_analysis_batch_item(batch_item_id,batch_id,source_relative_path,status) values(%s,%s,%s,'QUEUED')",(uuid.uuid4(),batch_id,path))
 def update_etl_batch_item(self,batch_id,path,status,analysis_id=None,error_code=None,error_message=None):
  with self.conn() as c:c.execute("""update platform.etl_analysis_batch_item set status=%s,analysis_id=%s,error_code=%s,error_message=%s
   where batch_item_id=(select batch_item_id from platform.etl_analysis_batch_item where batch_id=%s and source_relative_path=%s order by created_at desc limit 1)""",(status,analysis_id,error_code,error_message,batch_id,path))
 def update_etl_batch_progress(self,batch_id,succeeded,failed):
  with self.conn() as c:c.execute("update platform.etl_analysis_batch set succeeded_count=%s,failed_count=%s where batch_id=%s",(succeeded,failed,batch_id))
 def add_etl_batch_item(self,batch_id,path,status,analysis_id=None,error_code=None,error_message=None):
  with self.conn() as c:c.execute("insert into platform.etl_analysis_batch_item(batch_item_id,batch_id,source_relative_path,status,analysis_id,error_code,error_message) values(%s,%s,%s,%s,%s,%s,%s)",(uuid.uuid4(),batch_id,path,status,analysis_id,error_code,error_message))
 def complete_etl_batch(self,batch_id,succeeded,failed):
  with self.conn() as c:c.execute("update platform.etl_analysis_batch set status=%s,succeeded_count=%s,failed_count=%s,completed_at=now() where batch_id=%s",('FAILED' if failed and not succeeded else 'PARTIAL' if failed else 'SUCCEEDED',succeeded,failed,batch_id))
 def get_etl_batch(self,batch_id):
  with self.conn() as c:
   batch=c.execute("select * from platform.etl_analysis_batch where batch_id=%s",(batch_id,)).fetchone()
   if not batch:return None
   items=c.execute("select source_relative_path path,status,analysis_id,error_code,error_message from platform.etl_analysis_batch_item where batch_id=%s order by created_at,batch_item_id",(batch_id,)).fetchall()
  return {**dict(batch),'batch_id':str(batch['batch_id']),'created_at':batch['created_at'].isoformat(),'completed_at':batch['completed_at'].isoformat() if batch['completed_at'] else None,'items':[{**dict(x),'analysis_id':str(x['analysis_id']) if x['analysis_id'] else None} for x in items]}
 def list_etl_batches(self,limit=100):
  with self.conn() as c:
   batches=c.execute("""select batch_id,task_name,source_mode,requested_count,succeeded_count,failed_count,ai_provider,status,created_at,completed_at
    from platform.etl_analysis_batch order by created_at desc limit %s""",(limit,)).fetchall()
   items=c.execute("""select batch_id,source_relative_path path,status,analysis_id,error_code,error_message,created_at
    from platform.etl_analysis_batch_item
    where batch_id in (select batch_id from platform.etl_analysis_batch order by created_at desc limit %s)
    order by created_at,batch_item_id""",(limit,)).fetchall()
  grouped={str(b['batch_id']):[] for b in batches}
  for item in items:
   row=dict(item);key=str(row.pop('batch_id'));row['analysis_id']=str(row['analysis_id']) if row['analysis_id'] else None;row['created_at']=row['created_at'].isoformat();grouped.setdefault(key,[]).append(row)
  return [{**dict(b),'batch_id':str(b['batch_id']),'created_at':b['created_at'].isoformat(),'completed_at':b['completed_at'].isoformat() if b['completed_at'] else None,'items':grouped.get(str(b['batch_id']),[])} for b in batches]
