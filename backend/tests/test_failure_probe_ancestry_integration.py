"""Dedicated PostgreSQL only; no Hop, Vertica, model or durable test evidence."""
from contextlib import nullcontext
from uuid import uuid4
import pytest
import psycopg
from app.run_queue import RunQueue
from app.pilot_failure_probe import unexecuted_parents
from test_run_queue_integration import context,pytestmark


@pytest.mark.parametrize('change',['none','parent-written','root-written','cycle','missing'])
def test_fault_acceptance_requires_whole_same_task_unexecuted_chain(context,change):
    base,task=context
    with base.conn() as conn:
        class FixedQueue(RunQueue):
            def conn(self):return nullcontext(conn)
        queue=FixedQueue(base.url)
        try:
            root=queue.enqueue(task,'probe-root-'+uuid4().hex)
            conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',phase='REQUIREMENT_GATE',gate_result='{\"status\":\"NEEDS_INPUT\"}' WHERE run_id=%s",(root['run_id'],))
            parent=queue.revise(task,root['run_id'],'probe-parent-'+uuid4().hex,root['input_checksum'],
                                'Synthetic requirement correction','ai_sample','probe_parent')
            run={'parent_run_id':parent['run_id']}
            if change=='parent-written':conn.execute('UPDATE platform.task_run SET write_started=true WHERE run_id=%s',(parent['run_id'],))
            if change=='root-written':conn.execute('UPDATE platform.task_run SET write_started=true WHERE run_id=%s',(root['run_id'],))
            if change=='cycle':
                with pytest.raises(psycopg.errors.RaiseException,match='Run parent is immutable'):
                    with conn.transaction():
                        conn.execute('UPDATE platform.task_run SET parent_run_id=%s WHERE run_id=%s',(parent['run_id'],root['run_id']))
            if change=='missing':run['parent_run_id']=uuid4()
            assert unexecuted_parents(conn,task,run) is (change in ('none','cycle'))
            assert not unexecuted_parents(conn,'foreign-task',run)
        finally:conn.rollback()
