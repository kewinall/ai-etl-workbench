import os
from uuid import uuid4
import pytest
from app.project_evaluation import read
from test_run_queue_integration import context

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS')!='1',reason='Isolated PostgreSQL required')


def test_inventory_retains_no_run_and_cancelled_history(context):
    queue,task_id=context
    with queue.conn() as conn:
        project=conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s',(task_id,)).fetchone()['project_id']
    initial=read(queue,project)
    assert len(initial['cases'])==1
    assert initial['cases'][0]['run_id'] is None
    assert initial['cases'][0]['historical_release_count']==0
    first=queue.enqueue(task_id,'evaluation-first-0001')
    queue.cancel_unstarted(task_id,first['run_id'])
    second=queue.enqueue(task_id,'evaluation-second-0002')
    result=read(queue,project)
    assert [str(row['run_id']) for row in result['cases']]==[str(second['run_id']),str(first['run_id'])]
    assert [row['state'] for row in result['cases']]==['QUEUED','CANCELLED']
    assert result['comparison_ready'] is False
    assert result['improvement_rate'] is None


def test_inventory_is_project_scoped(context):
    queue,task_id=context
    with queue.conn() as conn:
        project=conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s',(task_id,)).fetchone()['project_id']
    assert read(queue,uuid4())['cases']==[]
    assert {row['task_id'] for row in read(queue,project)['cases']}=={task_id}
