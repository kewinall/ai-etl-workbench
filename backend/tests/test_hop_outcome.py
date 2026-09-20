import pytest
from app.hop_outcome import validated_hop_outcome


@pytest.mark.parametrize('status,exit_code,errors,expected', [
    ('COMPLETED',0,0,'HOP_EXECUTED_QA_REQUIRED'),
    ('FAILED',1,0,'HOP_EXECUTION_FAILED'),
    ('FAILED',0,1,'HOP_EXECUTION_FAILED'),
    ('UNKNOWN',None,None,'HOP_RESULT_UNKNOWN'),
])
def test_engine_result_never_grants_qa_or_release(status,exit_code,errors,expected):
    outcome, evidence = validated_hop_outcome(dict(status=status,exit_code=exit_code,errors=errors,log_checksum='a'*64))
    assert outcome == expected
    assert evidence['automatic_retry_allowed'] is False
    assert evidence['qa_passed'] is False
    assert evidence['release_ready'] is False


@pytest.mark.parametrize('changes', [
    {'status':'SUCCEEDED'}, {'exit_code':1}, {'errors':1},
    {'errors':False}, {'exit_code':-1}, {'log_checksum':None},
    {'log_checksum':'/private/log'}, {'exception':'password=secret'},
    {'status':'FAILED'},
])
def test_inconsistent_or_unbounded_evidence_rejected(changes):
    result = dict(status='COMPLETED',exit_code=0,errors=0,log_checksum='a'*64)
    result.update(changes)
    with pytest.raises(ValueError,match='INVALID_HOP_OUTCOME'):
        validated_hop_outcome(result)
