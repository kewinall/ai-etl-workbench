"""Consume website Hop requests once. No retry, DROP, model or release permission."""
import argparse
import os
import signal
from threading import Event
import vertica_python
from .run_queue import RunQueue
from .repository import PostgresRepository
from .hop_dispatch import claim, offer, finish
from .hop_connection_runtime import connection_runtime
from .target_ownership import lock_target, claim_target
from .hop_worker import execute_once
from .vertica_hop_executor import vertica_executor
from .bound_comparison import record_bound_comparison


def prepare_new_target(queue,repo,request):
    if os.getenv('WORKBENCH_EXECUTION_ENABLED')!='true':raise ValueError('EXECUTION_DISABLED')
    # Holding the Task/target locks prevents another platform operation from
    # changing the source/target binding during DDL. No existing table is reused.
    with queue.conn() as conn:
        current=offer(queue,conn,request['task_id'],request['run_id'],request['specification_id'])
        if current['binding_checksum']!=request['binding_checksum']:raise ValueError('HOP_DISPATCH_BINDING_CHANGED')
        active=conn.execute("SELECT 1 FROM platform.hop_dispatch_request WHERE request_id=%s AND claim_token=%s AND status='CLAIMED'",(request['request_id'],request['claim_token'])).fetchone()
        if not active:raise ValueError('HOP_DISPATCH_CLAIM_LOST')
        consent=conn.execute('''SELECT binding_checksum FROM platform.task_run_execution_authorization
            WHERE authorization_id=%s AND run_id=%s AND specification_id=%s AND expires_at>clock_timestamp()''',
            (request['authorization_id'],request['run_id'],request['specification_id'])).fetchone()
        if not consent or consent['binding_checksum']!=current['binding']['execution_binding_checksum']:
            raise ValueError('EXECUTION_AUTHORIZATION_MISSING_OR_EXPIRED')
        spec=current['specification'];snapshot=current['run']['settings_snapshot']
        lock_target(conn,spec['target_schema'],spec['target_table'])
        if conn.execute('SELECT 1 FROM platform.platform_sample_table WHERE schema_name=%s AND table_name=%s',(spec['target_schema'],spec['target_table'])).fetchone():
            raise ValueError('PILOT_NEW_TARGET_REQUIRED')
        with connection_runtime(repo,snapshot,snapshot['checksum']) as runtime:
            config={key:snapshot['connection'][key] for key in ('host','port','database','user','tlsmode')}
            config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
            try:
                with vertica_python.connect(**config) as db:
                    cursor=db.cursor()
                    cursor.execute('SELECT 1 FROM v_catalog.tables WHERE table_schema=%s AND table_name=%s',(spec['target_schema'],spec['target_table']))
                    if cursor.fetchone() is not None:raise ValueError('PILOT_NEW_TARGET_REQUIRED')
                    cursor.execute('CREATE SCHEMA IF NOT EXISTS ai_sample')
                    # Compiler bytes only; CREATE fails on any concurrent external table.
                    cursor.execute(current['ddl']);db.commit()
            finally:config.clear()
        conn.execute('''INSERT INTO platform.platform_sample_table
            (project_id,schema_name,table_name,task_id,ddl_checksum,row_count) VALUES(%s,%s,%s,%s,%s,0)''',
            (current['run']['project_id'],spec['target_schema'],spec['target_table'],request['task_id'],current['binding']['ddl_checksum']))
        queue.event(conn,request['run_id'],'PILOT_NEW_TARGET_CREATED','HOP_PREPARATION',
            {'request_id':str(request['request_id']),'ddl_checksum':current['binding']['ddl_checksum'],'drop_allowed':False})
    claim_target(queue,request['task_id'],request['run_id'],request['specification_id'])
    return snapshot


def run_once(queue,repo,task_id=None,run_id=None):
    request=claim(queue,task_id,run_id)
    if not request:return {'status':'IDLE'}
    status='NEEDS_REVIEW';code='HOP_PREPARATION_OR_COMPARISON_FAILED'
    try:
        snapshot=prepare_new_target(queue,repo,request)
        result=execute_once(queue,request['task_id'],request['run_id'],request['specification_id'],
            request['authorization_id'],vertica_executor(repo,snapshot))
        if result['status']=='HOP_EXECUTED_QA_REQUIRED':
            record_bound_comparison(queue,repo,request['task_id'],request['run_id'])
            status='COMPLETED';code='HOP_EXECUTED_QA_REQUIRED'
        else:code='HOP_FAILED_OR_UNKNOWN'
    except Exception:
        # Do not remove tables or retry after possible DDL/data side effects.
        pass
    finish(queue,request,status,code)
    return {'status':status,'run_id':str(request['run_id']),'outcome_code':code,'release_ready':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true')
    parser.add_argument('--task-id');parser.add_argument('--run-id');args=parser.parse_args()
    if os.getenv('WORKBENCH_EXECUTION_ENABLED')!='true':raise SystemExit('EXECUTION_DISABLED')
    queue=RunQueue(os.environ['DATABASE_URL']);repo=PostgresRepository(os.environ['DATABASE_URL']);stop=Event()
    for name in (signal.SIGTERM,signal.SIGINT):signal.signal(name,lambda *_:stop.set())
    while not stop.is_set():
        try:
            result=run_once(queue,repo,args.task_id,args.run_id)
            if result['status']!='IDLE' or args.once:print(result,flush=True)
        except Exception:print('HOP_DISPATCH_STORE_UNAVAILABLE_NO_RETRY',flush=True)
        if args.once:return
        stop.wait(3)


if __name__=='__main__':main()
