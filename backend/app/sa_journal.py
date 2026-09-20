"""Durable SA intent. No model calls; an uncertain intent is never auto-resubmitted."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from .run_queue import RunConflict
from .sa_contract import build_sa_context, validate_sa_review, digest, SAReviewV1
from .sa_gateway import PROMPT, PROMPT_VERSION


class SAJournal:
    def __init__(self, queue):
        self.queue = queue

    def context(self, task_id, run_id):
        with self.queue.conn() as conn:
            self.queue.locked_task(conn, task_id)
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s', (run_id, task_id)).fetchone()
            if not run:
                raise ValueError('RUN_NOT_FOUND')
            row = conn.execute("SELECT input_json,context_checksum FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND role='pilot_sa'", (task_id, run_id)).fetchone()
            if row:
                context = row['input_json']['context']
                if context.get('context_checksum') != row['context_checksum'] or digest({key: value for key, value in context.items() if key != 'context_checksum'}) != row['context_checksum']:
                    raise ValueError('SA_CONTEXT_INTEGRITY_ERROR')
                return {'context': context, 'context_origin': 'CAPTURED_AT_AUTHORIZATION'}
            return {'context': build_sa_context(run), 'context_origin': 'CURRENT_PREVIEW_NOT_DISPATCHED'}

    def read(self, task_id, run_id):
        with self.queue.conn() as conn:
            task = self.queue.locked_task(conn, task_id)
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s', (run_id, task_id)).fetchone()
            if not run:
                raise ValueError('RUN_NOT_FOUND')
            row = conn.execute("SELECT * FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND role='pilot_sa'", (task_id, run_id)).fetchone()
            result = {'run_id': str(run_id), 'matches_current': self.queue.matches_current(conn, task, run),
                      'dispatch_available': False, 'execution_authorized': False, 'invocation': None}
            if row:
                output = row['output_json'] or {}
                trace = output.get('trace') or {}
                usage = trace.get('usage') or {}
                result['invocation'] = {key: row[key] for key in ('invocation_id', 'status', 'provider', 'model', 'prompt_version', 'context_checksum', 'created_at')}
                result['invocation']['usage'] = {key: usage.get(key) for key in ('input_tokens', 'output_tokens', 'total_tokens', 'usage_type', 'ai_credits', 'premium_requests', 'cli_sessions', 'automatic_retries', 'tool_execution_count')}
                result['invocation']['duration_ms'] = trace.get('duration_ms', row['duration_ms'])
                result['invocation']['review'] = output.get('review') if row['status'] in ('VALIDATED_NOT_APPROVED', 'STALE_RESULT_NEEDS_REVIEW') else None
                allowed_errors = {'MODEL_CALL_FAILED', 'MODEL_TEMPORARY_FAILURE', 'MODEL_OUTPUT_INVALID', 'SA_OUTPUT_CONTRACT_INVALID', 'SA_DISPATCH_INTERRUPTED', 'SA_RUN_NOT_AUTHORIZED', 'SA_GATE_BLOCKED', 'SA_MODEL_VERSION_MISMATCH'}
                result['invocation']['error_code'] = trace.get('error_code') if trace.get('error_code') in allowed_errors else ('SA_REVIEW_REQUIRED' if trace.get('error_code') else None)
            return result

    def reserve(self, task_id, run_id, authorization=None):
        with self.queue.conn() as conn:
            task = self.queue.locked_task(conn, task_id)
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s FOR UPDATE', (run_id, task_id)).fetchone()
            if not run:
                raise ValueError('RUN_NOT_FOUND')
            existing = conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_sa'", (run_id,)).fetchone()
            if existing and authorization is not None and (existing['input_json'] or {}).get('authorization') == authorization:
                return {'invocation_id': existing['invocation_id'], 'status': existing['status']}
            if existing:
                raise RunConflict('SA_ALREADY_RESERVED_NO_AUTOMATIC_RETRY')
            approval = conn.execute("SELECT operator_id FROM platform.task_run_approval WHERE run_id=%s AND decision='APPROVE' AND input_checksum=%s AND settings_checksum=%s", (run_id, run['input_checksum'], run['settings_snapshot']['checksum'])).fetchone()
            if not approval or run['state'] != 'NEEDS_REVIEW' or run['write_started'] or not self.queue.matches_current(conn, task, run):
                raise RunConflict('SA_RUN_NOT_AUTHORIZED')
            context = build_sa_context(run)
            if context['deterministic_gate']['status'] != 'CHECKED':
                raise RunConflict('SA_GATE_BLOCKED')
            if authorization is not None:
                from .sa_work_queue import authorization_offer
                if authorization != authorization_offer(run) or (run.get('gate_result') or {}).get('status') != 'CHECKED':
                    raise RunConflict('SA_AUTHORIZATION_VERSION_MISMATCH')
            settings = run['settings_snapshot']
            invocation_id = uuid4()
            payload = {'context': context, 'prompt': PROMPT, 'prompt_checksum': digest(PROMPT),
                       'schema': SAReviewV1.model_json_schema(), 'schema_checksum': digest(SAReviewV1.model_json_schema())}
            status = 'SA_QUEUED' if authorization is not None else 'DISPATCH_RESERVED'
            if authorization is not None:
                payload.update(authorization=authorization, operator_id=str(approval['operator_id']))
            conn.execute("INSERT INTO platform.agent_invocation(invocation_id,task_id,run_id,role,provider,model,prompt_version,context_checksum,input_json,status) VALUES(%s,%s,%s,'pilot_sa',%s,%s,%s,%s,%s,%s)", (invocation_id, task_id, run_id, settings['ai']['provider_type'], settings['model_routes']['requirement_gate'], PROMPT_VERSION, context['context_checksum'], Jsonb(payload), status))
            self.queue.event(conn, run_id, status, run['phase'])
            return {'invocation_id': invocation_id, 'context': context, 'status': status}

    def finish(self, task_id, invocation_id, output, trace=None, claim_token=None):
        with self.queue.conn() as conn:
            task = self.queue.locked_task(conn, task_id)
            record = conn.execute("SELECT * FROM platform.agent_invocation WHERE invocation_id=%s AND task_id=%s AND role='pilot_sa' FOR UPDATE", (invocation_id, task_id)).fetchone()
            if not record or record['status'] != 'DISPATCH_RESERVED':
                raise RunConflict('SA_RESULT_NOT_WRITABLE')
            if record.get('claim_token'):
                if not conn.execute('SELECT 1 FROM platform.agent_invocation WHERE invocation_id=%s AND claim_token=%s AND lease_until>clock_timestamp() AND dispatch_deadline>clock_timestamp()', (invocation_id, claim_token)).fetchone():
                    raise RunConflict('SA_LEASE_LOST')
            accepted = validate_sa_review(output, record['input_json']['context'])
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s FOR UPDATE', (record['run_id'],)).fetchone()
            current = run['state'] == 'NEEDS_REVIEW' and not run['write_started'] and self.queue.matches_current(conn, task, run)
            status = 'VALIDATED_NOT_APPROVED' if current else 'STALE_RESULT_NEEDS_REVIEW'
            if current:
                outcome = 'SA_REQUIREMENT_NEEDS_INPUT' if accepted['status'] == 'NEEDS_INPUT' else 'SA_REVIEW_REQUIRES_APPROVAL'
                conn.execute('UPDATE platform.task_run SET outcome_code=%s,updated_at=now() WHERE run_id=%s', (outcome, run['run_id']))
            conn.execute('UPDATE platform.agent_invocation SET status=%s,output_json=%s WHERE invocation_id=%s', (status, Jsonb({'review': accepted, 'output_checksum': digest(accepted), 'trace': trace, 'execution_authorized': False}), invocation_id))
            self.queue.event(conn, run['run_id'], 'SA_' + status, run['phase'])
            return status

    def hold_uncertain(self, task_id, invocation_id, trace=None):
        with self.queue.conn() as conn:
            self.queue.locked_task(conn, task_id)
            row = conn.execute("UPDATE platform.agent_invocation SET status='OUTCOME_UNKNOWN_NEEDS_REVIEW',output_json=%s WHERE invocation_id=%s AND task_id=%s AND role='pilot_sa' AND status='DISPATCH_RESERVED' RETURNING run_id", (Jsonb({'trace': trace, 'execution_authorized': False}), invocation_id, task_id)).fetchone()
            if not row:
                raise RunConflict('SA_RESULT_NOT_WRITABLE')
            self.queue.event(conn, row['run_id'], 'SA_OUTCOME_UNKNOWN_NEEDS_REVIEW', 'REQUIREMENT_GATE')
