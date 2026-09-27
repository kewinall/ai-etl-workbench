"""Real process death and fresh-process recovery; synthetic write marker, not Hop."""
import json
import os
import selectors
import subprocess
import sys

import pytest
from app.run_queue import RunConflict
from test_run_queue_integration import context

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1',
                                reason='Isolated PostgreSQL required')


@pytest.mark.parametrize('write_started', [False, True])
def test_dead_owner_not_reclaimed_by_fresh_process(context, write_started):
    queue, task = context
    run = queue.enqueue(task, 'process-loss-request')
    queue.review(task, run['run_id'], run['input_checksum'], run['settings_snapshot']['checksum'], 'APPROVE')
    child_code = '''
import os,time
from app.run_queue import RunQueue
q=RunQueue(os.environ['DATABASE_URL'])
r=q.claim()
assert str(r['run_id'])==os.environ['TEST_RUN_ID']
if os.environ['TEST_WRITE_MARKER']=='1':
 with q.conn() as c:
  c.execute("UPDATE platform.task_run SET write_started=true,phase='HOP_EXECUTION' WHERE run_id=%s",(r['run_id'],))
print('CLAIM_COMMITTED',flush=True)
time.sleep(300)
'''
    environment = {**os.environ, 'TEST_RUN_ID': str(run['run_id']),
                   'TEST_WRITE_MARKER': '1' if write_started else '0'}
    child = subprocess.Popen([sys.executable, '-c', child_code], env=environment,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=10), 'Synthetic owner did not commit its claim'
            assert child.stdout.readline().strip() == 'CLAIM_COMMITTED'
        owned = queue.detail(task, run['run_id'])
        assert owned['state'] == 'RUNNING' and owned['write_started'] is write_started
        child.kill()
        assert child.wait(timeout=10) != 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        child.stdout.close()
        child.stderr.close()
    # Advance the synthetic lease after actual owner death; do not wait on wall clock.
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task_run SET lease_until=clock_timestamp()-interval '1 second' WHERE run_id=%s", (run['run_id'],))
    recovery = '''
import json,os
from app.run_queue import RunQueue
q=RunQueue(os.environ['DATABASE_URL'])
print(json.dumps({'reaped':q.reap_expired(),'reaped_again':q.reap_expired(),'claim':q.claim()}))
'''
    result = subprocess.run([sys.executable, '-c', recovery], env=environment,
                            capture_output=True, text=True, timeout=15, check=True)
    assert json.loads(result.stdout) == {'reaped': 1, 'reaped_again': 0, 'claim': None}
    saved = queue.detail(task, run['run_id'])
    assert saved['state'] == 'NEEDS_REVIEW' and saved['lease_token'] is None
    assert saved['outcome_code'] == ('HOP_RESULT_UNKNOWN' if write_started else 'LEASE_EXPIRED')
    assert sum(e['event_type']=='LEASE_EXPIRED_NEEDS_REVIEW' for e in saved['events']) == 1
    assert saved['events'][-1]['event_context']['automatic_retry_allowed'] is False
    with pytest.raises(RunConflict):
        queue.finish(run['run_id'], owned['lease_token'], 'SUCCEEDED')
    with pytest.raises(RunConflict, match='ACTIVE_RUN_EXISTS'):
        queue.enqueue(task, 'process-loss-new-request')
    assert queue.enqueue(task, 'process-loss-request')['run_id'] == run['run_id']
