from uuid import uuid4
from unittest.mock import Mock
import pytest
from test_run_api import client


def test_offer_and_confirmation_are_bound_to_run(monkeypatch):
    identity=uuid4();checksum='a'*64
    offer=Mock(return_value={'binding':{'checksum':checksum},'release_ready':False})
    save=Mock(return_value={'qa_approved':True,'release_ready':False})
    monkeypatch.setattr('app.qa_approval.read_approval',offer)
    monkeypatch.setattr('app.qa_approval.approve_review',save)
    api=client();url=f'/api/tasks/test/runs/{identity}/qa-approval'
    assert api.get(url).json()=={'binding':{'checksum':checksum},'release_ready':False}
    response=api.post(url,json={'confirmed':True,'binding_checksum':checksum})
    assert response.status_code==200 and response.json()['release_ready'] is False
    assert save.call_args.args[1:]==('test',identity,checksum)
    assert save.call_args.kwargs=={'confirmed':True}


@pytest.mark.parametrize('payload',[{'confirmed':'true','binding_checksum':'a'*64},
    {'confirmed':True,'binding_checksum':'bad'},
    {'confirmed':True,'binding_checksum':'a'*64,'release_ready':True}])
def test_invalid_confirmation_never_reaches_store(monkeypatch,payload):
    save=Mock();monkeypatch.setattr('app.qa_approval.approve_review',save)
    assert client().post(f'/api/tasks/test/runs/{uuid4()}/qa-approval',json=payload).status_code==422
    save.assert_not_called()


@pytest.mark.parametrize('error,status',[(ValueError('QA_APPROVAL_VERSION_CONFLICT'),409),
    (ValueError('private host'),422),(RuntimeError('private password'),503)])
def test_errors_are_safe_and_conflict_is_explicit(monkeypatch,error,status):
    monkeypatch.setattr('app.qa_approval.approve_review',Mock(side_effect=error))
    result=client().post(f'/api/tasks/test/runs/{uuid4()}/qa-approval',json={'confirmed':True,'binding_checksum':'a'*64})
    assert result.status_code==status and 'private' not in result.text
