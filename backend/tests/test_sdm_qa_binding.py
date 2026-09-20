from contextlib import nullcontext
from unittest.mock import Mock
import pytest
from app.sdm_qa_binding import bind_sdm_qa


def setup(monkeypatch,row=None,existing=None):
    monkeypatch.setattr('app.sdm_qa_binding.verify_document',Mock())
    conn=Mock();conn.execute.side_effect=[Mock(fetchone=lambda:row),Mock(fetchone=lambda:existing),Mock()]
    queue=Mock();queue.conn.return_value=nullcontext(conn)
    monkeypatch.setattr('app.sdm_qa_binding.load_delivery_context',lambda *a,**k:
        dict(qa_binding_checksum='q',specification_id='s',specification_checksum='h',qa_approval_id='a'))
    return queue,conn


def test_wrong_qa_version_never_queries_candidate(monkeypatch):
    queue,conn=setup(monkeypatch)
    with pytest.raises(ValueError,match='SDM_QA_VERSION_CONFLICT'):bind_sdm_qa(queue,'t','r','s','wrong')
    conn.execute.assert_not_called()


def test_missing_candidate_rejected(monkeypatch):
    queue,conn=setup(monkeypatch)
    with pytest.raises(ValueError,match='SDM_QA_CANDIDATE_MISMATCH'):bind_sdm_qa(queue,'t','r','s','q')
    assert conn.execute.call_count==1


@pytest.mark.parametrize('existing',[None,{'qa_approval_id':'a'}])
def test_link_is_idempotent_and_not_release(monkeypatch,existing):
    queue,conn=setup(monkeypatch,dict(status='CANDIDATE_NOT_RELEASED',specification_id='s',specification_checksum='h'),existing)
    result=bind_sdm_qa(queue,'t','r','s','q')
    assert result['release_ready'] is False
    assert queue.event.call_count==(0 if existing else 1)
