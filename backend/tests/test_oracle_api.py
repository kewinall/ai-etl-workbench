from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.oracle_api import create_oracle_router
from app import oracle_store


def setup():
    app=FastAPI();app.include_router(create_oracle_router(object()))
    return TestClient(app),f'/api/tasks/test/runs/{uuid4()}/specifications/{uuid4()}/oracles'


def test_confirmation_required_before_store(monkeypatch):
    def forbidden(*args):raise AssertionError('must not invoke')
    monkeypatch.setattr(oracle_store,'approve_oracle',forbidden)
    client,url=setup()
    for confirmation in [False,'true',1,None]:
        response=client.post(url+'/'+str(uuid4())+'/approve',json={'document_checksum':'a'*64,'confirmed':confirmation})
        assert response.status_code==422


def test_save_scope_and_safe_response(monkeypatch):
    calls=[]
    def save(queue,*args):
        calls.append(args)
        return {'oracle_id':str(uuid4()),'status':'ORACLE_SAVED_NOT_APPROVED','qa_passed':False,'release_ready':False}
    monkeypatch.setattr(oracle_store,'save_oracle',save)
    client,url=setup();response=client.post(url,json={'document':'synthetic document'})
    assert response.status_code==201
    assert calls[0][0]=='test' and calls[0][-1]==b'synthetic document'
    assert 'synthetic document' not in response.text
    assert response.json()['qa_passed'] is False


@pytest.mark.parametrize('error,status',[(ValueError('private row'),409),(RuntimeError('private connection'),503)])
def test_errors_never_expose_private_exception(monkeypatch,error,status):
    def fail(*args):raise error
    monkeypatch.setattr(oracle_store,'save_oracle',fail)
    client,url=setup();response=client.post(url,json={'document':'{}'})
    assert response.status_code==status
    assert 'private' not in response.text
