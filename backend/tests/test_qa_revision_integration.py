"""Real isolated PG revision transaction; QA evidence acceptance tested separately."""
from contextlib import nullcontext
import pytest
from app.run_queue import RunQueue,RunConflict
from test_run_queue_integration import context,pytestmark


def test_qa_revision_preserves_outcome_and_requires_new_approval(context,monkeypatch):
    base,task=context
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self):return nullcontext(conn)
        queue=Queue(base.url)
        try:
            parent=queue.enqueue(task,'qa-parent')
            conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',phase='HOP_EXECUTION',write_started=true,outcome_code='HOP_EXECUTED_QA_REQUIRED' WHERE run_id=%s",(parent['run_id'],))
            binding={'checksum':'b'*64,'invocation_id':'synthetic-qa','automatic_retry_allowed':False}
            monkeypatch.setattr('app.qa_revision.offer',lambda q,c,r: binding if r['state']=='NEEDS_REVIEW' else None)
            args=(task,parent['run_id'],'qa-child',parent['input_checksum'],'clarified requirement','ai_sample','corrected_qa_target')
            with pytest.raises(RunConflict,match='CONFIRMATION_REQUIRED'):queue.revise(*args)
            with pytest.raises(RunConflict,match='BINDING_CHANGED'):queue.revise(*args,qa_revision_checksum='x'*64)
            with pytest.raises(RunConflict,match='NEW_TARGET_REQUIRED'):
                queue.revise(*args[:5],'business','new_target',qa_revision_checksum='b'*64)
            child=queue.revise(*args,qa_revision_checksum='b'*64)
            assert queue.revise(*args,qa_revision_checksum='b'*64)['run_id']==child['run_id']
            saved=queue.detail(task,parent['run_id'])
            assert saved['state']=='CANCELLED' and saved['outcome_code']=='HOP_EXECUTED_QA_REQUIRED'
            assert saved['write_started'] and saved['input_snapshot']==parent['input_snapshot']
            new=queue.detail(task,child['run_id'])
            assert new['parent_run_id']==parent['run_id'] and new['approval'] is None
            assert new['state']=='QUEUED' and not new['write_started'] and new['gate_result'] is None
            assert any(e['event_type']=='QA_REVISION_LINKED' and e['event_context']==binding for e in saved['events'])
        finally:conn.rollback()
