"""Dedicated disposable PostgreSQL only; retains synthetic death evidence.

No model, Hop, DDL target creation or Vertica is invoked.
"""
import os
import selectors
import subprocess
import sys
import pytest
from app.run_queue import RunQueue
from app.hop_dispatch import claim

pytestmark = pytest.mark.skipif(
    os.getenv('WORKBENCH_HOP_CLAIM_DEATH_TEST') != 'dedicated-disposable-database',
    reason='Dedicated disposable DB required; committed synthetic evidence retained')


def test_dead_preparation_owner_cannot_be_claimed_again(tmp_path, monkeypatch):
    assert os.environ['DATABASE_HOST'] == 'postgres'
    assert os.environ['DATABASE_NAME'] == 'workbench'
    queue = RunQueue(os.environ['DATABASE_URL'])
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) n FROM platform.task_run').fetchone()['n'] == 0
    script = '''
import sys,time
from pathlib import Path
import pytest
sys.path.insert(0,'/app/backend/tests')
import test_hop_dispatch_integration as scenario
from test_run_queue_integration import context
original=scenario.claim
def claimed_then_wait(q,*args):
    result=original(q,*args)
    assert result is not None
    with q.conn() as conn: conn.commit()
    print('PREPARATION_CLAIM_COMMITTED',flush=True)
    time.sleep(300)
    raise RuntimeError('Parent failed to terminate synthetic owner')
scenario.claim=claimed_then_wait
fixture=context.__wrapped__()
scope=next(fixture)
scenario.test_website_hop_request_requires_lineage_and_is_single_consumption(
    scope,Path(sys.argv[1]),pytest.MonkeyPatch())
'''
    child = subprocess.Popen([sys.executable, '-c', script, str(tmp_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            assert selector.select(15), 'Synthetic preparation owner did not commit'
            assert child.stdout.readline().strip() == 'PREPARATION_CLAIM_COMMITTED'
        child.kill()
        assert child.wait(10) != 0
    finally:
        if child.poll() is None:
            child.kill(); child.wait(10)
        child.stdout.close(); child.stderr.close()
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
    with queue.conn() as conn:
        rows = conn.execute('SELECT r.status,t.task_id,t.run_id,t.write_started,t.lease_token FROM platform.hop_dispatch_request r JOIN platform.task_run t USING(run_id)').fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row['status'] == 'CLAIMED' and not row['write_started'] and row['lease_token'] is None
        before = conn.execute('SELECT count(*) n FROM platform.task_run_event').fetchone()['n']
    assert queue.reap_expired() == 0
    assert claim(queue, row['task_id'], row['run_id']) is None
    assert claim(queue, row['task_id'], row['run_id']) is None
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) n FROM platform.task_run_event').fetchone()['n'] == before
        assert conn.execute('SELECT count(*) n FROM platform.task_run_target_claim').fetchone()['n'] == 0
    # CLAIMED is deliberately not called recovered: operator resolution is still missing.
