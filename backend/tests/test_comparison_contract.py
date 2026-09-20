from hashlib import sha256
import json
from uuid import uuid4
import pytest
from app.comparison_store import checked_public_evidence


def evidence():
    return dict(version=1,comparison='EXACT_MULTISET',status='MATCH',expected_count=1,actual_count=1,
        missing_count=0,unexpected_count=0,expected_checksum='a'*64,actual_checksum='a'*64,
        qa_passed=False,release_ready=False,oracle_document_checksum='b'*64,specification_checksum='c'*64,
        naming_checksum='d'*64,run_id=str(uuid4()),oracle_id=str(uuid4()),execution_binding_checksum='e'*64,
        hop_event_id=1,hop_log_checksum='f'*64,actual_provenance='NOT_VERIFIED')


def check(value):
    checksum=sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return checked_public_evidence(value,checksum,value['run_id'])


def test_valid_match_and_mismatch():
    value=evidence();assert check(value)==value
    value.update(status='MISMATCH',missing_count=1,unexpected_count=1,actual_checksum='0'*64)
    assert check(value)==value


@pytest.mark.parametrize('change',[
    {'version':True},{'comparison':'COUNT_ONLY'},{'status':None},{'status':'MISMATCH'},
    {'expected_count':True},{'actual_count':1.0},{'actual_count':-1},{'actual_count':10001},
    {'missing_count':2},{'missing_count':1},{'unexpected_count':1},{'hop_event_id':False},
    {'hop_event_id':0},{'hop_log_checksum':'private text'},{'oracle_id':'not-an-id'},
    {'actual_checksum':'0'*64},{'qa_passed':True},{'actual_provenance':'VERIFIED'},
])
def test_invalid_even_with_recalculated_checksum(change):
    with pytest.raises(ValueError,match='COMPARISON_EVIDENCE_INVALID'):check({**evidence(),**change})
