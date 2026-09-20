"""Owns the actual read connection and query; no public SQL/cursor injection."""
import vertica_python
from hashlib import sha256
from .bound_result_query import load_bound_result_query, execute_bound_result_query
from .comparison_store import record_execution_comparison
from .execution_oracle import load_execution_oracle
from .hop_connection_runtime import connection_runtime
from .target_ownership import check_target_claim
from .target_preflight import empty_target_sql


def capture_binding(queue,repo,task_id,run_id):
    query,pin=load_bound_result_query(queue,task_id,run_id)
    with queue.conn() as conn:
        run=conn.execute('SELECT settings_snapshot FROM platform.task_run WHERE run_id=%s AND task_id=%s',(run_id,task_id)).fetchone()
        auth=conn.execute('SELECT binding FROM platform.task_run_execution_authorization WHERE run_id=%s',(run_id,)).fetchone()
        empty=conn.execute('SELECT * FROM platform.task_run_target_empty_check WHERE run_id=%s',(run_id,)).fetchone()
        writes=conn.execute("SELECT created_at FROM platform.task_run_event WHERE run_id=%s AND event_type='WRITE_STARTED' ORDER BY event_id",(run_id,)).fetchall()
    if not run or not auth or not empty or len(writes)!=1:
        raise ValueError('RESULT_TARGET_PROVENANCE_REQUIRED')
    binding=auth['binding']
    claim=check_target_claim(repo,binding)
    if (claim['task_id']!=task_id or claim['created_at']>empty['created_at']
            or empty['created_at']>writes[0]['created_at']
            or empty['task_id']!=claim['task_id'] or empty['project_id']!=claim['project_id']
            or empty['sql_checksum']!=sha256(empty_target_sql(claim).encode()).hexdigest()
            or empty['settings_checksum']!=binding['settings_checksum']
            or empty['hpl_checksum']!=binding['hpl_checksum']):
        raise ValueError('RESULT_TARGET_PROVENANCE_CHANGED')
    return query,pin,run['settings_snapshot'],empty['created_at']


def record_bound_comparison(queue,repo,task_id,run_id):
    query,pin,snapshot,empty_at=capture_binding(queue,repo,task_id,run_id)
    with connection_runtime(repo,snapshot,query['plan']['settings_checksum']) as runtime:
        config={key:snapshot['connection'][key] for key in ('host','port','database','user','tlsmode')}
        config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
        try:
            with vertica_python.connect(**config) as db:
                cursor=db.cursor()
                execute_bound_result_query(cursor,query,pin)
                result=record_execution_comparison(queue,task_id,run_id,cursor)
        finally:
            config.clear()
    # A changed upstream cannot promote the saved unverified comparison.
    query_after,pin_after,snapshot_after,empty_after=capture_binding(queue,repo,task_id,run_id)
    if (query_after!=query or pin_after!=pin or snapshot_after!=snapshot or empty_after!=empty_at):
        raise ValueError('RESULT_TARGET_PROVENANCE_CHANGED')
    with queue.conn() as conn:
        current=load_execution_oracle(queue,task_id,run_id,connection=conn)
        if current!=pin:raise ValueError('RESULT_TARGET_PROVENANCE_CHANGED')
        values=(result['comparison_id'],run_id,result['checksum'],query['checksum'],snapshot['checksum'],empty_at,pin['hop_event_id'])
        row=conn.execute('''INSERT INTO platform.result_comparison_provenance
            (comparison_id,run_id,comparison_checksum,query_checksum,settings_checksum,empty_checked_at,hop_event_id)
            VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING comparison_id''',values).fetchone()
        if row:
            queue.event(conn,run_id,'RESULT_SOURCE_BOUND','QA_PREPARATION',
                {'comparison_id':result['comparison_id'],'query_checksum':query['checksum'],
                 'scope':'PLATFORM_MANAGED_TARGET','qa_passed':False,'release_ready':False})
    return {**result,'source_status':'BOUND_PLATFORM_TARGET','qa_passed':False,'release_ready':False}
