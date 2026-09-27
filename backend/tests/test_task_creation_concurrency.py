import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from app.repository import PostgresRepository
from app.repository import TaskCreationConflict
from test_run_queue_integration import context

pytestmark=pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS')!='1',reason='Isolated PostgreSQL required')

def test_concurrent_creation_keeps_unique_ids_and_complete_children(context):
    queue,existing=context
    repo=PostgresRepository(os.environ['DATABASE_URL'])
    project=repo.get_task(existing)['project_id']
    barrier=Barrier(8)
    def create(index):
        barrier.wait()
        return repo.create_task(dict(project_id=project,name=f'Concurrent synthetic {index}',
            requirement='Synthetic creation only',source_type='CSV',source_config={},
            target_type='VERTICA',target_schema='ai_sample',target_table='never_created',model='synthetic'))
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(create,range(8)))
        assert len({row['id'] for row in results})==8
        assert all(len(row['nodes'])==8 and len(row['logs'])==1 for row in results)
        assert all(row['status']=='CREATED' and row['project_id']==project for row in results)
    finally:
        # Only this isolated fixture's newly created synthetic tasks; no runs exist.
        with queue.conn() as conn:
            conn.execute('DELETE FROM platform.task WHERE project_id=%s AND task_id<>%s',(project,existing))

def test_same_request_replays_once_and_changed_payload_conflicts(context):
    queue,existing=context
    repo=PostgresRepository(os.environ['DATABASE_URL'])
    project=repo.get_task(existing)['project_id']
    payload=dict(project_id=project,creation_request_key=str(uuid4()),name='Synthetic retry',
        requirement='Synthetic request only',source_type='CSV',source_config={},
        target_type='VERTICA',target_schema='ai_sample',target_table='never_created',model='synthetic')
    barrier=Barrier(6)
    def create(_):
        barrier.wait()
        return repo.create_task(payload)['id']
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            ids=list(pool.map(create,range(6)))
        assert len(set(ids))==1
        assert repo.create_task(payload)['id']==ids[0]
        with pytest.raises(TaskCreationConflict):repo.create_task({**payload,'name':'Changed request'})
        assert len(repo.get_task(ids[0])['logs'])==1
    finally:
        with queue.conn() as conn:
            conn.execute('DELETE FROM platform.task WHERE project_id=%s AND task_id<>%s',(project,existing))
