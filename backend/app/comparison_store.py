"""Unverified-source comparison evidence; never a release gate or public write API."""
from hashlib import sha256
import json
from uuid import UUID,uuid4
import re
from psycopg.types.json import Jsonb
from .execution_result_comparison import compare_execution_cursor
from .execution_oracle import load_execution_oracle

EVIDENCE_FIELDS={'version','comparison','status','expected_count','actual_count','missing_count','unexpected_count',
    'expected_checksum','actual_checksum','qa_passed','release_ready','oracle_document_checksum',
    'specification_checksum','naming_checksum','run_id','oracle_id','execution_binding_checksum',
    'hop_event_id','hop_log_checksum','actual_provenance'}


def checked_public_evidence(evidence,checksum,run_id):
    if not isinstance(evidence,dict) or set(evidence)!=EVIDENCE_FIELDS:
        raise ValueError('COMPARISON_EVIDENCE_INVALID')
    if (evidence['run_id']!=str(run_id) or evidence['actual_provenance']!='NOT_VERIFIED'
            or evidence['qa_passed'] is not False or evidence['release_ready'] is not False):
        raise ValueError('COMPARISON_EVIDENCE_INVALID')
    digest=sha256(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=checksum:raise ValueError('COMPARISON_EVIDENCE_CHANGED')
    if (type(evidence['version']) is not int or evidence['version']!=1
            or evidence['comparison']!='EXACT_MULTISET' or evidence['status'] not in ('MATCH','MISMATCH')):
        raise ValueError('COMPARISON_EVIDENCE_INVALID')
    counts=[evidence[key] for key in ('expected_count','actual_count','missing_count','unexpected_count')]
    if any(type(value) is not int or not 0<=value<=10000 for value in counts):
        raise ValueError('COMPARISON_EVIDENCE_INVALID')
    expected,actual,missing,unexpected=counts
    if (missing>expected or unexpected>actual or expected-missing!=actual-unexpected
            or (evidence['status']=='MATCH')!=(missing==unexpected==0)):
        raise ValueError('COMPARISON_EVIDENCE_INVALID')
    if (type(evidence['hop_event_id']) is not int or evidence['hop_event_id']<=0
            or any(not isinstance(evidence[key],str) or not re.fullmatch('[a-f0-9]{64}',evidence[key])
                   for key in EVIDENCE_FIELDS if key.endswith('_checksum'))):
        raise ValueError('COMPARISON_EVIDENCE_INVALID')
    if (evidence['status']=='MATCH')!=(evidence['expected_checksum']==evidence['actual_checksum']):
        raise ValueError('COMPARISON_EVIDENCE_INVALID')
    try:
        for key in ('run_id','oracle_id'):
            if str(UUID(evidence[key]))!=evidence[key]:raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise ValueError('COMPARISON_EVIDENCE_INVALID') from None
    return evidence


def record_execution_comparison(queue,task_id,run_id,cursor):
    result=compare_execution_cursor(queue,task_id,run_id,cursor)
    checksum=sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    checked_public_evidence(result,checksum,run_id)
    with queue.conn() as conn:
        # Recheck state/provenance after potentially slow cursor consumption,
        # holding the same Task lock through evidence + timeline insertion.
        pinned=load_execution_oracle(queue,task_id,run_id,connection=conn)
        expected={'oracle_id':pinned['oracle_id'],'oracle_document_checksum':pinned['document_checksum'],
            'execution_binding_checksum':pinned['binding_checksum'],
            'hop_event_id':pinned['hop_event_id'],'hop_log_checksum':pinned['hop_log_checksum']}
        if any(result[key]!=value for key,value in expected.items()):
            raise ValueError('COMPARISON_BINDING_CHANGED')
        row=conn.execute('SELECT comparison_id,checksum FROM platform.task_run_result_comparison WHERE run_id=%s AND checksum=%s',(run_id,checksum)).fetchone()
        if not row:
            row=conn.execute('INSERT INTO platform.task_run_result_comparison(comparison_id,run_id,checksum,evidence) VALUES(%s,%s,%s,%s) RETURNING comparison_id,checksum',
                (uuid4(),run_id,checksum,Jsonb(result))).fetchone()
            queue.event(conn,run_id,'RESULT_COMPARISON_RECORDED','QA_PREPARATION',
                {'comparison_id':str(row['comparison_id']),'checksum':checksum,'status':result['status'],
                 'actual_provenance':'NOT_VERIFIED','qa_passed':False,'release_ready':False})
    return {'comparison_id':str(row['comparison_id']),'checksum':checksum,'evidence':result,
            'status':'COMPARISON_RECORDED_NOT_QA_APPROVED'}


def list_comparisons(queue,task_id,run_id):
    with queue.conn() as conn:
        if not conn.execute('SELECT run_id FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone():
            raise ValueError('COMPARISON_RUN_NOT_FOUND')
        rows=conn.execute('''SELECT c.comparison_id,c.checksum,c.evidence,c.created_at,
            CASE WHEN p.comparison_id IS NULL THEN NULL ELSE jsonb_build_object(
                'status','BOUND_PLATFORM_TARGET','scope','PLATFORM_MANAGED_TARGET',
                'query_checksum',p.query_checksum,'settings_checksum',p.settings_checksum,
                'empty_checked_at',p.empty_checked_at,'checked_at',p.checked_at,
                'qa_passed',false,'release_ready',false) END AS provenance
            FROM platform.task_run_result_comparison c
            LEFT JOIN platform.result_comparison_provenance p ON p.comparison_id=c.comparison_id
                AND p.run_id=c.run_id AND p.comparison_checksum=c.checksum
            WHERE c.run_id=%s ORDER BY c.created_at,c.comparison_id''',(run_id,)).fetchall()
    return {'items':[{**dict(row),'comparison_id':str(row['comparison_id']),
                     'evidence':checked_public_evidence(row['evidence'],row['checksum'],run_id)} for row in rows],
            'qa_passed':False,'release_ready':False}
