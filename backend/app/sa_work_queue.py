"""SA outbox on the existing invocation journal. Never reclaims an uncertain call."""
from uuid import uuid4
from .run_queue import RunConflict
from .sa_contract import build_sa_context, digest, SAReviewV1
from .sa_gateway import PROMPT, PROMPT_VERSION


def authorization_offer(run):
    identity = {
            'input_checksum': run['input_checksum'], 'settings_checksum': run['settings_snapshot']['checksum'],
            'context_checksum': build_sa_context(run)['context_checksum'],
            'prompt_checksum': digest(PROMPT), 'schema_checksum': digest(SAReviewV1.model_json_schema())}
    if run['settings_snapshot']['ai']['provider_type'] == 'LOCAL_COPILOT':
        return {**identity, 'consent': True, 'policy_version': 'copilot-cli-once-v1',
                'max_cli_sessions': 1, 'automatic_retries': 0, 'token_cap_supported': False}
    return {**identity, 'consent': True, 'policy_version': 'sa-bounded-v1',
            'max_provider_attempts': 4, 'max_output_tokens_per_attempt': 2048}


class SAWorkQueue:
    def __init__(self, queue):
        self.queue = queue

    def enqueue(self, task_id, run_id, authorization):
        from .sa_journal import SAJournal
        if authorization.get('consent') is not True:
            raise RunConflict('SA_MODEL_CALL_CONSENT_REQUIRED')
        result = SAJournal(self.queue).reserve(task_id, run_id, authorization)
        return {key: result[key] for key in ('invocation_id', 'status')}

    def claim(self, provider_type=None, task_id=None, run_id=None):
        # Lock the owning Task first, matching revision/cancellation/journal lock order.
        with self.queue.conn() as conn:
            record = conn.execute("""SELECT a.* FROM platform.agent_invocation a
                JOIN platform.task t ON t.task_id=a.task_id
                WHERE a.role='pilot_sa' AND a.status='SA_QUEUED'
                AND ((%s::text IS NULL AND a.provider IN ('LITELLM_BEDROCK','LITELLM_PROXY')) OR a.provider=%s)
                AND (%s::text IS NULL OR a.task_id=%s)
                AND (%s::uuid IS NULL OR a.run_id=%s)
                ORDER BY a.created_at LIMIT 1 FOR UPDATE OF t SKIP LOCKED""", (provider_type, provider_type, task_id, task_id, run_id, run_id)).fetchone()
            if not record:
                return None
            task = self.queue.locked_task(conn, record['task_id'])
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s FOR UPDATE', (record['run_id'],)).fetchone()
            payload = record['input_json']
            valid = (run['state'] == 'NEEDS_REVIEW' and not run['write_started']
                     and self.queue.matches_current(conn, task, run)
                     and payload.get('authorization') == authorization_offer(run)
                     and payload['context'] == build_sa_context(run)
                     and record['prompt_version'] == PROMPT_VERSION)
            if not valid:
                conn.execute("UPDATE platform.agent_invocation SET status='STALE_NOT_DISPATCHED' WHERE invocation_id=%s AND status='SA_QUEUED'", (record['invocation_id'],))
                self.queue.event(conn, run['run_id'], 'SA_STALE_NOT_DISPATCHED', run['phase'])
                return {'status': 'STALE_NOT_DISPATCHED'}
            token = uuid4()
            claimed = conn.execute("""UPDATE platform.agent_invocation SET status='DISPATCH_RESERVED',
                claim_token=%s,lease_until=clock_timestamp()+interval '60 seconds',
                dispatch_deadline=clock_timestamp()+interval '10 minutes'
                WHERE invocation_id=%s AND status='SA_QUEUED' RETURNING *""", (token, record['invocation_id'])).fetchone()
            if not claimed:
                return None
            self.queue.event(conn, run['run_id'], 'SA_DISPATCH_RESERVED', run['phase'])
            return claimed

    def cancel_queued(self, task_id, run_id):
        with self.queue.conn() as conn:
            self.queue.locked_task(conn, task_id)
            row = conn.execute("SELECT * FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND role='pilot_sa' FOR UPDATE", (task_id, run_id)).fetchone()
            if not row or row['status'] not in ('SA_QUEUED', 'CANCELLED_NOT_DISPATCHED'):
                raise RunConflict('SA_ALREADY_CLAIMED_REQUIRES_RECONCILIATION')
            if row['status'] == 'SA_QUEUED':
                conn.execute("UPDATE platform.agent_invocation SET status='CANCELLED_NOT_DISPATCHED' WHERE invocation_id=%s", (row['invocation_id'],))
                self.queue.event(conn, run_id, 'SA_CANCELLED_NOT_DISPATCHED', 'REQUIREMENT_GATE')
            return {'invocation_id': row['invocation_id'], 'status': 'CANCELLED_NOT_DISPATCHED'}

    def heartbeat(self, invocation_id, token):
        with self.queue.conn() as conn:
            row = conn.execute("""UPDATE platform.agent_invocation
                SET lease_until=least(clock_timestamp()+interval '60 seconds',dispatch_deadline)
                WHERE invocation_id=%s AND claim_token=%s AND status='DISPATCH_RESERVED'
                AND lease_until>clock_timestamp() AND dispatch_deadline>clock_timestamp()
                RETURNING invocation_id""", (invocation_id, token)).fetchone()
            if not row:
                raise RunConflict('SA_LEASE_LOST')

    def reap_expired(self):
        with self.queue.conn() as conn:
            rows = conn.execute("""SELECT a.invocation_id,a.run_id FROM platform.agent_invocation a
                JOIN platform.task t ON t.task_id=a.task_id
                WHERE a.role='pilot_sa' AND a.status='DISPATCH_RESERVED' AND a.claim_token IS NOT NULL
                AND (a.lease_until<=clock_timestamp() OR a.dispatch_deadline<=clock_timestamp())
                FOR UPDATE OF t SKIP LOCKED""").fetchall()
            count = 0
            for row in rows:
                updated = conn.execute("""UPDATE platform.agent_invocation SET status='OUTCOME_UNKNOWN_NEEDS_REVIEW'
                    WHERE invocation_id=%s AND status='DISPATCH_RESERVED'
                    AND (lease_until<=clock_timestamp() OR dispatch_deadline<=clock_timestamp())
                    RETURNING invocation_id""", (row['invocation_id'],)).fetchone()
                if updated:
                    self.queue.event(conn, row['run_id'], 'SA_WORKER_EXPIRED_NO_RETRY', 'REQUIREMENT_GATE')
                    count += 1
            return count
