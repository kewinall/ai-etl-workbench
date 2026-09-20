"""Internal versioned encrypted oracle storage. No QA approval or public API."""
from hashlib import sha256
import json
from uuid import uuid4
from .approved_candidate import load_approved_candidate
from .private_oracle import encrypt_oracle, decrypt_oracle
from .oracle_schema import validate_oracle_schema,oracle_columns
from .result_oracle import compare_oracle_document


def save_oracle(queue, task_id, run_id, specification_id, content):
    if not isinstance(content,bytes) or not 1<=len(content)<=8*1024*1024:
        raise ValueError('ORACLE_DOCUMENT_LIMIT')
    with queue.conn() as conn:
        # Existing Task lock serializes versions and rejects stale/foreign inputs.
        candidate=load_approved_candidate(queue,conn,task_id,run_id,specification_id)
        naming=conn.execute('SELECT checksum FROM platform.naming_contract WHERE contract_id=(SELECT naming_contract_id FROM platform.specification WHERE specification_id=%s)',(specification_id,)).fetchone()
        sealed=encrypt_oracle(run_id,specification_id,content,document_checksum=sha256(content).hexdigest(),
                              specification_checksum=candidate['specification_checksum'],naming_checksum=naming['checksum'])
        document=json.loads(content)
        validate_oracle_schema(document,candidate['compiled'])
        latest=conn.execute('SELECT oracle_id,version,document_checksum FROM platform.result_oracle WHERE specification_id=%s ORDER BY version DESC LIMIT 1',(specification_id,)).fetchone()
        if latest and latest['document_checksum']==sealed['document_checksum']:
            row=latest
        else:
            row=conn.execute('INSERT INTO platform.result_oracle(oracle_id,specification_id,version,document_checksum,specification_checksum,naming_checksum,cipher_text,nonce,size) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING oracle_id,version,document_checksum',
                (uuid4(),specification_id,latest['version']+1 if latest else 1,sealed['document_checksum'],sealed['specification_checksum'],sealed['naming_checksum'],sealed['cipher_text'],sealed['nonce'],sealed['size'])).fetchone()
            queue.event(conn,run_id,'RESULT_ORACLE_SAVED','QA_PREPARATION',{'oracle_id':str(row['oracle_id']),'version':row['version'],'document_checksum':row['document_checksum'],'approved':False})
    return {**dict(row),'oracle_id':str(row['oracle_id']),'status':'ORACLE_SAVED_NOT_APPROVED','qa_passed':False,'release_ready':False}


def approved_oracle_binding(conn,candidate):
    """Caller holds the Task lock; revalidated on offer, reserve and write gate."""
    sid=candidate['specification_id'];run_id=candidate['run']['run_id']
    row=conn.execute('SELECT * FROM platform.result_oracle WHERE specification_id=%s ORDER BY version DESC LIMIT 1 FOR SHARE',(sid,)).fetchone()
    if not row:raise ValueError('EXPECTED_RESULT_ORACLE_REQUIRED')
    approval=conn.execute('SELECT approval_id,document_checksum FROM platform.result_oracle_approval WHERE oracle_id=%s FOR SHARE',(row['oracle_id'],)).fetchone()
    if not approval or approval['document_checksum']!=row['document_checksum']:
        raise ValueError('EXPECTED_RESULT_ORACLE_APPROVAL_REQUIRED')
    content=decrypt_oracle(run_id,sid,row)
    compare_oracle_document(content,[],document_checksum=row['document_checksum'],
        specification_checksum=candidate['specification_checksum'],
        naming_checksum=candidate['compiled']['specification']['naming']['checksum'])
    validate_oracle_schema(json.loads(content),candidate['compiled'])
    return {'oracle_id':str(row['oracle_id']),'oracle_version':row['version'],
        'oracle_checksum':row['document_checksum'],'oracle_approval_id':str(approval['approval_id'])}


def oracle_editor_context(queue,task_id,run_id,specification_id):
    with queue.conn() as conn:
        candidate=load_approved_candidate(queue,conn,task_id,run_id,specification_id)
        compiled=candidate['compiled']
        columns=oracle_columns(compiled)
    return {'version':1,'specification_checksum':candidate['specification_checksum'],
        'naming_checksum':compiled['specification']['naming']['checksum'],'columns':columns,
        'output_types':compiled['output_types'],
        'max_rows':10000,'max_document_bytes':8*1024*1024,
        'execution_authorized':False,'qa_passed':False,'release_ready':False}


def list_oracles(queue,task_id,run_id,specification_id):
    """Historical metadata only; recorded approval is not execution eligibility."""
    with queue.conn() as conn:
        scope=conn.execute('SELECT specification_id FROM platform.specification WHERE task_id=%s AND run_id=%s AND specification_id=%s',
                           (task_id,run_id,specification_id)).fetchone()
        if not scope:raise ValueError('ORACLE_SCOPE_NOT_FOUND')
        rows=conn.execute('''SELECT o.oracle_id,o.version,o.document_checksum,
            o.specification_checksum,o.naming_checksum,o.created_at,
            a.approval_id,a.created_at AS approved_at
            FROM platform.result_oracle o
            LEFT JOIN platform.result_oracle_approval a ON a.oracle_id=o.oracle_id
            AND a.document_checksum=o.document_checksum
            WHERE o.specification_id=%s ORDER BY o.version DESC''',(specification_id,)).fetchall()
    return {'items':[{**dict(row),'oracle_id':str(row['oracle_id']),
        'approval_id':str(row['approval_id']) if row['approval_id'] else None,
        'approval_recorded':row['approval_id'] is not None,
        'eligibility':'NOT_EVALUATED','qa_passed':False,'release_ready':False} for row in rows]}


def read_oracle(queue,task_id,run_id,specification_id,oracle_id):
    # Historical reads preserve old versions; not a check of execution eligibility.
    with queue.conn() as conn:
        row=conn.execute('SELECT o.* FROM platform.result_oracle o JOIN platform.specification s USING(specification_id) WHERE o.oracle_id=%s AND s.task_id=%s AND s.run_id=%s AND s.specification_id=%s',
                         (oracle_id,task_id,run_id,specification_id)).fetchone()
    if not row:raise ValueError('ORACLE_NOT_FOUND')
    return decrypt_oracle(run_id,specification_id,row)


def review_oracle(queue,task_id,run_id,specification_id,oracle_id,offset=0,limit=50):
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:
        raise ValueError('ORACLE_PAGE_INVALID')
    content=read_oracle(queue,task_id,run_id,specification_id,oracle_id)
    document=json.loads(content)
    # Browser JSON numbers cannot represent every BIGINT. All non-null cells are
    # display strings; these rows are never accepted as an execution/QA result.
    def cell(value):
        if value is None:return None
        if isinstance(value,bool):return 'true' if value else 'false'
        return str(value)
    rows=document['rows'];page=rows[offset:offset+limit]
    return {'oracle_id':str(oracle_id),'document_checksum':sha256(content).hexdigest(),
        'columns':document['columns'],'rows':[{key:cell(value) for key,value in row.items()} for row in page],
        'offset':offset,'limit':limit,'total_rows':len(rows),'has_more':offset+len(page)<len(rows),
        'view':'HISTORICAL_READ_ONLY','qa_passed':False,'release_ready':False}


def approve_oracle(queue,task_id,run_id,specification_id,oracle_id,document_checksum):
    with queue.conn() as conn:
        candidate=load_approved_candidate(queue,conn,task_id,run_id,specification_id)
        row=conn.execute('SELECT * FROM platform.result_oracle WHERE specification_id=%s ORDER BY version DESC LIMIT 1 FOR SHARE',(specification_id,)).fetchone()
        if not row or str(row['oracle_id'])!=str(oracle_id) or row['document_checksum']!=document_checksum:
            raise ValueError('CURRENT_ORACLE_CHECKSUM_REQUIRED')
        content=decrypt_oracle(run_id,specification_id,row)
        compiled=candidate['compiled']
        compare_oracle_document(content,[],document_checksum=document_checksum,
            specification_checksum=candidate['specification_checksum'],naming_checksum=compiled['specification']['naming']['checksum'])
        validate_oracle_schema(json.loads(content),compiled)
        approval=conn.execute('SELECT * FROM platform.result_oracle_approval WHERE oracle_id=%s',(oracle_id,)).fetchone()
        if not approval:
            operator=conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1 FOR SHARE').fetchone()
            if not operator:raise ValueError('OPERATOR_REQUIRED')
            approval=conn.execute('INSERT INTO platform.result_oracle_approval(approval_id,oracle_id,operator_id,document_checksum) VALUES(%s,%s,%s,%s) RETURNING *',
                (uuid4(),oracle_id,operator['operator_id'],document_checksum)).fetchone()
            queue.event(conn,run_id,'RESULT_ORACLE_APPROVED','QA_PREPARATION',{'oracle_id':str(oracle_id),'approval_id':str(approval['approval_id']),'version':row['version'],'document_checksum':document_checksum})
    return {'approval_id':str(approval['approval_id']),'oracle_id':str(oracle_id),'document_checksum':document_checksum,
            'status':'ORACLE_APPROVED_NOT_EXECUTED','qa_passed':False,'release_ready':False}
