"""Explicit synthetic missing-column acceptance, never a general repair API.

Claim one authorized request; create its new empty registered target normally,
rename one empty synthetic column, execute unchanged compiled Hop once. Retain
the table and failed evidence. No DROP, retry, auto-repair or release authority.
"""
import argparse
from hashlib import sha256
import json
import os
import re
import vertica_python
from .run_queue import RunQueue
from .repository import PostgresRepository
from .hop_dispatch import claim,offer,finish
from .pilot_hop_worker import prepare_new_target
from .hop_connection_runtime import connection_runtime
from .hop_worker import execute_once
from .vertica_hop_executor import vertica_executor
from .sa_contract import digest

SYNTHETIC_CSV=b'record_key,label\nA,alpha\nB,beta\n'


def check_scope(current,binding_checksum):
    spec=current['specification'];run=current['run']
    source=run['input_snapshot']['source_config']['sources']
    if (current['binding_checksum']!=binding_checksum or run['write_started'] or run.get('parent_run_id')
            or spec['version']!=1 or spec['target_schema']!='ai_sample'
            or not re.fullmatch(r'pilot_missing_column_[0-9]{8}',spec['target_table'])
            or spec['output_columns']!=['record_key','label'] or spec['filters'] or spec['aggregation'] is not None
            or spec['write_mode']!='APPEND' or len(source)!=1
            or source[0].get('checksum')!=sha256(SYNTHETIC_CSV).hexdigest()):
        raise ValueError('FAILURE_PROBE_SCOPE_INVALID')
    return spec['target_table']


def run(queue,repo,task_id,run_id,binding_checksum):
    if os.getenv('WORKBENCH_SYNTHETIC_FAILURE_PROBE')!='missing-column-v1':
        raise ValueError('EXPLICIT_FAILURE_PROBE_REQUIRED')
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        row=conn.execute('SELECT specification_id FROM platform.hop_dispatch_request WHERE run_id=%s AND status=\'QUEUED\'',(run_id,)).fetchone()
        if not row:raise ValueError('QUEUED_AUTHORIZED_REQUEST_REQUIRED')
        check_scope(offer(queue,conn,task_id,run_id,row['specification_id']),binding_checksum)
    request=claim(queue,task_id,run_id)
    if not request:raise ValueError('FAILURE_PROBE_ALREADY_CLAIMED')
    code='HOP_PREPARATION_OR_COMPARISON_FAILED'
    try:
        snapshot=prepare_new_target(queue,repo,request)
        with queue.conn() as conn:
            queue.locked_task(conn,task_id)
            current=offer(queue,conn,task_id,run_id,request['specification_id'])
            table=check_scope(current,binding_checksum)
            registered=conn.execute('SELECT * FROM platform.platform_sample_table WHERE schema_name=\'ai_sample\' AND table_name=%s',(table,)).fetchone()
            if (not registered or str(registered['project_id'])!=str(current['run']['project_id'])
                    or registered['task_id']!=task_id):raise ValueError('FAILURE_PROBE_OWNERSHIP_INVALID')
            with connection_runtime(repo,snapshot,snapshot['checksum']) as runtime:
                config={k:snapshot['connection'][k] for k in ('host','port','database','user','tlsmode')}
                config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
                try:
                    with vertica_python.connect(**config) as db:
                        cur=db.cursor();cur.execute(f'SELECT COUNT(*) FROM "ai_sample"."{table}"')
                        if cur.fetchone()[0]!=0:raise ValueError('FAILURE_PROBE_TARGET_NOT_EMPTY')
                        cur.execute('SELECT column_name FROM v_catalog.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',('ai_sample',table))
                        if [r[0] for r in cur.fetchall()]!=['record_key','label']:raise ValueError('FAILURE_PROBE_COLUMNS_CHANGED')
                        cur.execute('SELECT VERSION()');version=cur.fetchone()[0]
                        cur.execute(f'ALTER TABLE "ai_sample"."{table}" RENAME COLUMN "label" TO "label_missing_fault"')
                        db.commit()
                finally:config.clear()
            queue.event(conn,run_id,'SYNTHETIC_MISSING_COLUMN_INJECTED','HOP_PREPARATION',
                {'version':1,'column':'label','renamed_to':'label_missing_fault','rows_before':0,
                 'engine_version':version,'binding_checksum':binding_checksum,'original_hpl_unchanged':True})
        result=execute_once(queue,task_id,run_id,request['specification_id'],request['authorization_id'],vertica_executor(repo,snapshot))
        code='HOP_FAILED_OR_UNKNOWN'
        with connection_runtime(repo,snapshot,snapshot['checksum']) as runtime:
            config={k:snapshot['connection'][k] for k in ('host','port','database','user','tlsmode')}
            config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
            try:
                # Fresh session records persistent state, not a presumed rollback.
                with vertica_python.connect(**config) as db:
                    cur=db.cursor();cur.execute(f'SELECT COUNT(*) FROM "ai_sample"."{table}"');count=cur.fetchone()[0]
                    cur.execute('SELECT column_name FROM v_catalog.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',('ai_sample',table))
                    columns=[r[0] for r in cur.fetchall()]
            finally:config.clear()
        evidence=dict(version=1,run_id=str(run_id),outcome=result['status'],observed_row_count=count,
                      columns=columns,engine_stopped=True,automatic_retry_allowed=False)
        with queue.conn() as conn:queue.event(conn,run_id,'SYNTHETIC_FAILURE_TARGET_OBSERVED','HOP_EXECUTION',{**evidence,'checksum':digest(evidence)})
        return {**evidence,'checksum':digest(evidence),'expected_failure_observed':result['status']=='HOP_EXECUTION_FAILED' and count==0}
    finally:finish(queue,request,'NEEDS_REVIEW',code)


def main():
    p=argparse.ArgumentParser();p.add_argument('--task-id',required=True);p.add_argument('--run-id',required=True);p.add_argument('--binding-checksum',required=True)
    a=p.parse_args()
    try:print(json.dumps(run(RunQueue(os.environ['DATABASE_URL']),PostgresRepository(os.environ['DATABASE_URL']),a.task_id,a.run_id,a.binding_checksum)),flush=True)
    except Exception:raise SystemExit('FAILURE_PROBE_STOPPED_CHECK_SAVED_EVIDENCE_NO_RETRY') from None


if __name__=='__main__':main()
