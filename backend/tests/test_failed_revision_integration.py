"""Isolated PG failure-revision boundary; never claims true Hop/Vertica acceptance."""
from contextlib import nullcontext
import pytest
from app.run_queue import RunQueue,RunConflict
from app.execution_reconciliation import offer,close
from app.control_worker import run_once
from test_run_queue_integration import context,pytestmark


@pytest.mark.parametrize('outcome',['HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN'])
def test_reconciled_failure_new_revision_preserves_history_and_reapproves(context,outcome):
    base,task=context
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self):return nullcontext(conn)
        queue=Queue(base.url)
        try:
            parent=queue.enqueue(task,'failed-parent')
            conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',phase='HOP_EXECUTION',write_started=true,outcome_code=%s WHERE run_id=%s",(outcome,parent['run_id']))
            args=(task,parent['run_id'],'failed-child',parent['input_checksum'],'corrected requirement','ai_sample','revised_target')
            with pytest.raises(RunConflict,match='RUN_NOT_REVISABLE'):queue.revise(*args)
            row=queue.detail(task,parent['run_id'])
            receipt=close(queue,task,parent['run_id'],offer(row)['checksum'],'a'*64,0,
                          engine_stopped=True,target_checked=True,confirmed=True)
            assert queue.detail(task,parent['run_id'])['failed_revision_available']
            with pytest.raises(RunConflict,match='NEW_TARGET_REQUIRED'):
                queue.revise(*args[:6],'synthetic')
            with pytest.raises(RunConflict,match='NEW_TARGET_REQUIRED'):
                queue.revise(*args[:5],'business','revised_target')
            child=queue.revise(*args)
            assert queue.revise(*args)['run_id']==child['run_id']
            preserved=queue.detail(task,parent['run_id'])
            assert preserved['state']=='FAILED' and preserved['outcome_code']==outcome and preserved['write_started']
            assert not preserved['failed_revision_available']
            assert preserved['input_snapshot']==parent['input_snapshot']
            current=queue.detail(task,child['run_id'])
            assert current['parent_run_id']==parent['run_id'] and current['approval'] is None
            assert not current['write_started'] and current['gate_result'] is None
            assert run_once(queue)['status']=='IDLE'
            queue.review(task,child['run_id'],child['input_checksum'],child['settings_snapshot']['checksum'],'APPROVE')
            assert run_once(queue)['status']=='CHECKED'
            assert queue.detail(task,child['run_id'])['phase']=='REQUIREMENT_GATE'
            event=next(e for e in current['events'] if e['event_type']=='REVISION_CREATED')
            assert event['event_context']['reconciliation_id']==receipt['reconciliation_id']
        finally:conn.rollback()


def test_unreconciled_failed_run_cannot_revise(context):
    queue,task=context
    parent=queue.enqueue(task,'failed-parent')
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task_run SET state='FAILED',phase='HOP_EXECUTION',write_started=true,outcome_code='HOP_EXECUTION_FAILED' WHERE run_id=%s",(parent['run_id'],))
    with pytest.raises(RunConflict,match='RECONCILIATION_REQUIRED'):
        queue.revise(task,parent['run_id'],'failed-child',parent['input_checksum'],'corrected','ai_sample','new_target')
