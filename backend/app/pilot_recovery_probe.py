"""Opt-in, single-attempt frozen-cohort fault probe. Never a repair API."""
import argparse
from contextlib import contextmanager
import json
import os

import vertica_python

from .hop_connection_runtime import connection_runtime
from .hop_dispatch import claim, offer, finish
from .hop_worker import execute_once
from .pilot_hop_worker import prepare_new_target
from .pilot_recovery_scope import check_scope
from .repository import PostgresRepository
from .run_queue import RunQueue
from .sa_contract import digest
from .target_ownership import lock_target
from .vertica_hop_executor import vertica_executor


def enrolled_scope(conn, current, task_id, binding):
    rows = conn.execute('''SELECT c.definition,p.project_id FROM platform.pilot_case_task b
        JOIN platform.pilot_cohort_case c USING(cohort_id,case_key)
        JOIN platform.pilot_cohort p USING(cohort_id) WHERE b.task_id=%s''',
        (task_id,)).fetchall()
    if len(rows) != 1 or str(rows[0]['project_id']) != str(current['run']['project_id']):
        raise ValueError('RECOVERY_ENROLLMENT_REQUIRED')
    return check_scope(current, binding, rows[0]['definition'])


@contextmanager
def database(repo, snapshot):
    with connection_runtime(repo, snapshot, snapshot['checksum']) as runtime:
        config = {k: snapshot['connection'][k] for k in ('host','port','database','user','tlsmode')}
        config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'], connection_timeout=10)
        try:
            with vertica_python.connect(**config) as db:
                yield db
        finally:
            config.clear()


def observe(db, table):
    cur = db.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "ai_sample"."{table}"')
    count = cur.fetchone()[0]
    cur.execute('''SELECT column_name FROM v_catalog.columns
        WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position''', ('ai_sample',table))
    return count, [r[0] for r in cur.fetchall()]


def run(queue, repo, task_id, run_id, binding):
    if os.getenv('WORKBENCH_SYNTHETIC_FAILURE_PROBE') != 'frozen-cohort-missing-column-v1':
        raise ValueError('EXPLICIT_RECOVERY_PROBE_REQUIRED')
    with queue.conn() as conn:
        queue.locked_task(conn, task_id)
        row = conn.execute('''SELECT specification_id FROM platform.hop_dispatch_request
            WHERE run_id=%s AND status='QUEUED' ''', (run_id,)).fetchone()
        if not row:
            raise ValueError('QUEUED_AUTHORIZED_REQUEST_REQUIRED')
        enrolled_scope(conn, offer(queue,conn,task_id,run_id,row['specification_id']), task_id,binding)
    request = claim(queue,task_id,run_id)
    if not request:
        raise ValueError('RECOVERY_ALREADY_CLAIMED')
    try:
        snapshot = prepare_new_target(queue,repo,request)
        with queue.conn() as conn:
            queue.locked_task(conn,task_id)
            current = offer(queue,conn,task_id,run_id,request['specification_id'])
            scope = enrolled_scope(conn,current,task_id,binding)
            table, column, renamed = scope['table'], scope['column'], scope['renamed_to']
            lock_target(conn,'ai_sample',table)
            registry = conn.execute('''SELECT * FROM platform.platform_sample_table
                WHERE schema_name='ai_sample' AND table_name=%s FOR SHARE''',(table,)).fetchone()
            owner = conn.execute('''SELECT run_id FROM platform.task_run_target_claim
                WHERE schema_name='ai_sample' AND table_name=%s FOR SHARE''',(table,)).fetchone()
            if (not registry or str(registry['project_id']) != str(current['run']['project_id'])
                    or registry['task_id'] != task_id
                    or registry['ddl_checksum'] != current['binding']['ddl_checksum']
                    or not owner or str(owner['run_id']) != str(run_id)):
                raise ValueError('RECOVERY_TARGET_OWNERSHIP_INVALID')
            with database(repo,snapshot) as db:
                count, columns = observe(db,table)
                if count != 0 or columns != scope['columns']:
                    raise ValueError('RECOVERY_NEW_EMPTY_TARGET_REQUIRED')
                cur = db.cursor()
                cur.execute('SELECT VERSION()')
                version = cur.fetchone()[0]
                cur.execute(f'ALTER TABLE "ai_sample"."{table}" RENAME COLUMN "{column}" TO "{renamed}"')
                db.commit()
            queue.event(conn,run_id,'SYNTHETIC_MISSING_COLUMN_INJECTED','HOP_PREPARATION',
                {'version':1,'case_key':scope['case_key'],'column':column,'renamed_to':renamed,
                 'rows_before':0,'engine_version':version,'binding_checksum':binding,
                 'original_hpl_unchanged':True})
        result = execute_once(queue,task_id,run_id,request['specification_id'],
                              request['authorization_id'],vertica_executor(repo,snapshot))
        with database(repo,snapshot) as db:
            count, columns = observe(db,table)
        terminal = result['status'] in ('HOP_EXECUTION_FAILED','HOP_EXECUTED_QA_REQUIRED')
        evidence = dict(version=1,run_id=str(run_id),outcome=result['status'],
                        observed_row_count=count,columns=columns,engine_stopped=terminal,
                        automatic_retry_allowed=False)
        with queue.conn() as conn:
            queue.event(conn,run_id,'SYNTHETIC_FAILURE_TARGET_OBSERVED','HOP_EXECUTION',
                        {**evidence,'checksum':digest(evidence)})
        return {**evidence,'checksum':digest(evidence),
                'expected_failure_observed':result['status']=='HOP_EXECUTION_FAILED' and count==0}
    finally:
        finish(queue,request,'NEEDS_REVIEW','RECOVERY_PROBE_REQUIRES_EVIDENCE_REVIEW')


def main():
    parser = argparse.ArgumentParser()
    for name in ('task-id','run-id','binding-checksum'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(RunQueue(os.environ['DATABASE_URL']),
            PostgresRepository(os.environ['DATABASE_URL']),args.task_id,args.run_id,args.binding_checksum)))
    except Exception:
        raise SystemExit('RECOVERY_PROBE_STOPPED_REVIEW_EVIDENCE_NO_RETRY') from None


if __name__ == '__main__':
    main()
