"""Dedicated DB only: actual execute_once owner loss after a real Hop partial commit.

Synthetic specification/oracle, no AI invocation and no QA/Release grant. The
external supervisor must kill this entire named worker container, not just its
Python PID; Hop is a child in a separate process group. Never use a formal DB.
"""
import base64
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
import vertica_python
from app.repository import PostgresRepository
from app.run_queue import RunQueue, RunConflict
from app.control_worker import run_once
from app import task_uploads, specification_store
from app.platform_harness import encrypt_secret
from app.delivery_compiler import compile_delivery_components
from app.execution_authorization import offer, authorize
from app.execution_reservation import reserve
from app.hop_worker import execute_once
from app.hop_connection_runtime import connection_runtime
from app.target_ownership import claim_target, check_target_claim
from app.target_preflight import verify_empty_target
from test_source_order_compilation import ordered_design
from oracle_fixture import approved_answer

ROOT = Path('/app/runtime-temp')
STATE = ROOT/'partial-worker.json'


def config():
    return dict(host='portability-vertica', port=5433, database='WorkbenchPortable', user='dbadmin',
                tlsmode='disable', connection_timeout=10,
                password=Path('/run/portability-secrets/password').read_text().strip())


def counts(table):
    assert re.fullmatch(r'worker_interrupt_[a-f0-9]{32}', table)
    with vertica_python.connect(**config()) as db:
        cursor = db.cursor()
        cursor.execute(f'SELECT COUNT(*),COUNT(DISTINCT source_position),MIN(source_position),MAX(source_position),SUM(source_position) FROM "ai_sample"."{table}"')
        return list(cursor.fetchone())


def seed(repo, queue):
    assert not STATE.exists(), 'Fresh runtime volume required'
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) n FROM platform.task_run').fetchone()['n'] == 0
    key = ROOT/'partial-test.key'
    descriptor = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(base64.urlsafe_b64encode(os.urandom(32)).decode())
    os.environ['PLATFORM_SETTINGS_ENCRYPTION_KEY'] = key.read_text()
    connection = {key: value for key,value in config().items() if key not in ('password','connection_timeout')}
    connection.update(type='VERTICA', connection_id='partial-test')
    settings = repo.setting('data_connections_targets')
    repo.update_setting('data_connections_targets', {**settings,'etl_qa':connection})
    repo.save_secret('connection:partial-test', *encrypt_secret(config()['password']))
    suffix = uuid4().hex
    profile = 'partial-test-' + suffix
    repo.upsert_ai_profile(dict(profile_id=profile, display_name='Synthetic failure test - no model calls',
        provider_type='LITELLM_BEDROCK',region='us-east-1',model_routes={r:'bedrock/synthetic' for r in ('requirement_gate','etl_specification','qa_review')}))
    project = repo.create_project(dict(project_name='Isolated partial write test',default_ai_profile=profile,default_connection='partial-test'))
    task, table = 'partial-worker-' + suffix, 'worker_interrupt_' + suffix
    spec, template, naming = ordered_design()
    snapshot = template['input_snapshot']
    snapshot['requirement_text'] = '保留全部資料及來源順序，輸出 category、amount、source_position；不篩選不彙總。'
    content = '類別,金額\n' + ''.join(f'R{i:04d},1.00\n' for i in range(1,2001))
    upload = task_uploads.save_and_profile('partial.csv', content.encode())
    snapshot['source_config']['sources'] = [{**upload,'type':'CSV','has_actual_data':True,
        'fields':snapshot['source_config']['sources'][0]['fields']}]
    snapshot['target_config']['table'] = table
    spec['target_table'] = table
    with queue.conn() as conn:
        conn.execute("INSERT INTO platform.task(task_id,project_id,task_name,task_type,requirement_text,status,source_type,target_type,source_config,target_config) VALUES(%s,%s,'Partial worker loss','NEW',%s,'CREATED','CSV','VERTICA',%s,%s)",
            (task,project['project_id'],snapshot['requirement_text'],Jsonb(snapshot['source_config']),Jsonb(snapshot['target_config'])))
        conn.execute("INSERT INTO platform.naming_contract(contract_id,task_id,version,status,contract_json,checksum,confirmed_at) VALUES(%s,%s,1,'CONFIRMED',%s,%s,now())",
            (naming['contract_id'],task,Jsonb(naming['contract_json']),naming['checksum']))
    run = queue.enqueue(task,'partial-worker-once')
    queue.review(task,run['run_id'],run['input_checksum'],run['settings_snapshot']['checksum'],'APPROVE')
    assert run_once(queue)['status'] == 'CHECKED'
    spec.update(run_id=str(run['run_id']),input_checksum=run['input_checksum'],settings_checksum=run['settings_snapshot']['checksum'])
    with queue.conn() as conn:
        current,naming = specification_store.context(queue,conn,task,run['run_id'])
        compiled = compile_delivery_components(spec,current,naming)
        saved = specification_store.save(queue,conn,task,run['run_id'],compiled)
        specification_store.approve(queue,conn,task,run['run_id'],saved['specification_id'],saved['content_checksum'])
    sid = saved['specification_id']
    approved_answer(queue,task,run['run_id'],sid,rows=[{'category':f'R{i:04d}','amount':'1.00','source_position':i} for i in range(1,2001)])
    with vertica_python.connect(**config()) as db:
        cursor=db.cursor()
        cursor.execute('CREATE SCHEMA IF NOT EXISTS ai_sample')
        cursor.execute(compiled['ddl'])
    with queue.conn() as conn:
        conn.execute('INSERT INTO platform.platform_sample_table(project_id,schema_name,table_name,task_id,ddl_checksum,row_count) VALUES(%s,%s,%s,%s,%s,0)',
            (project['project_id'],'ai_sample',table,task,compiled['ddl_checksum']))
    claim_target(queue,task,run['run_id'],sid)
    with queue.conn() as conn:
        current = offer(queue,conn,task,run['run_id'],sid)
    consent = authorize(queue,task,run['run_id'],sid,current['binding_checksum'],True)
    data = dict(task_id=task,run_id=str(run['run_id']),specification_id=str(sid),
                authorization_id=consent['authorization_id'],table=table)
    STATE.write_text(json.dumps(data))
    return run,data


def serve(repo,queue):
    run,data=seed(repo,queue)
    def executor(prepared,lost,log_sink):
        check_target_claim(repo,prepared['binding'])
        data['binding']=prepared['binding']
        STATE.write_text(json.dumps(data))
        with connection_runtime(repo,run['settings_snapshot'],run['settings_snapshot']['checksum']) as runtime:
            with (prepared['directory']/'metadata.json').open('x') as stream:
                stream.write(runtime['metadata'])
            environment = {key:os.environ[key] for key in ('PATH','HOME','HOP_HOME','LANG') if key in os.environ}
            environment.update(runtime['environment'],WORKBENCH_PARTIAL_WRITE_PROBE='dedicated-portability-database-v1')
            log = (ROOT/'partial-hop.log').open('xb')
            child = subprocess.Popen(['java','-cp','lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*:lib/jdbc/vertica-jdbc.jar',
                '/validation/ExecutePartialWriteProbe.java',str(prepared['directory']),str(prepared['source_path'])],
                cwd='/opt/hop',env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                deadline=time.monotonic()+45
                while time.monotonic()<deadline and child.poll() is None and not lost.is_set():
                    if (prepared['directory']/'partial-ready').exists() and counts(data['table'])==[1000,1000,1,1000,500500]:
                        detail=queue.detail(data['task_id'],data['run_id'])
                        assert detail['write_started'] and detail['state']=='RUNNING'
                        print('PARTIAL_COMMITTED_OWNER_ALIVE_WAITING_FOR_CONTAINER_KILL',flush=True)
                        # The external supervisor must kill the whole container here.
                        lost.wait(180)
                        raise ValueError('Supervisor did not kill the owner within the test window')
                    time.sleep(.1)
                raise ValueError('No partial commit observed')
            finally:
                if child.poll() is None:
                    os.killpg(child.pid,signal.SIGKILL)
                    child.wait(timeout=10)
                log.close()
                environment.clear()
    executor.preflight=lambda prepared:verify_empty_target(repo,prepared['binding'],run['settings_snapshot'])
    execute_once(queue,data['task_id'],UUID(data['run_id']),UUID(data['specification_id']),UUID(data['authorization_id']),executor)
    raise ValueError('Owner was not killed; this is not a successful process-loss test')


def recover(repo,queue):
    data=json.loads(STATE.read_text())
    os.environ['PLATFORM_SETTINGS_ENCRYPTION_KEY']=(ROOT/'partial-test.key').read_text()
    old=queue.detail(data['task_id'],data['run_id'])
    assert old['state']=='RUNNING' and old['write_started'] and old['lease_token']
    assert counts(data['table'])==[1000,1000,1,1000,500500]
    deadline=time.monotonic()+80
    while not queue.reap_expired():
        assert time.monotonic()<deadline, 'Natural lease expiry not observed'
        time.sleep(1)
    assert queue.reap_expired()==0 and queue.claim() is None and queue.claim() is None
    final=queue.detail(data['task_id'],data['run_id'])
    assert final['state']=='NEEDS_REVIEW' and final['outcome_code']=='HOP_RESULT_UNKNOWN' and final['lease_token'] is None
    assert sum(e['event_type']=='LEASE_EXPIRED_NEEDS_REVIEW' for e in final['events'])==1
    assert final['events'][-1]['event_context']['automatic_retry_allowed'] is False
    try:
        reserve(queue,data['task_id'],UUID(data['run_id']),UUID(data['specification_id']),UUID(data['authorization_id']),data['binding'])
    except RunConflict as error:
        assert str(error)=='EXECUTION_AUTHORIZATION_CONSUMED'
    else:
        raise AssertionError('Consumed authorization was reused')
    try:
        queue.enqueue(data['task_id'],'partial-worker-new-key')
    except RunConflict as error:
        assert str(error)=='ACTIVE_RUN_EXISTS'
    else:
        raise AssertionError('A duplicate run was created')
    assert str(queue.enqueue(data['task_id'],'partial-worker-once')['run_id'])==data['run_id']
    try:
        queue.finish(data['run_id'],old['lease_token'],'SUCCEEDED')
    except RunConflict:
        pass
    else:
        raise AssertionError('Dead owner published success')
    assert counts(data['table'])==[1000,1000,1,1000,500500]
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) n FROM platform.release_delivery').fetchone()['n']==0
        assert conn.execute('SELECT count(*) n FROM platform.agent_invocation').fetchone()['n']==0
    result=dict(status='PASS',scope='SYNTHETIC_SPEC_REAL_EXECUTE_ONCE_OWNER_LOSS',persisted_rows=1000,
                run_state=final['state'],outcome=final['outcome_code'],automatic_retry=False,
                consumed_authorization_rejected=True,duplicate_run_rejected=True,release_ready=False,model_calls=0)
    with (ROOT/'partial-recovery.json').open('x') as stream:
        json.dump(result,stream)
    print(json.dumps(result),flush=True)


def main():
    from urllib.parse import urlparse
    name=os.getenv('DATABASE_NAME','')
    if (os.getenv('WORKBENCH_PARTIAL_WORKER_TEST')!='dedicated-new-database'
            or not re.fullmatch(r'partial_loss_probe(?:_[a-z0-9]+)?',name)
            or urlparse(os.getenv('DATABASE_URL','')).hostname!='partial-loss-postgres'):
        raise ValueError('Dedicated database opt-in required')
    repo=PostgresRepository(os.environ['DATABASE_URL']);queue=RunQueue(repo.url)
    with queue.conn() as conn:
        assert conn.execute('SELECT current_database() n').fetchone()['n']==name
    if sys.argv[1:] == ['serve']:
        serve(repo,queue)
    elif sys.argv[1:] == ['recover']:
        recover(repo,queue)
    else:
        raise ValueError('serve or recover required')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        import traceback
        locations=[{'function':frame.name,'line':frame.lineno} for frame in traceback.extract_tb(error.__traceback__)]
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__,'locations':locations,
                          'detail':'Retain isolated DB/runtime; no automatic retry or cleanup'}),flush=True)
        raise SystemExit(1)
