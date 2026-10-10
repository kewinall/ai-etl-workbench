import os
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.workflow_status import create_workflow_router
from app.repository import PostgresRepository
from test_run_queue_integration import context

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated PostgreSQL only')


def test_status_reads_real_stores_without_writes_or_dispatch(context):
    queue, task_id = context
    run = queue.enqueue(task_id, 'workflow-status-integration')
    app = FastAPI()
    app.include_router(create_workflow_router(queue, PostgresRepository(os.environ['DATABASE_URL'])))
    client = TestClient(app)
    before = queue.detail(task_id, run['run_id'])
    url = f'/api/tasks/{task_id}/runs/{run["run_id"]}/workflow-status'
    for _ in range(2):
        result = client.get(url)
        assert result.status_code == 200, result.text
        assert result.headers['cache-control'] == 'no-store'
        assert result.json()['current_stage'] == 'requirements'
        assert result.json()['run_id'] == str(run['run_id'])
    assert queue.detail(task_id, run['run_id']) == before
    with queue.conn() as conn:
        for table in ('agent_invocation', 'hop_dispatch_request', 'release_candidate_record'):
            assert conn.execute(f'SELECT count(*) AS n FROM platform.{table} WHERE run_id=%s', (run['run_id'],)).fetchone()['n'] == 0
    assert client.get(url.replace(task_id, 'nonexistent-task')).status_code == 404
    assert client.get(url.replace(str(run['run_id']), str(uuid4()))).status_code == 404
