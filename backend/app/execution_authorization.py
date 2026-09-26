"""Explicit one-attempt consent record. No dispatch, writes or implicit consent."""
from hashlib import sha256
import json
import re
from contextlib import nullcontext
from uuid import uuid4
from psycopg.types.json import Jsonb
from .approved_candidate import load_approved_candidate
from .oracle_store import approved_oracle_binding


def offer(queue, conn, task_id, run_id, specification_id, preparing=False):
    candidate = load_approved_candidate(queue, conn, task_id, run_id, specification_id, preparing=preparing)
    run = candidate['run']
    sources = run['input_snapshot']['source_config'].get('sources') or []
    if len(sources) > 1:
        raise ValueError('MULTI_SOURCE_EXECUTION_NOT_READY')
    if len(sources) != 1 or sources[0].get('type') != 'CSV' or not sources[0].get('upload_id'):
        raise ValueError('VERIFIED_UPLOADED_CSV_REQUIRED')
    source_checksum = sources[0].get('checksum')
    if not isinstance(source_checksum,str) or not re.fullmatch('[a-f0-9]{64}',source_checksum):
        raise ValueError('SOURCE_BINDING_REQUIRED')
    oracle=approved_oracle_binding(conn,candidate)
    binding = {'policy_version':'hop-single-attempt-v2', 'max_attempts':1, 'automatic_retry':False,
               'run_id':str(run_id), 'specification_id':str(specification_id),
               'specification_checksum':candidate['specification_checksum'],
               'specification_approval_id':candidate['approval_id'],
               'input_checksum':run['input_checksum'],
               'settings_checksum':run['settings_snapshot']['checksum'],
               'hpl_checksum':candidate['compiled']['hpl_checksum'],
               'result_query_checksum':candidate['result_query']['checksum'],
               'source_checksum':source_checksum,**oracle}
    digest = sha256(json.dumps(binding,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'binding':binding, 'binding_checksum':digest, 'execution_authorized':False}


def authorize(queue, task_id, run_id, specification_id, binding_checksum, consent, *, connection=None):
    if consent is not True:
        raise ValueError('EXPLICIT_EXECUTION_CONSENT_REQUIRED')
    with (nullcontext(connection) if connection is not None else queue.conn()) as conn:
        current = offer(queue,conn,task_id,run_id,specification_id)
        if current['binding_checksum'] != binding_checksum:
            raise ValueError('EXECUTION_BINDING_CHANGED')
        existing = conn.execute('SELECT *,expires_at>clock_timestamp() AS valid FROM platform.task_run_execution_authorization WHERE run_id=%s FOR SHARE',(run_id,)).fetchone()
        if existing:
            if existing['binding_checksum'] != binding_checksum or not existing['valid']:
                raise ValueError('EXECUTION_AUTHORIZATION_CONFLICT_OR_EXPIRED')
            return {'authorization_id':str(existing['authorization_id']), 'status':'CONSENT_RECORDED_NOT_DISPATCHED'}
        operator = conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
        if not operator:
            raise ValueError('OPERATOR_NOT_CONFIGURED')
        identity = uuid4()
        conn.execute('INSERT INTO platform.task_run_execution_authorization(authorization_id,run_id,specification_id,operator_id,binding,binding_checksum) VALUES(%s,%s,%s,%s,%s,%s)',
                     (identity,run_id,specification_id,operator['operator_id'],Jsonb(current['binding']),binding_checksum))
        queue.event(conn,run_id,'EXECUTION_CONSENT_RECORDED','HOP_PREPARATION',{'authorization_id':str(identity),'binding_checksum':binding_checksum,'automatic_retry_allowed':False})
        return {'authorization_id':str(identity), 'status':'CONSENT_RECORDED_NOT_DISPATCHED'}
