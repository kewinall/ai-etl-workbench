import pytest
from app.qa_approval import approval_state
from app.sa_contract import digest


def sample():
    binding={'run_id':'r','invocation_id':'i','review_checksum':'a'*64}
    binding['checksum']=digest(binding)
    return dict(binding=binding,binding_checksum=binding['checksum'],run_id='r',invocation_id='i',
        approval_id='a',created_at='now'),binding


def test_current_approval_and_history_are_distinct():
    saved,binding=sample()
    assert approval_state(saved,binding)['status']=='APPROVED_CURRENT'
    stale=approval_state(saved,None)
    assert stale['status']=='STALE_APPROVAL' and not stale['qa_approved']
    assert stale['approval']['approval_id']=='a' and not stale['release_ready']


def test_no_approval_is_not_approved():
    _,binding=sample()
    assert approval_state(None,binding)['status']=='AWAITING_CONFIRMATION'
    assert approval_state(None,None)['status']=='NOT_ELIGIBLE'


def test_corrupt_approval_never_shown_as_valid():
    saved,binding=sample();saved['binding_checksum']='0'*64
    with pytest.raises(ValueError,match='QA_APPROVAL_INTEGRITY_ERROR'):approval_state(saved,binding)
