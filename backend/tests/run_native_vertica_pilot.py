"""Opt-in real Pilot: persists a unique Project/Task/table and execution evidence.

Run only inside the isolated worker with CONTROL worker stopped. Never drops
tables, overwrites settings, invokes a model, or grants QA/Release success.
"""
import os
from uuid import uuid4, UUID
from decimal import Decimal
from psycopg.types.json import Jsonb
import vertica_python
from app.repository import PostgresRepository
from app.run_queue import RunQueue
from app.control_worker import run_once
from app import task_uploads, specification_store
from app.execution_authorization import offer, authorize
from app.hop_worker import execute_once
from app.vertica_hop_executor import vertica_executor
from app.target_ownership import claim_target
from app.delivery_compiler import compile_delivery_components
from test_etl_specification import design
from oracle_fixture import approved_answer
from app.execution_oracle import load_execution_oracle
from app.comparison_store import list_comparisons, record_execution_comparison
from app.bound_result_query import load_bound_result_query, execute_bound_result_query


def main():
    if os.getenv('WORKBENCH_REAL_VERTICA_PILOT') != '1':
        raise ValueError('EXPLICIT_PILOT_OPT_IN_REQUIRED')
    repo=PostgresRepository(os.environ['DATABASE_URL']);queue=RunQueue(os.environ['DATABASE_URL'])
    crash_probe=os.getenv('WORKBENCH_CRASH_PROBE')=='1'
    if crash_probe:
        from pathlib import Path
        if not list(Path('/opt/hop/lib/jdbc').glob('vertica-jdbc-*.jar')):
            raise ValueError('CRASH_PROBE_VERTICA_DRIVER_REQUIRED')
        # This opt-in probe creates only a new task. Historical NEEDS_REVIEW
        # attempts are left untouched; no queued/running task may be claimed.
        with queue.conn() as conn:
            assert conn.execute("SELECT count(*) n FROM platform.task_run WHERE state IN ('QUEUED','RUNNING')").fetchone()['n']==0
            assert conn.execute("SELECT count(*) n FROM platform.worker_presence WHERE kind='CONTROL' AND activity<>'STOPPED' AND last_seen>clock_timestamp()-interval '45 seconds'").fetchone()['n']==0
    completed=[UUID(value) for value in os.getenv('WORKBENCH_REVIEWED_COMPLETED_RUN','').split(',') if value]
    for identity in completed:
        with queue.conn() as conn:
            prior=conn.execute('SELECT task_id FROM platform.task_run WHERE run_id=%s',(identity,)).fetchone()
        assert prior and prior['task_id'].startswith('native-pilot-')
        load_execution_oracle(queue,prior['task_id'],identity)
        assert any(item['evidence']['status']=='MATCH' for item in list_comparisons(queue,prior['task_id'],identity)['items'])
    with queue.conn() as conn:
        reviewed=[UUID(value) for value in os.getenv('WORKBENCH_REVIEWED_FAILED_RUN','').split(',') if value]
        for identity in reviewed:
            prior=conn.execute('SELECT state,outcome_code,lease_token,task_id FROM platform.task_run WHERE run_id=%s',(identity,)).fetchone()
            assert prior and prior['state']=='NEEDS_REVIEW' and prior['outcome_code']=='HOP_EXECUTION_FAILED' and prior['lease_token'] is None and prior['task_id'].startswith('native-pilot-')
        if not crash_probe:
            assert conn.execute("SELECT count(*) AS n FROM platform.task_run WHERE state IN ('QUEUED','RUNNING','NEEDS_REVIEW') AND NOT (run_id=ANY(%s::uuid[]))",(reviewed+completed,)).fetchone()['n']==0
    connection=repo.setting('data_connections_targets')['etl_qa']
    assert connection['connection_id']=='vertica-default'
    suffix=uuid4().hex
    profile='native-pilot-'+suffix
    repo.upsert_ai_profile(dict(profile_id=profile,display_name='Deterministic native Pilot - no model calls',provider_type='LITELLM_BEDROCK',region='us-east-1',model_routes={role:'bedrock/synthetic' for role in ('requirement_gate','etl_specification','qa_review')}))
    project=repo.create_project(dict(project_name='Native Vertica Pilot '+suffix,default_ai_profile=profile,default_connection=connection['connection_id']))
    task='native-pilot-'+suffix;table='pilot_'+suffix
    print({'task_id':task,'project_id':project['project_id'],'stage':'FIXTURE_CREATION'},flush=True)
    spec, template, naming=design();snapshot=template['input_snapshot']
    upload=task_uploads.save_and_profile('pilot.csv','類別,金額\nA,101.25\nA,200.10\nB,99.00\n'.encode())
    snapshot['source_config']['sources']=[{**upload,'type':'CSV','has_actual_data':True,'fields':snapshot['source_config']['sources'][0]['fields']}]
    snapshot['target_config']['table']=table;spec['target_table']=table
    with queue.conn() as conn:
        conn.execute("INSERT INTO platform.task(task_id,project_id,task_name,task_type,requirement_text,status,source_type,target_type,source_config,target_config) VALUES(%s,%s,'Native Vertica Pilot','NEW',%s,'CREATED','CSV','VERTICA',%s,%s)",(task,project['project_id'],snapshot['requirement_text'],Jsonb(snapshot['source_config']),Jsonb(snapshot['target_config'])))
        conn.execute("INSERT INTO platform.naming_contract(contract_id,task_id,version,status,contract_json,checksum,confirmed_at) VALUES(%s,%s,1,'CONFIRMED',%s,%s,now())",(naming['contract_id'],task,Jsonb(naming['contract_json']),naming['checksum']))
    run=queue.enqueue(task,'native-pilot-once')
    queue.review(task,run['run_id'],run['input_checksum'],run['settings_snapshot']['checksum'],'APPROVE')
    assert run_once(queue)['status']=='CHECKED'
    spec.update(run_id=str(run['run_id']),input_checksum=run['input_checksum'],settings_checksum=run['settings_snapshot']['checksum'])
    with queue.conn() as conn:
        current,naming=specification_store.context(queue,conn,task,run['run_id'])
        compiled=compile_delivery_components(spec,current,naming)
        saved=specification_store.save(queue,conn,task,run['run_id'],compiled)
        specification_store.approve(queue,conn,task,run['run_id'],saved['specification_id'],saved['content_checksum'])
    sid=saved['specification_id']
    approved_answer(queue,task,run['run_id'],sid,rows=[{'category':'A','total_amount':'301.35','row_count':2}])
    cfg={key:connection[key] for key in ('host','port','database','user','tlsmode')}
    cfg.update(password=repo.read_secret_at_version('connection:'+connection['connection_id'],run['settings_snapshot']['credential_versions']['connection']),connection_timeout=10)
    with vertica_python.connect(**cfg) as db:
        cursor=db.cursor();cursor.execute('CREATE SCHEMA IF NOT EXISTS ai_sample')
        cursor.execute(compiled['ddl']);db.commit()
    with queue.conn() as conn:
        conn.execute('INSERT INTO platform.platform_sample_table(project_id,schema_name,table_name,task_id,ddl_checksum,row_count) VALUES(%s,%s,%s,%s,%s,0)',(project['project_id'],'ai_sample',table,task,compiled['ddl_checksum']))
    claim_target(queue,task,run['run_id'],sid)
    with queue.conn() as conn:
        consent_offer=offer(queue,conn,task,run['run_id'],sid)
    consent=authorize(queue,task,run['run_id'],sid,consent_offer['binding_checksum'],True)
    executor=vertica_executor(repo,run['settings_snapshot'])
    if crash_probe:
        from threading import Event
        import json
        actual=executor
        def executor(prepared,lost,log_sink):
            result=actual(prepared,lost,log_sink)
            if result['status']!='COMPLETED':
                return result  # Keep real failure evidence; no forced UNKNOWN.
            print(json.dumps({'stage':'HOP_FINISHED_BEFORE_ACK','task_id':task,
                'project_id':str(project['project_id']),'run_id':str(run['run_id']),
                'specification_id':str(sid),'authorization_id':str(consent['authorization_id']),
                'table':table,'log_checksum':result['log_checksum']}),flush=True)
            # Test supervisor must kill this exact container. Timing out records
            # UNKNOWN through the normal worker; never silently retries.
            Event().wait(300)
            raise RuntimeError('CRASH_PROBE_NOT_INTERRUPTED')
        executor.preflight=actual.preflight
    result=execute_once(queue,task,run['run_id'],sid,UUID(consent['authorization_id']),executor)
    print({'task_id':task,'run_id':str(run['run_id']),'outcome':result['status'],'qa_passed':False,'release_ready':False},flush=True)
    assert result['status']=='HOP_EXECUTED_QA_REQUIRED'
    query,pin=load_bound_result_query(queue,task,run['run_id'])
    with vertica_python.connect(**cfg) as db:
        cursor=db.cursor();execute_bound_result_query(cursor,query,pin)
        assert cursor.fetchall()==[['A',Decimal('301.35'),2]]
        execute_bound_result_query(cursor,query,pin)
        comparison=record_execution_comparison(queue,task,run['run_id'],cursor)
        assert comparison['evidence']['status']=='MATCH'
        print({'comparison_id':comparison['comparison_id'],'query_checksum':query['checksum']},flush=True)
    print('REAL_HOP_VERTICA_ROWS_MATCHED_NOT_RELEASED',flush=True)


if __name__=='__main__':
    try: main()
    except Exception as error:
        print('NATIVE_PILOT_STOPPED '+type(error).__name__,flush=True)
        raise SystemExit(1)
