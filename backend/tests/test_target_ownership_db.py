"""Real PostgreSQL constraints; all synthetic rows are rolled back, no ETL."""
import os
from uuid import uuid4
import psycopg
import pytest
from app.run_queue import RunQueue

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS')!='1',reason='Isolated PostgreSQL required')


def test_unique_immutable_prewrite_target_claim():
    assert os.getenv('DATABASE_HOST')=='postgres' and os.getenv('DATABASE_NAME')=='workbench'
    queue=RunQueue(os.environ['DATABASE_URL'])
    with queue.conn() as conn:
        try:
            project=conn.execute('SELECT project_id FROM platform.project ORDER BY created_at LIMIT 1').fetchone()['project_id']
            runs=[]
            for _ in range(2):
                task='claim-test-'+uuid4().hex;run=uuid4();runs.append((task,run))
                conn.execute("INSERT INTO platform.task(task_id,project_id,task_name,task_type,requirement_text,status,source_type,target_type) VALUES(%s,%s,'Rollback claim test','NEW','Synthetic rollback only','CREATED','CSV','VERTICA')",(task,project))
                conn.execute("""INSERT INTO platform.task_run(run_id,task_id,project_id,request_key,input_snapshot,input_checksum,settings_snapshot,state)
                    VALUES(%s,%s,%s,%s,'{}',%s,'{}','NEEDS_REVIEW')""",(run,task,project,'claim-test-'+uuid4().hex,'a'*64))
            table='claim_test_'+uuid4().hex
            def insert(pair,name):
                task,run=pair
                conn.execute('''INSERT INTO platform.task_run_target_claim(run_id,task_id,project_id,schema_name,table_name,
                    settings_checksum,specification_checksum,hpl_checksum,ddl_checksum,registry_created_at,registry_rebuilt_at)
                    VALUES(%s,%s,%s,'ai_sample',%s,%s,%s,%s,%s,now(),now())''',
                    (run,task,project,name,*(['a'*64]*4)))
            insert(runs[0],table)
            def empty_check(pair):
                task,run=pair
                conn.execute('''INSERT INTO platform.task_run_target_empty_check
                    (run_id,task_id,project_id,settings_checksum,hpl_checksum,sql_checksum)
                    VALUES(%s,%s,%s,%s,%s,%s)''',(run,task,project,*(['a'*64]*3)))
            empty_check(runs[0])
            with pytest.raises(psycopg.errors.UniqueViolation):
                with conn.transaction():insert(runs[1],table)
            for sql in ('UPDATE platform.task_run_target_claim SET table_name=table_name WHERE run_id=%s',
                        'DELETE FROM platform.task_run_target_claim WHERE run_id=%s',
                        'UPDATE platform.task_run_target_empty_check SET sql_checksum=sql_checksum WHERE run_id=%s',
                        'DELETE FROM platform.task_run_target_empty_check WHERE run_id=%s'):
                with pytest.raises(psycopg.errors.RaiseException,match='immutable'):
                    with conn.transaction():conn.execute(sql,(runs[0][1],))
            insert(runs[1],table+'_other')
            conn.execute('UPDATE platform.task_run SET write_started=true WHERE run_id=%s',(runs[1][1],))
            with pytest.raises(psycopg.errors.RaiseException,match='before execution'):
                with conn.transaction():empty_check(runs[1])
            with pytest.raises(psycopg.errors.RaiseException,match='before execution'):
                with conn.transaction():insert(runs[1],table+'_late')
        finally:
            conn.rollback()
