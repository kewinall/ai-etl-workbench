from uuid import uuid4
import pytest
from test_run_api import client
from app import comparison_store


def test_comparison_read_route_and_no_write_route(monkeypatch):
    calls=[]
    def listing(queue,task,run):
        calls.append((task,str(run)));return {'items':[],'qa_passed':False,'release_ready':False}
    monkeypatch.setattr(comparison_store,'list_comparisons',listing)
    run=str(uuid4());url=f'/api/tasks/test/runs/{run}/comparisons';api=client()
    assert api.get(url).json()=={'items':[],'qa_passed':False,'release_ready':False}
    assert calls==[('test',run)]
    assert api.post(url,json={'status':'MATCH'}).status_code==405


@pytest.mark.parametrize('error,status',[(ValueError('COMPARISON_RUN_NOT_FOUND'),404),(ValueError('private data'),422),(RuntimeError('private hostname'),503)])
def test_errors_are_masked(monkeypatch,error,status):
    def fail(*args):raise error
    monkeypatch.setattr(comparison_store,'list_comparisons',fail)
    response=client().get(f'/api/tasks/test/runs/{uuid4()}/comparisons')
    assert response.status_code==status and 'private' not in response.text


def test_public_evidence_rejects_extra_data_and_changed_checksum():
    from hashlib import sha256
    import json
    value={key:None for key in comparison_store.EVIDENCE_FIELDS}
    value.update(run_id='test',actual_provenance='NOT_VERIFIED',qa_passed=False,release_ready=False)
    digest=sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with pytest.raises(ValueError,match='INVALID'):
        comparison_store.checked_public_evidence({**value,'rows':['private data']},digest,'test')
    with pytest.raises(ValueError,match='CHANGED'):
        comparison_store.checked_public_evidence(value,'0'*64,'test')
