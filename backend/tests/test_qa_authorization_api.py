from unittest.mock import Mock
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import app.qa_authorization_api as module


def fixture(monkeypatch):
    run=str(uuid4()); comparison=str(uuid4())
    offer=dict(eligible=True,dispatch_enabled=True,comparison_id=comparison,context_checksum='a'*64,
        prompt_checksum='b'*64,schema_checksum='c'*64,model='copilot/test',invocation=None)
    monkeypatch.setattr(module,'offer',Mock(return_value=offer))
    journal=Mock(); journal.reserve.return_value={'status':'QA_RESERVED','invocation_id':str(uuid4())}
    monkeypatch.setattr(module,'QAJournal',Mock(return_value=journal))
    app=FastAPI();app.include_router(module.create_qa_authorization_router(Mock()))
    return TestClient(app),f'/api/tasks/t/runs/{run}/qa-authorization',offer,journal


@pytest.mark.parametrize('change',['confirmed','model','context_checksum','comparison_id','disabled'])
def test_changed_offer_or_no_consent_does_not_reserve(monkeypatch,change):
    api,url,offer,journal=fixture(monkeypatch)
    body={key:offer[key] for key in ('model','context_checksum','prompt_checksum','schema_checksum','comparison_id')}
    body['confirmed']=True
    if change=='confirmed':body[change]=False
    elif change=='model':body[change]='copilot/other'
    elif change=='comparison_id':body[change]=str(uuid4())
    elif change=='disabled':offer['dispatch_enabled']=False
    else:body[change]='0'*64
    assert api.post(url,json=body).status_code==409
    journal.reserve.assert_not_called()


def test_authorization_only_reserves_and_get_is_read_only(monkeypatch):
    api,url,offer,journal=fixture(monkeypatch)
    assert api.get(url).status_code==200
    journal.reserve.assert_not_called()
    body={key:offer[key] for key in ('model','context_checksum','prompt_checksum','schema_checksum','comparison_id')}
    response=api.post(url,json={**body,'confirmed':True})
    assert response.status_code==200 and response.json()['status']=='QA_RESERVED'
    journal.reserve.assert_called_once()
