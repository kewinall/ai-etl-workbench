"""Close expired QA dispatches without issuing or replaying model requests."""
from psycopg.types.json import Jsonb


def reap_expired_qa(queue):
    with queue.conn() as conn:
        candidates=conn.execute("""SELECT a.invocation_id,a.task_id FROM platform.agent_invocation a
            JOIN platform.qa_dispatch_claim c USING(invocation_id)
            WHERE a.role='pilot_qa' AND a.status='QA_RESERVED'
            AND c.expires_at<=clock_timestamp() ORDER BY c.expires_at LIMIT 100""").fetchall()
    closed=0
    for item in candidates:
        with queue.conn() as conn:
            # Same lock order as finish/dispatch. Recheck after acquiring the lock.
            queue.locked_task(conn,item['task_id'])
            row=conn.execute("""UPDATE platform.agent_invocation a
                SET status='QA_OUTCOME_UNKNOWN',output_json=%s
                FROM platform.qa_dispatch_claim c
                WHERE a.invocation_id=c.invocation_id AND a.invocation_id=%s
                AND a.role='pilot_qa' AND a.status='QA_RESERVED'
                AND c.expires_at<=clock_timestamp() RETURNING a.run_id""",
                (Jsonb({'error_code':'QA_DISPATCH_EXPIRED','automatic_retry':False}),item['invocation_id'])).fetchone()
            if row:
                queue.event(conn,row['run_id'],'QA_OUTCOME_UNKNOWN','QA_REVIEW',
                    {'invocation_id':str(item['invocation_id']),'error_code':'QA_DISPATCH_EXPIRED','automatic_retry':False})
                closed+=1
    return closed
