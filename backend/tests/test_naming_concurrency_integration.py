import os
import time
from threading import Barrier, Event
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
import pytest
from app.repository import PostgresRepository
from app.platform_harness import checksum
from test_run_queue_integration import context

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated Compose DB required')


def contract(reason):
    columns = [{'source_name':'id','english_name':'id','vertica_type':'BIGINT','confidence':1.0,'reason':reason}]
    return {'contract_type':'NamingContractV1','status':'CONFIRMED','columns':columns,'checksum':checksum(columns)}


def test_parallel_naming_returns_own_revision_and_unique_versions(context):
    queue, task_id = context
    repo = PostgresRepository(queue.url)
    barrier = Barrier(2)
    def save(reason):
        data = contract(reason)
        barrier.wait(timeout=5)
        result = repo.confirm_naming_contract(task_id, data)
        assert result['checksum'] == data['checksum']
        assert result['contract_json']['columns'][0]['reason'] == reason
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(save, reason) for reason in ('first caller','second caller')]
        results = [future.result(timeout=10) for future in futures]
    assert {row['version'] for row in results} == {1,2}
    assert len({row['contract_id'] for row in results}) == 2


def test_naming_waits_on_task_lock_used_by_specification_review(context):
    queue, task_id = context
    repo = PostgresRepository(queue.url)
    connected = Event()
    name = 'naming-lock-test-' + uuid4().hex
    def connection():
        conn = psycopg.connect(queue.url, row_factory=dict_row, application_name=name, options='-c lock_timeout=5000')
        connected.set()
        return conn
    repo.conn = connection
    with ThreadPoolExecutor(max_workers=1) as pool:
        with queue.conn() as owner:
            queue.locked_task(owner, task_id)
            future = pool.submit(repo.confirm_naming_contract, task_id, contract('waiting writer'))
            assert connected.wait(timeout=3)
            deadline = time.monotonic()+3
            waiting = False
            while time.monotonic() < deadline:
                with queue.conn() as observer:
                    waiting = observer.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name=%s AND wait_event_type='Lock') AS waiting", (name,)).fetchone()['waiting']
                if waiting:break
                time.sleep(0.02)
            assert waiting and not future.done()
            assert owner.execute('SELECT count(*) AS n FROM platform.naming_contract WHERE task_id=%s',(task_id,)).fetchone()['n'] == 0
        assert future.result(timeout=7)['version'] == 1
