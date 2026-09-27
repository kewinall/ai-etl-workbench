"""Actual isolated PostgreSQL roundtrip, not Hop/Vertica/QA acceptance."""
from hashlib import sha256
import json
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from app import specification_store as store
from app.etl_specification import validate_specification
from app.oracle_store import save_oracle, read_oracle, approve_oracle, oracle_editor_context, review_oracle
from app.comparison_store import checked_public_evidence, list_comparisons
from app.result_oracle import compare_oracle_document
from test_comparison_contract import evidence
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from test_source_order_compilation import ordered_design


def test_ordered_oracle_encrypted_roundtrip_and_comparison_history(context):
    queue,task_id,run,spec,naming,api=prepared(context,design_factory=ordered_design)
    rid=run['run_id']
    # Public V3 execution remains closed pending full QA/release integration.
    assert api.post(f'/api/tasks/{task_id}/runs/{rid}/specifications',json=spec).status_code==422
    with queue.conn() as conn:
        current,names=store.context(queue,conn,task_id,rid)
        checked=validate_specification(spec,current,names)
        assert checked['status']=='VALIDATED_NOT_APPROVED',checked
        saved=store.save(queue,conn,task_id,rid,checked)
        sid=saved['specification_id']
        store.approve(queue,conn,task_id,rid,sid,saved['content_checksum'])
    editor=oracle_editor_context(queue,task_id,rid,sid)
    assert editor['version']==2 and editor['comparison']=='EXACT_SOURCE_SEQUENCE'
    assert editor['ordinal_column']=='source_position'
    doc={k:editor[k] for k in ('version','comparison','ordinal_column','specification_checksum','naming_checksum','columns')}
    doc['rows']=[{'category':'Z','amount':'30','source_position':1},
                 {'category':'A','amount':'10','source_position':2}]
    content=json.dumps(doc).encode()
    oracle=save_oracle(queue,task_id,rid,sid,content)
    assert save_oracle(queue,task_id,rid,sid,content)==oracle
    approve_oracle(queue,task_id,rid,sid,oracle['oracle_id'],oracle['document_checksum'])
    assert read_oracle(queue,task_id,rid,sid,oracle['oracle_id'])==content
    review=review_oracle(queue,task_id,rid,sid,oracle['oracle_id'])
    assert review['comparison']=='EXACT_SOURCE_SEQUENCE'
    assert [r['source_position'] for r in review['rows']]==['1','2']
    assert review['qa_passed'] is review['release_ready'] is False
    with queue.conn() as conn:
        row=conn.execute('SELECT * FROM platform.result_oracle WHERE oracle_id=%s',(oracle['oracle_id'],)).fetchone()
        assert content not in bytes(row['cipher_text'])
    old={k:v for k,v in doc.items() if k not in ('comparison','ordinal_column')}
    old['version']=1
    with pytest.raises(ValueError,match='ORACLE_ORDER_CONTRACT_MISMATCH'):
        save_oracle(queue,task_id,rid,sid,json.dumps(old).encode())
    # Store explicit synthetic unverified comparison packets. This does not
    # simulate or claim completed execution or result provenance.
    from decimal import Decimal
    actual=[{**r,'amount':Decimal(r['amount'])} for r in doc['rows']]
    packets=[]
    for rows in (actual,list(reversed(actual))):
        result=compare_oracle_document(content,rows,document_checksum=oracle['document_checksum'],
            specification_checksum=doc['specification_checksum'],naming_checksum=doc['naming_checksum'])
        packet={**evidence(),**result,'run_id':str(rid),'oracle_id':oracle['oracle_id']}
        digest=sha256(json.dumps(packet,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        checked_public_evidence(packet,digest,rid)
        cid=uuid4()
        with queue.conn() as conn:
            conn.execute('INSERT INTO platform.task_run_result_comparison(comparison_id,run_id,checksum,evidence) VALUES(%s,%s,%s,%s)',
                         (cid,rid,digest,Jsonb(packet)))
        packets.append((cid,packet))
    history=list_comparisons(queue,task_id,rid)
    assert [r['evidence'] for r in history['items']]==[packet for _,packet in packets]
    assert all(r['provenance'] is None for r in history['items'])
    assert [r['evidence']['position_mismatch_count'] for r in history['items']]==[0,2]
    with pytest.raises(psycopg.Error):
        with queue.conn() as conn:
            conn.execute("UPDATE platform.task_run_result_comparison SET evidence='{}' WHERE comparison_id=%s",(packets[0][0],))
