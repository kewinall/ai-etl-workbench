"""Single-consumption Developer intent and atomic specification handoff.

No provider calls, automatic approval or ETL execution occur in this module.
"""
from uuid import uuid4
from psycopg.types.json import Jsonb
from .developer_contract import load_context, validate_proposal
from .developer_gateway import developer_material
from .etl_specification import validate_specification
from .invocation_usage import checked_usage
from .sa_contract import digest
from .specification_store import save


def checked_trace(trace, record, output):
    expected = {key: record[key] for key in ('provider', 'model', 'prompt_version', 'context_checksum')}
    expected.update(run_id=str(record['run_id']), status='VALIDATED_NOT_APPROVED',
                    input_checksum=record['input_json']['context']['input_checksum'],
                    prompt_checksum=record['input_json']['prompt_checksum'],
                    schema_checksum=record['input_json']['schema_checksum'], output_checksum=digest(output))
    if any(trace.get(key) != value for key, value in expected.items()):
        raise ValueError('DEVELOPER_TRACE_BINDING_CHANGED')
    duration = trace.get('duration_ms')
    if type(duration) is not int or duration < 0:
        raise ValueError('DEVELOPER_TRACE_INVALID')
    usage = checked_usage(trace.get('usage'))
    if record['provider'] == 'LOCAL_COPILOT' and any(
            usage.get(key) != value for key, value in
            (('cli_sessions', 1), ('automatic_retries', 0), ('tool_execution_count', 0))):
        raise ValueError('DEVELOPER_NATIVE_USAGE_INVALID')
    return {**expected, 'duration_ms': duration, 'usage': usage}


class DeveloperJournal:
    def __init__(self, queue):
        self.queue = queue

    def reserve(self, task_id, run_id, context_checksum, *, confirmed=False):
        if confirmed is not True:
            raise ValueError('DEVELOPER_EXPLICIT_CONSENT_REQUIRED')
        with self.queue.conn() as conn:
            captured = load_context(self.queue, conn, task_id, run_id)
            context = captured['context']; settings = captured['run']['settings_snapshot']
            if context['context_checksum'] != context_checksum:
                raise ValueError('DEVELOPER_CONTEXT_VERSION_CHANGED')
            existing = conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_developer'", (run_id,)).fetchone()
            if existing:
                if existing['context_checksum'] != context_checksum:
                    raise ValueError('DEVELOPER_ALREADY_RESERVED_NO_AUTOMATIC_RETRY')
                return {'invocation_id': str(existing['invocation_id']), 'status': existing['status']}
            model = (settings.get('model_routes') or {}).get('etl_specification')
            if not model:
                raise ValueError('DEVELOPER_MODEL_NOT_CONFIGURED')
            operator = conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
            if not operator:
                raise ValueError('OPERATOR_NOT_CONFIGURED')
            identity = uuid4()
            material = developer_material(context)
            payload = {'context': context, 'operator_id': str(operator['operator_id']), 'consent_recorded': True,
                       **{key: material[key] for key in ('prompt', 'prompt_checksum', 'schema', 'schema_checksum')}}
            conn.execute("""INSERT INTO platform.agent_invocation
                (invocation_id,task_id,run_id,role,provider,model,prompt_version,context_checksum,input_json,status)
                VALUES(%s,%s,%s,'pilot_developer',%s,%s,%s,%s,%s,'DEVELOPER_RESERVED')""",
                (identity, task_id, run_id, settings['ai']['provider_type'], model, material['prompt_version'], context_checksum, Jsonb(payload)))
            self.queue.event(conn, run_id, 'DEVELOPER_INTENT_RECORDED', 'SPEC_GENERATION',
                             {'invocation_id': str(identity), 'context_checksum': context_checksum, 'automatic_retry': False})
        return {'invocation_id': str(identity), 'status': 'DEVELOPER_RESERVED'}

    def claim(self, task_id, invocation_id):
        with self.queue.conn() as conn:
            self.queue.locked_task(conn, task_id)
            row = conn.execute("SELECT * FROM platform.agent_invocation WHERE invocation_id=%s AND task_id=%s AND role='pilot_developer' FOR UPDATE", (invocation_id, task_id)).fetchone()
            if not row or row['status'] != 'DEVELOPER_RESERVED':
                raise ValueError('DEVELOPER_NOT_DISPATCHABLE')
            current = load_context(self.queue, conn, task_id, row['run_id'])
            if current['context'] != row['input_json']['context']:
                raise ValueError('DEVELOPER_CONTEXT_VERSION_CHANGED')
            token = uuid4()
            result = conn.execute('''INSERT INTO platform.developer_dispatch_claim(invocation_id,claim_token)
                VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING claim_token''', (invocation_id, token)).fetchone()
            if not result:
                raise ValueError('DEVELOPER_DISPATCH_ALREADY_CONSUMED')
        return token

    def _check(self, conn, task_id, invocation_id, token):
        self.queue.locked_task(conn, task_id)
        row = conn.execute('''SELECT a.* FROM platform.agent_invocation a
            JOIN platform.developer_dispatch_claim c USING(invocation_id)
            WHERE a.task_id=%s AND a.invocation_id=%s AND a.role='pilot_developer'
            AND a.status='DEVELOPER_RESERVED' AND c.claim_token=%s AND c.expires_at>clock_timestamp()
            FOR UPDATE OF a''', (task_id, invocation_id, token)).fetchone()
        if not row:
            raise ValueError('DEVELOPER_DISPATCH_CLAIM_EXPIRED_OR_LOST')
        return row

    def check(self, task_id, invocation_id, token):
        with self.queue.conn() as conn:
            row = self._check(conn, task_id, invocation_id, token)
            captured = load_context(self.queue, conn, task_id, row['run_id'])
            if captured['context'] != row['input_json']['context']:
                raise ValueError('DEVELOPER_CONTEXT_VERSION_CHANGED')
            return captured

    def finish(self, task_id, invocation_id, token, output, trace):
        with self.queue.conn() as conn:
            row = self._check(conn, task_id, invocation_id, token)
            safe_trace = checked_trace(trace, row, output)
            try:
                captured = load_context(self.queue, conn, task_id, row['run_id'])
                fresh = captured['context'] == row['input_json']['context']
            except ValueError:
                fresh = False
            stored = None
            if fresh:
                accepted = validate_proposal(output, captured)
                validated = validate_specification(accepted['proposal']['specification'], captured['run'], captured['naming'])
                stored = save(self.queue, conn, task_id, row['run_id'], validated)
                stored = {**stored, 'specification_id': str(stored['specification_id'])}
            status = 'VALIDATED_NOT_APPROVED' if fresh else 'STALE_RESULT_NEEDS_REVIEW'
            # Even stale replies retain their exact checksum and usage, never a new specification.
            conn.execute('UPDATE platform.agent_invocation SET status=%s,output_json=%s,duration_ms=%s WHERE invocation_id=%s',
                         (status, Jsonb({'proposal': output, 'proposal_checksum': digest(output), 'trace': safe_trace,
                                         'specification': stored, 'execution_authorized': False, 'release_ready': False}),
                          safe_trace['duration_ms'], invocation_id))
            self.queue.event(conn, row['run_id'], 'DEVELOPER_' + status, 'SPEC_GENERATION',
                             {'invocation_id': str(invocation_id), 'execution_authorized': False})
        return {'status': status, 'specification': stored, 'execution_authorized': False, 'release_ready': False}

    def hold_uncertain(self, task_id, invocation_id, token):
        with self.queue.conn() as conn:
            self.queue.locked_task(conn, task_id)
            # A matching consumed claim may expire while the provider is running.
            row = conn.execute("""UPDATE platform.agent_invocation a SET status='DEVELOPER_OUTCOME_UNKNOWN',output_json=%s
                WHERE a.task_id=%s AND a.invocation_id=%s AND a.role='pilot_developer' AND a.status='DEVELOPER_RESERVED'
                AND EXISTS(SELECT 1 FROM platform.developer_dispatch_claim c WHERE c.invocation_id=a.invocation_id AND c.claim_token=%s)
                RETURNING a.run_id""", (Jsonb({'error_code': 'DEVELOPER_OUTCOME_UNKNOWN', 'automatic_retry': False}), task_id, invocation_id, token)).fetchone()
            if not row:
                raise ValueError('DEVELOPER_RESULT_NOT_WRITABLE')
            self.queue.event(conn, row['run_id'], 'DEVELOPER_OUTCOME_UNKNOWN', 'SPEC_GENERATION', {'automatic_retry': False})
