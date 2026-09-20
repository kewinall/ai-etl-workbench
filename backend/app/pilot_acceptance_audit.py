"""Read-only selected Run audit. No models, intent writes or ETL execution."""
import argparse
import json
import os
from uuid import UUID
import vertica_python
from .run_queue import RunQueue
from .repository import PostgresRepository
from .qa_context import load_qa_context
from .qa_journal import QAJournal
from .hop_connection_runtime import connection_runtime
from .bound_result_query import load_bound_result_query,execute_bound_result_query
from .result_reader import read_result_rows
from .expected_result import ResultColumn
from .result_oracle import compare_oracle_document
from . import release_store


def audit(task_id,run_id):
    queue=RunQueue(os.environ['DATABASE_URL']);repo=PostgresRepository(queue.url)
    with queue.conn() as conn:
        run=conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone()
        if not run:raise ValueError('RUN_NOT_FOUND')
        comparison=conn.execute('SELECT comparison_id FROM platform.task_run_result_comparison WHERE run_id=%s ORDER BY created_at DESC LIMIT 1',(run_id,)).fetchone()
        counts=conn.execute("SELECT event_type,count(*) AS count FROM platform.task_run_event WHERE run_id=%s GROUP BY event_type",(run_id,)).fetchall()
        models=conn.execute('SELECT role,model,status,prompt_version,invocation_id FROM platform.agent_invocation WHERE run_id=%s ORDER BY created_at',(run_id,)).fetchall()
        portability=conn.execute('''SELECT p.check_id,p.status,p.evidence,p.checksum
            FROM platform.release_portability_check p JOIN platform.release_candidate_record c USING(candidate_id)
            WHERE c.run_id=%s AND c.task_id=%s ORDER BY p.started_at''',(run_id,task_id)).fetchall()
    captured=load_qa_context(queue,task_id,run_id,comparison['comparison_id'])
    qa=QAJournal(queue).read(task_id,run_id)
    query,oracle=load_bound_result_query(queue,task_id,run_id)
    document=json.loads(oracle['content']);snapshot=run['settings_snapshot']
    with connection_runtime(repo,snapshot,snapshot['checksum']) as runtime:
        config={key:snapshot['connection'][key] for key in ('host','port','database','user','tlsmode')}
        config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'],connection_timeout=10)
        try:
            with vertica_python.connect(**config) as db:
                cursor=db.cursor();execute_bound_result_query(cursor,query,oracle)
                rows=read_result_rows(cursor,[ResultColumn(**column) for column in document['columns']])
        finally:config.clear()
    spec=captured['context']['semantics']['specification']
    comparison_result=compare_oracle_document(oracle['content'],rows,document_checksum=oracle['document_checksum'],
        specification_checksum=captured['context']['specification_checksum'],naming_checksum=spec['naming']['checksum'])
    release=release_store.status(queue,repo,task_id,run_id)
    return dict(task_id=task_id,run_id=str(run_id),read_only=True,models=models,events=counts,
        qa_history=[dict(invocation_id=item['invocation_id'],prompt_version=item['prompt_version'],
            status=item['review']['status'] if item['review'] else item['status'],usage=item['usage']) for item in qa['history']],
        qa_context_version=captured['context']['version'],qa_context_checksum=captured['context']['context_checksum'],
        execution_details=captured['context']['semantics']['execution_details'],
        result_comparison=comparison_result,qa_approved=qa['qa_approved'],
        portability_checks=portability,release=release,release_ready=release['release_ready'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--task-id',required=True);parser.add_argument('--run-id',required=True,type=UUID)
    args=parser.parse_args()
    print(json.dumps(audit(args.task_id,args.run_id),default=str,ensure_ascii=False))
