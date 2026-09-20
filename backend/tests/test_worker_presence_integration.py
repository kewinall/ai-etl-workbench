import os
from uuid import uuid4
import pytest
from app.run_queue import RunQueue, RunConflict
from app.worker_presence import WorkerRegistry

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated Compose DB required')


@pytest.fixture
def registry():
    assert os.getenv('DATABASE_HOST') == 'postgres' and os.getenv('DATABASE_NAME') == 'workbench'
    queue = RunQueue(os.environ['DATABASE_URL'])
    with queue.conn() as conn:
        assert conn.execute("SELECT count(*) AS n FROM platform.worker_presence WHERE activity<>'STOPPED' AND last_seen>clock_timestamp()-interval '45 seconds'").fetchone()['n'] == 0
    instance = uuid4()
    try:
        yield queue, WorkerRegistry(queue), instance
    finally:
        with queue.conn() as conn:
            conn.execute('DELETE FROM platform.worker_presence WHERE instance_id=%s', (instance,))


def test_registry_uses_database_time_and_distinguishes_observation(registry):
    queue, workers, instance = registry
    workers.touch(instance, 'SA_COPILOT', 'OBSERVE', 'IDLE')
    row = next(row for row in workers.snapshot()['workers'] if row['kind'] == 'SA_COPILOT')
    assert row['status'] == 'ONLINE' and row['active_instances'] == 1 and row['can_dispatch'] is False
    assert 'instance_id' not in row and 'hostname' not in row
    with pytest.raises(RunConflict, match='IDENTITY'):
        workers.touch(instance, 'SA_COPILOT', 'EXECUTE', 'IDLE')
    with queue.conn() as conn:
        conn.execute("UPDATE platform.worker_presence SET last_seen=clock_timestamp()-interval '46 seconds' WHERE instance_id=%s", (instance,))
    row = next(row for row in workers.snapshot()['workers'] if row['kind'] == 'SA_COPILOT')
    assert row['status'] == 'OFFLINE' and row['can_dispatch'] is False


def test_clean_shutdown_cannot_reanimate_same_worker_identity(registry):
    _, workers, instance = registry
    workers.touch(instance, 'SA_COPILOT', 'EXECUTE', 'BUSY')
    row = next(row for row in workers.snapshot()['workers'] if row['kind'] == 'SA_COPILOT')
    assert row['status'] == 'ONLINE' and row['can_dispatch'] is True
    workers.touch(instance, 'SA_COPILOT', 'EXECUTE', 'STOPPED')
    with pytest.raises(RunConflict, match='IDENTITY'):
        workers.touch(instance, 'SA_COPILOT', 'EXECUTE', 'IDLE')
    row = next(row for row in workers.snapshot()['workers'] if row['kind'] == 'SA_COPILOT')
    assert row['status'] == 'OFFLINE' and row['can_dispatch'] is False
