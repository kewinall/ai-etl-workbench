"""Internal post-execution oracle selection. No target query, QA pass or API."""
from hashlib import sha256
import json
import re
from contextlib import nullcontext
from .private_oracle import decrypt_oracle
from .result_oracle import compare_oracle_document
from .hop_outcome import validated_hop_outcome
from .source_binding import execution_sources


def required_result_query_checksum(binding):
    value = binding.get('result_query_checksum') if isinstance(binding, dict) else None
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('EXECUTION_RESULT_QUERY_BINDING_REQUIRED')
    return value


def load_execution_oracle(queue,task_id,run_id,*,connection=None):
    with (nullcontext(connection) if connection is not None else queue.conn()) as conn:
        queue.locked_task(conn,task_id)
        run=conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND run_id=%s FOR SHARE',(task_id,run_id)).fetchone()
        if (not run or run['state']!='NEEDS_REVIEW' or run['phase']!='HOP_EXECUTION'
                or not run['write_started'] or run['outcome_code']!='HOP_EXECUTED_QA_REQUIRED' or run['lease_token'] is not None):
            raise ValueError('COMPLETED_HOP_EXECUTION_REQUIRED')
        events=conn.execute("SELECT event_id,event_context FROM platform.task_run_event WHERE run_id=%s AND event_type='HOP_EXECUTED_QA_REQUIRED' AND phase='HOP_EXECUTION' ORDER BY event_id FOR SHARE",(run_id,)).fetchall()
        log=conn.execute('SELECT checksum FROM platform.task_run_private_log WHERE run_id=%s FOR SHARE',(run_id,)).fetchone()
        if len(events)!=1 or not log:raise ValueError('HOP_COMPLETION_EVIDENCE_REQUIRED')
        evidence=events[0]['event_context']
        outcome,_=validated_hop_outcome({key:evidence.get(key) for key in ('status','exit_code','errors','log_checksum')})
        if outcome!='HOP_EXECUTED_QA_REQUIRED' or evidence['log_checksum']!=log['checksum']:
            raise ValueError('HOP_COMPLETION_EVIDENCE_CHANGED')
        consent=conn.execute('''SELECT a.*,r.binding_checksum AS reserved_checksum
            FROM platform.task_run_execution_authorization a
            JOIN platform.task_run_execution_reservation r ON r.authorization_id=a.authorization_id AND r.run_id=a.run_id
            WHERE a.run_id=%s FOR SHARE OF a,r''',(run_id,)).fetchone()
        if not consent:raise ValueError('EXECUTION_ORACLE_BINDING_REQUIRED')
        binding=consent['binding']
        digest=sha256(json.dumps(binding,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        policy=binding.get('policy_version')
        if (policy not in ('hop-single-attempt-v2','hop-single-attempt-v3') or digest!=consent['binding_checksum']
                or digest!=consent['reserved_checksum'] or binding.get('run_id')!=str(run_id)
                or binding.get('specification_id')!=str(consent['specification_id'])):
            raise ValueError('EXECUTION_ORACLE_BINDING_CHANGED')
        if policy == 'hop-single-attempt-v3':
            expected_sources=execution_sources(run['input_snapshot']['source_config'],2)
            if any(binding.get(key)!=value for key,value in expected_sources.items()):
                raise ValueError('EXECUTION_ORACLE_BINDING_CHANGED')
        elif 'source_checksums' in binding:
            raise ValueError('EXECUTION_ORACLE_BINDING_CHANGED')
        query_checksum = required_result_query_checksum(binding)
        row=conn.execute('''SELECT o.*,a.approval_id,a.document_checksum AS approved_checksum
            FROM platform.result_oracle o JOIN platform.result_oracle_approval a USING(oracle_id)
            JOIN platform.specification s USING(specification_id)
            WHERE o.oracle_id=%s AND s.specification_id=%s AND s.task_id=%s AND s.run_id=%s
            FOR SHARE OF o,a,s''',(binding.get('oracle_id'),consent['specification_id'],task_id,run_id)).fetchone()
        if (not row or str(row['approval_id'])!=binding.get('oracle_approval_id')
                or row['version']!=binding.get('oracle_version') or row['document_checksum']!=binding.get('oracle_checksum')
                or row['approved_checksum']!=row['document_checksum']
                or row['specification_checksum']!=binding.get('specification_checksum')):
            raise ValueError('EXECUTION_ORACLE_BINDING_CHANGED')
        content=decrypt_oracle(run_id,consent['specification_id'],row)
        compare_oracle_document(content,[],document_checksum=row['document_checksum'],
            specification_checksum=row['specification_checksum'],naming_checksum=row['naming_checksum'])
    # This merely selects immutable expected data. Callers still need trustworthy
    # actual-result provenance and persisted QA evidence; never return content in HTTP.
    return {'status':'EXECUTION_ORACLE_PINNED_NOT_COMPARED','content':content,
            'binding_checksum':digest,'oracle_id':str(row['oracle_id']),
            'result_query_checksum':query_checksum,
            'document_checksum':row['document_checksum'],'hop_event_id':events[0]['event_id'],
            'hop_log_checksum':log['checksum'],'qa_passed':False,'release_ready':False}
