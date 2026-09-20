"""Durable Pilot queue foundation. Does not invoke legacy ETL or external writes."""
import hashlib
import json
import re
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .execution_settings import resolve_settings


class RunConflict(ValueError):
    pass


class RunBlocked(ValueError):
    def __init__(self, issues):
        super().__init__('RUN_SETTINGS_BLOCKED')
        self.issues = issues


def without_secrets(value):
    if isinstance(value, dict):
        return {key: without_secrets(item) for key, item in value.items()
                if not any(part in key.lower() for part in ('password', 'secret', 'token', 'api_key', 'access_key'))}
    if isinstance(value, list):
        return [without_secrets(item) for item in value]
    return value


class LockedSettings:
    def __init__(self, conn):
        self.conn = conn
    def get_project(self, project_id):
        return self.conn.execute('SELECT * FROM platform.project WHERE project_id=%s FOR SHARE', (project_id,)).fetchone()
    def setting(self, key, default):
        row = self.conn.execute('SELECT setting_value FROM platform.system_setting WHERE setting_key=%s FOR SHARE', (key,)).fetchone()
        return row['setting_value'] if row else default
    def ai_profile(self, profile_id):
        return self.conn.execute('SELECT * FROM platform.ai_provider_profile WHERE profile_id=%s FOR SHARE', (profile_id,)).fetchone()
    def secret_version(self, secret_ref):
        row = self.conn.execute('SELECT updated_at FROM platform.secret_vault_entry WHERE secret_ref=%s FOR SHARE', (secret_ref,)).fetchone()
        return row['updated_at'].isoformat() if row else None


class RunQueue:
    def __init__(self, url):
        self.url = url

    def conn(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=5,
                               options='-c statement_timeout=10000 -c lock_timeout=5000')

    def start_gate(self, run_id, token):
        with self.conn() as conn:
            row = conn.execute("UPDATE platform.task_run SET phase='REQUIREMENT_GATE',updated_at=now() WHERE run_id=%s AND state='RUNNING' AND phase='PREFLIGHT' AND lease_token=%s AND lease_until>clock_timestamp() RETURNING run_id", (run_id, token)).fetchone()
            if not row:
                raise RunConflict('GATE_TRANSITION_REJECTED')
            self.event(conn, run_id, 'REQUIREMENT_GATE_STARTED', 'REQUIREMENT_GATE')

    def complete_gate(self, run_id, token, result):
        if result.get('status') not in ('NEEDS_INPUT','CHECKED','ERROR'):
            raise ValueError('INVALID_GATE_RESULT')
        outcome = {'NEEDS_INPUT':'REQUIREMENT_NEEDS_INPUT','CHECKED':'PIPELINE_NOT_READY','ERROR':'CONTROL_WORKER_ERROR'}[result['status']]
        with self.conn() as conn:
            row = conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',outcome_code=%s,gate_result=%s,lease_token=NULL,lease_until=NULL,updated_at=now() WHERE run_id=%s AND state='RUNNING' AND phase='REQUIREMENT_GATE' AND gate_result IS NULL AND NOT write_started AND lease_token=%s AND lease_until>clock_timestamp() RETURNING run_id", (outcome, Jsonb(result), run_id, token)).fetchone()
            if not row:
                raise RunConflict('GATE_TRANSITION_REJECTED')
            self.event(conn, run_id, outcome, 'REQUIREMENT_GATE')

    @staticmethod
    def locked_task(conn, task_id):
        task = conn.execute('SELECT task_id,project_id,requirement_text,source_type,source_config,target_type,target_config FROM platform.task WHERE task_id=%s FOR UPDATE', (task_id,)).fetchone()
        if not task:
            raise ValueError('TASK_NOT_FOUND')
        return task

    @staticmethod
    def input_snapshot(task, overrides):
        snapshot = without_secrets({**task, 'project_id': str(task['project_id']), 'execution_overrides': overrides})
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return snapshot, digest

    def matches_current(self, conn, task, run):
        overrides = run['input_snapshot'].get('execution_overrides', {})
        _, digest = self.input_snapshot(task, overrides)
        resolved = resolve_settings(LockedSettings(conn), task, overrides)
        return (digest == run['input_checksum'] and resolved['snapshot'] is not None
                and resolved['snapshot']['checksum'] == run['settings_snapshot']['checksum'])

    def enqueue(self, task_id, request_key, overrides=None):
        if not isinstance(request_key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,120}', request_key):
            raise ValueError('INVALID_REQUEST_KEY')
        overrides = overrides or {}
        if set(overrides) - {'ai_profile_id', 'connection_id'}:
            raise ValueError('UNKNOWN_EXECUTION_OVERRIDE')
        with self.conn() as conn:
            task = self.locked_task(conn, task_id)
            # Same request returns its existing result even after later edits.
            existing = conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND request_key=%s', (task_id, request_key)).fetchone()
            if existing:
                if existing['input_snapshot'].get('execution_overrides', {}) != overrides:
                    raise RunConflict('IDEMPOTENCY_KEY_REUSED')
                return existing
            active = conn.execute("SELECT run_id FROM platform.task_run WHERE task_id=%s AND state IN ('QUEUED','RUNNING','NEEDS_REVIEW')", (task_id,)).fetchone()
            if active:
                raise RunConflict('ACTIVE_RUN_EXISTS')
            resolved = resolve_settings(LockedSettings(conn), task, overrides)
            if resolved['status'] == 'BLOCKED':
                raise RunBlocked(resolved['issues'])
            snapshot, digest = self.input_snapshot(task, overrides)
            run_id = uuid4()
            result = conn.execute('INSERT INTO platform.task_run(run_id,task_id,project_id,request_key,input_snapshot,input_checksum,settings_snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                                  (run_id, task_id, task['project_id'], request_key, Jsonb(snapshot), digest, Jsonb(resolved['snapshot']))).fetchone()
            self.event(conn, run_id, 'ENQUEUED', 'PREFLIGHT')
            return result

    def revise(self, task_id, parent_id, request_key, input_checksum, requirement_text, target_schema, target_table, requirements_v1=None, source_fields_v1=None, csv_input_contract_v1=None, csv_replacement_v1=None):
        from .source_replacement import replace_csv_source, verify_csv_replacement
        if csv_replacement_v1 is not None and source_fields_v1 is not None:
            raise ValueError('CONFLICTING_SOURCE_CHANGES')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,120}', request_key):
            raise ValueError('INVALID_REQUEST_KEY')
        if not requirement_text.strip() or len(requirement_text) > 20000:
            raise ValueError('INVALID_REQUIREMENT')
        if any(not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', value) for value in (target_schema, target_table)):
            raise ValueError('INVALID_TARGET_IDENTIFIER')
        with self.conn() as conn:
            task = self.locked_task(conn, task_id)
            parent = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s FOR UPDATE', (parent_id, task_id)).fetchone()
            if not parent:
                raise ValueError('RUN_NOT_FOUND')
            if input_checksum != parent['input_checksum']:
                raise RunConflict('REVIEW_CHECKSUM_MISMATCH')
            target = {**(parent['input_snapshot'].get('target_config') or {}), 'schema': target_schema, 'table': target_table}
            from .source_revision import revise_source
            from .csv_contract import revise_csv_contract
            source = revise_source(parent['input_snapshot'].get('source_config') or {}, source_fields_v1)
            source = replace_csv_source(source, csv_replacement_v1)
            source = revise_csv_contract(source, csv_input_contract_v1)
            if requirements_v1 is not None:
                from .requirement_contract import RequirementConditionsV1
                target['requirements_v1'] = RequirementConditionsV1.model_validate(requirements_v1).model_dump()
            existing = conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND request_key=%s', (task_id, request_key)).fetchone()
            if existing:
                snapshot = existing['input_snapshot']
                if existing['parent_run_id'] != parent_id or snapshot['requirement_text'] != requirement_text or snapshot['target_config'] != target or snapshot['source_config'] != source:
                    raise RunConflict('IDEMPOTENCY_KEY_REUSED')
                return existing
            if parent['state'] != 'NEEDS_REVIEW' or parent['phase'] != 'REQUIREMENT_GATE' or not parent['gate_result'] or parent['write_started']:
                raise RunConflict('RUN_NOT_REVISABLE')
            if not self.matches_current(conn, task, parent):
                raise RunConflict('INPUT_OR_SETTINGS_CHANGED')
            verify_csv_replacement(csv_replacement_v1)
            if requirement_text == task['requirement_text'] and target == task['target_config'] and source == without_secrets(task['source_config']):
                raise RunConflict('REVISION_HAS_NO_CHANGES')
            overrides = parent['input_snapshot'].get('execution_overrides', {})
            # Keep private connection/file metadata from the live Task, never restore a masked snapshot.
            source = revise_source(task['source_config'] or {}, source_fields_v1)
            source = replace_csv_source(source, csv_replacement_v1)
            source = revise_csv_contract(source, csv_input_contract_v1)
            updated_task = {**task, 'requirement_text': requirement_text, 'target_config': target, 'source_config': source}
            resolved = resolve_settings(LockedSettings(conn), updated_task, overrides)
            if resolved['status'] == 'BLOCKED':
                raise RunBlocked(resolved['issues'])
            snapshot, digest = self.input_snapshot(updated_task, overrides)
            # All changes commit together; never reset legacy Task execution or artifacts.
            conn.execute('UPDATE platform.task SET requirement_text=%s,target_config=%s,source_config=%s WHERE task_id=%s', (requirement_text, Jsonb(target), Jsonb(source), task_id))
            conn.execute("UPDATE platform.task_run SET state='CANCELLED',outcome_code='SUPERSEDED_BY_REVISION',updated_at=now() WHERE run_id=%s", (parent_id,))
            result = conn.execute('INSERT INTO platform.task_run(run_id,task_id,project_id,request_key,input_snapshot,input_checksum,settings_snapshot,parent_run_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                (uuid4(), task_id, task['project_id'], request_key, Jsonb(snapshot), digest, Jsonb(resolved['snapshot']), parent_id)).fetchone()
            self.event(conn, parent_id, 'SUPERSEDED_BY_REVISION', parent['phase'])
            self.event(conn, result['run_id'], 'REVISION_CREATED', 'PREFLIGHT')
            return result

    @staticmethod
    def event(conn, run_id, event, phase, context=None):
        conn.execute('INSERT INTO platform.task_run_event(run_id,event_type,phase,event_context) VALUES(%s,%s,%s,%s)', (run_id, event, phase, Jsonb(context or {})))

    def claim(self, lease_seconds=60):
        if type(lease_seconds) is not int or not 10 <= lease_seconds <= 300:
            raise ValueError('INVALID_LEASE')
        with self.conn() as conn:
            # Lock order is Task -> Run -> settings for enqueue, review and claim.
            row = conn.execute("SELECT r.run_id,r.task_id FROM platform.task_run r JOIN platform.task t ON t.task_id=r.task_id WHERE r.state='QUEUED' AND EXISTS (SELECT 1 FROM platform.task_run_approval a WHERE a.run_id=r.run_id AND a.decision='APPROVE' AND a.input_checksum=r.input_checksum AND a.settings_checksum=r.settings_snapshot->>'checksum') ORDER BY r.created_at,r.run_id FOR UPDATE OF t SKIP LOCKED LIMIT 1").fetchone()
            if not row:
                return None
            task = self.locked_task(conn, row['task_id'])
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s FOR UPDATE', (row['run_id'],)).fetchone()
            if run['state'] != 'QUEUED':
                return None
            if not self.matches_current(conn, task, run):
                conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',outcome_code='INPUT_OR_SETTINGS_CHANGED',updated_at=now() WHERE run_id=%s", (run['run_id'],))
                self.event(conn, run['run_id'], 'APPROVAL_STALE', run['phase'])
                return None
            result = conn.execute("UPDATE platform.task_run SET state='RUNNING',lease_token=%s,lease_until=clock_timestamp()+(%s * interval '1 second'),updated_at=now() WHERE run_id=%s RETURNING *", (uuid4(), lease_seconds, row['run_id'])).fetchone()
            self.event(conn, row['run_id'], 'CLAIMED', result['phase'])
            return result

    def review(self, task_id, run_id, input_checksum, settings_checksum, decision):
        if decision not in ('APPROVE', 'REJECT'):
            raise ValueError('INVALID_DECISION')
        with self.conn() as conn:
            task = self.locked_task(conn, task_id)
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s FOR UPDATE', (run_id, task_id)).fetchone()
            if not run:
                raise ValueError('RUN_NOT_FOUND')
            if run['input_checksum'] != input_checksum or run['settings_snapshot']['checksum'] != settings_checksum:
                raise RunConflict('REVIEW_CHECKSUM_MISMATCH')
            existing = conn.execute('SELECT * FROM platform.task_run_approval WHERE run_id=%s', (run_id,)).fetchone()
            if existing:
                if existing['decision'] != decision:
                    raise RunConflict('REVIEW_ALREADY_RECORDED')
                if decision == 'APPROVE' and not self.matches_current(conn, task, run):
                    raise RunConflict('INPUT_OR_SETTINGS_CHANGED')
                return existing
            if run['state'] != 'QUEUED' or run['write_started']:
                raise RunConflict('RUN_NOT_REVIEWABLE')
            if not self.matches_current(conn, task, run):
                raise RunConflict('INPUT_OR_SETTINGS_CHANGED')
            operator = conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
            if not operator:
                raise ValueError('OPERATOR_NOT_CONFIGURED')
            result = conn.execute("INSERT INTO platform.task_run_approval(approval_id,run_id,operator_id,kind,decision,input_checksum,settings_checksum) VALUES(%s,%s,%s,'INPUT_REVIEW',%s,%s,%s) RETURNING *", (uuid4(), run_id, operator['operator_id'], decision, input_checksum, settings_checksum)).fetchone()
            self.event(conn, run_id, 'INPUT_' + decision, run['phase'])
            if decision == 'REJECT':
                conn.execute("UPDATE platform.task_run SET state='CANCELLED',outcome_code='INPUT_REJECTED',updated_at=now() WHERE run_id=%s", (run_id,))
            return result

    def cancel_unstarted(self, task_id, run_id):
        with self.conn() as conn:
            self.locked_task(conn, task_id)
            row = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s FOR UPDATE', (run_id, task_id)).fetchone()
            if not row:
                raise ValueError('RUN_NOT_FOUND')
            if row['state'] == 'CANCELLED':
                return row
            if row['state'] not in ('QUEUED','NEEDS_REVIEW') or row['write_started']:
                raise RunConflict('RUN_REQUIRES_EXECUTION_RECONCILIATION')
            row = conn.execute("UPDATE platform.task_run SET state='CANCELLED',outcome_code='OPERATOR_CANCELLED',updated_at=now() WHERE run_id=%s RETURNING *", (run_id,)).fetchone()
            self.event(conn, run_id, 'OPERATOR_CANCELLED', row['phase'])
            return row

    def list_runs(self, task_id):
        with self.conn() as conn:
            self.locked_task(conn, task_id)
            return conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s ORDER BY created_at DESC,run_id', (task_id,)).fetchall()

    def detail(self, task_id, run_id):
        with self.conn() as conn:
            task = self.locked_task(conn, task_id)
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s AND task_id=%s', (run_id, task_id)).fetchone()
            if not run:
                raise ValueError('RUN_NOT_FOUND')
            approval = conn.execute('SELECT * FROM platform.task_run_approval WHERE run_id=%s', (run_id,)).fetchone()
            events = conn.execute('SELECT event_id,event_type,phase,created_at,event_context FROM platform.task_run_event WHERE run_id=%s ORDER BY event_id', (run_id,)).fetchall()
            return {**run, 'approval': approval, 'matches_current': self.matches_current(conn, task, run), 'events': events}

    def heartbeat(self, run_id, token, lease_seconds=60):
        if type(lease_seconds) is not int or not 10 <= lease_seconds <= 300:
            raise ValueError('INVALID_LEASE')
        with self.conn() as conn:
            row = conn.execute("UPDATE platform.task_run SET lease_until=clock_timestamp()+(%s * interval '1 second'),updated_at=now() WHERE run_id=%s AND state='RUNNING' AND lease_token=%s AND lease_until>clock_timestamp() RETURNING run_id", (lease_seconds, run_id, token)).fetchone()
            if not row:
                raise RunConflict('LEASE_LOST')

    def begin_external_write(self, run_id, token, prepared_binding=None):
        with self.conn() as conn:
            identity = conn.execute('SELECT task_id FROM platform.task_run WHERE run_id=%s', (run_id,)).fetchone()
            if not identity:
                raise ValueError('RUN_NOT_FOUND')
            task = self.locked_task(conn, identity['task_id'])
            run = conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s FOR UPDATE', (run_id,)).fetchone()
            if not self.matches_current(conn, task, run):
                raise RunConflict('INPUT_OR_SETTINGS_CHANGED')
            from .execution_authorization import offer
            import os
            if os.getenv('WORKBENCH_EXECUTION_ENABLED') != 'true':
                raise RunConflict('EXECUTION_DISABLED')
            receipt = conn.execute('SELECT a.*,r.binding_checksum AS reserved_checksum FROM platform.task_run_execution_reservation r JOIN platform.task_run_execution_authorization a USING(authorization_id) WHERE r.run_id=%s AND a.run_id=%s FOR SHARE OF r,a',(run_id,run_id)).fetchone()
            if not receipt:
                raise RunConflict('EXECUTION_RESERVATION_REQUIRED')
            if run['lease_token'] != token or run['state'] != 'RUNNING' or run['phase'] != 'HOP_PREPARATION' or run['write_started']:
                raise RunConflict('WRITE_NOT_AUTHORIZED_OR_ALREADY_STARTED')
            current = offer(self,conn,task['task_id'],run_id,receipt['specification_id'],preparing=True)
            expected = {key:current['binding'][key] for key in ('run_id','specification_id','specification_checksum','input_checksum','settings_checksum','hpl_checksum','source_checksum')}
            expected['approval_id'] = current['binding']['specification_approval_id']
            if (prepared_binding != expected or current['binding_checksum'] != receipt['binding_checksum']
                    or current['binding_checksum'] != receipt['reserved_checksum']):
                raise RunConflict('EXECUTION_BINDING_CHANGED')
            row = conn.execute("UPDATE platform.task_run SET write_started=true,phase='HOP_EXECUTION',updated_at=now() WHERE run_id=%s AND state='RUNNING' AND lease_token=%s AND lease_until>clock_timestamp() AND NOT write_started AND %s>clock_timestamp() RETURNING run_id", (run_id, token, receipt['expires_at'])).fetchone()
            if not row:
                raise RunConflict('WRITE_NOT_AUTHORIZED_OR_ALREADY_STARTED')
            self.event(conn, run_id, 'WRITE_STARTED', 'HOP_EXECUTION')

    def finish(self, run_id, token, state):
        if state not in ('SUCCEEDED', 'FAILED', 'NEEDS_REVIEW'):
            raise ValueError('INVALID_OUTCOME')
        with self.conn() as conn:
            row = conn.execute("UPDATE platform.task_run SET state=%s,lease_token=NULL,lease_until=NULL,updated_at=now() WHERE run_id=%s AND state='RUNNING' AND lease_token=%s AND lease_until>clock_timestamp() AND NOT write_started RETURNING phase", (state, run_id, token)).fetchone()
            if not row:
                raise RunConflict('LEASE_LOST')
            self.event(conn, run_id, state, row['phase'])

    def fail_hop_preparation(self, run_id, token):
        with self.conn() as conn:
            row = conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',outcome_code='HOP_PREPARATION_INVALID',lease_token=NULL,lease_until=NULL,updated_at=now() WHERE run_id=%s AND state='RUNNING' AND phase='HOP_PREPARATION' AND NOT write_started AND lease_token=%s AND lease_until>clock_timestamp() RETURNING phase", (run_id, token)).fetchone()
            if not row:
                raise RunConflict('LEASE_LOST_OR_HOP_ALREADY_STARTED')
            self.event(conn, run_id, 'HOP_PREPARATION_INVALID', row['phase'],
                       {'automatic_retry_allowed':False, 'external_write_started':False})
        return {'status':'HOP_PREPARATION_INVALID', 'run_id':str(run_id)}

    def complete_hop(self, run_id, token, result):
        from .hop_outcome import validated_hop_outcome
        outcome, evidence = validated_hop_outcome(result)
        with self.conn() as conn:
            if result['log_checksum'] is not None:
                log = conn.execute('SELECT checksum FROM platform.task_run_private_log WHERE run_id=%s FOR SHARE', (run_id,)).fetchone()
                if not log or log['checksum'] != result['log_checksum']:
                    raise RunConflict('HOP_LOG_EVIDENCE_MISSING_OR_CHANGED')
            row = conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',outcome_code=%s,lease_token=NULL,lease_until=NULL,updated_at=now() WHERE run_id=%s AND state='RUNNING' AND phase='HOP_EXECUTION' AND write_started AND lease_token=%s AND lease_until>clock_timestamp() RETURNING phase", (outcome, run_id, token)).fetchone()
            if not row:
                raise RunConflict('LEASE_LOST_OR_HOP_NOT_STARTED')
            self.event(conn, run_id, outcome, row['phase'], evidence)
        return {'status':outcome, 'run_id':str(run_id)}

    def reap_expired(self):
        with self.conn() as conn:
            rows = conn.execute("UPDATE platform.task_run SET state='NEEDS_REVIEW',outcome_code=CASE WHEN write_started THEN 'HOP_RESULT_UNKNOWN' ELSE 'LEASE_EXPIRED' END,lease_token=NULL,lease_until=NULL,updated_at=now() WHERE run_id IN (SELECT run_id FROM platform.task_run WHERE state='RUNNING' AND lease_until<=clock_timestamp() FOR UPDATE SKIP LOCKED) RETURNING run_id,phase,write_started,outcome_code").fetchall()
            for row in rows:
                self.event(conn, row['run_id'], 'LEASE_EXPIRED_NEEDS_REVIEW', row['phase'],
                           {'outcome_code':row['outcome_code'], 'external_write_may_have_occurred':row['write_started'], 'automatic_retry_allowed':False})
            return len(rows)
