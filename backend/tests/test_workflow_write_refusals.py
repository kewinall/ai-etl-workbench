"""Direct HTTP refusal probes on isolated synthetic Runs; no provider/ETL dispatch."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from app import main
from app.repository import PostgresRepository
from test_run_queue_integration import context

CHECKSUM = 'a' * 64
CASES = [
    ('sa-approval', {'confirmed': True, 'binding_checksum': CHECKSUM}),
    ('qa-approval', {'confirmed': True, 'binding_checksum': CHECKSUM}),
    ('sdm-delivery', {'qa_binding_checksum': CHECKSUM}),
    ('hop-dispatch', {'confirmed': True, 'specification_id': str(uuid4()), 'binding_checksum': CHECKSUM}),
    ('comparison-recovery', {'confirmed': True, 'binding_checksum': CHECKSUM}),
    ('hop-preparation-reconciliation', {'confirmed': True, 'engine_stopped': True, 'target_checked': True,
        'target_exists': False, 'observed_row_count': None, 'binding_checksum': CHECKSUM}),
    ('reconciliation', {'confirmed': True, 'engine_stopped': True, 'target_checked': True,
        'observed_row_count': 0, 'binding_checksum': CHECKSUM}),
    ('release/candidate', {'confirmed': True, 'qa_binding_checksum': CHECKSUM}),
    ('release/approve', {'confirmed': True, 'candidate_id': str(uuid4()), 'binding_checksum': CHECKSUM}),
]


def persisted_counts(queue):
    with queue.conn() as conn:
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='platform' AND table_type='BASE TABLE' ORDER BY table_name").fetchall()
        return {r['table_name']: conn.execute(sql.SQL('SELECT count(*) AS n FROM platform.{}').format(sql.Identifier(r['table_name']))).fetchone()['n'] for r in tables}


@pytest.mark.parametrize('route,payload', CASES)
@pytest.mark.parametrize('state', ['unreviewed', 'written', 'cross_task'])
def test_missing_prerequisites_and_wrong_identity_never_write(context, monkeypatch, route, payload, state):
    queue, task_id = context
    run = queue.enqueue(task_id, 'write-refusal-probe')
    if state == 'written':
        with queue.conn() as conn:
            conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',phase='HOP_EXECUTION',write_started=true,outcome_code='HOP_EXECUTED_QA_REQUIRED' WHERE run_id=%s", (run['run_id'],))
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
    repository = PostgresRepository(queue.url)
    before = repository.get_task(task_id)
    run_before = queue.detail(task_id, run['run_id'])
    counts = persisted_counts(queue)
    address_task = 'wrong-task-identity' if state == 'cross_task' else task_id
    response = TestClient(main.app).post(f'/api/tasks/{address_task}/runs/{run["run_id"]}/{route}', json=payload)
    assert response.status_code in (404, 409, 422), response.text
    assert not isinstance(response.json().get('detail'), list), 'Probe must reach service validation, not fail request schema'
    assert queue.detail(task_id, run['run_id']) == run_before
    assert repository.get_task(task_id) == before
    assert persisted_counts(queue) == counts
