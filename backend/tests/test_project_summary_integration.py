import os
import pytest
from uuid import uuid4
from app.project_summary import project_summary
from test_run_queue_integration import context

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS')!='1',reason='Isolated PostgreSQL required')


def test_latest_run_only_and_legacy_success_is_not_delivery(context):
    queue,task_id=context
    with queue.conn() as conn:
        project_id=conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s',(task_id,)).fetchone()['project_id']
        conn.execute("UPDATE platform.task SET status='SUCCEEDED' WHERE task_id=%s",(task_id,))
    result=project_summary(queue,project_id)
    assert result['task_count']==1 and result['states']==[{'state':'NO_RUN','count':1}]
    first=queue.enqueue(task_id,'summary-first-0001')
    result=project_summary(queue,project_id)
    assert result['states']==[{'state':'QUEUED','count':1}]
    queue.cancel_unstarted(task_id,first['run_id'])
    result=project_summary(queue,project_id)
    assert result['states']==[{'state':'CANCELLED','count':1}]
    queue.enqueue(task_id,'summary-second-0002')
    result=project_summary(queue,project_id)
    assert result['task_count']==1 and result['states']==[{'state':'QUEUED','count':1}]
    assert not result['qa_evaluated'] and not result['release_evaluated']


def test_summary_isolates_projects(context):
    queue, task_id = context
    other_project = uuid4()
    try:
        with queue.conn() as conn:
            original = conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s', (task_id,)).fetchone()['project_id']
            conn.execute('INSERT INTO platform.project(project_id,project_name) VALUES(%s,%s)', (other_project, 'summary-isolation-' + uuid4().hex))
        assert project_summary(queue, original)['task_count'] == 1
        empty = project_summary(queue, other_project)
        assert empty['task_count'] == 0 and empty['states'] == []
        with queue.conn() as conn:
            conn.execute('UPDATE platform.task SET project_id=%s WHERE task_id=%s', (other_project, task_id))
        assert project_summary(queue, original)['task_count'] == 0
        moved = project_summary(queue, other_project)
        assert moved['task_count'] == 1 and moved['states'] == [{'state': 'NO_RUN', 'count': 1}]
    finally:
        with queue.conn() as conn:
            conn.execute('UPDATE platform.task SET project_id=%s WHERE task_id=%s', (original, task_id))
            conn.execute('DELETE FROM platform.project WHERE project_id=%s', (other_project,))
