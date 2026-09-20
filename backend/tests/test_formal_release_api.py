from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.formal_release_api import create_formal_release_router
from app import release_store


def test_release_http_requires_confirmation_and_rechecks_download(monkeypatch):
    app=FastAPI();app.include_router(create_formal_release_router(None,None));api=TestClient(app)
    base=f'/api/tasks/test/runs/{uuid4()}/release';calls=[]
    monkeypatch.setattr(release_store,'prepare',lambda *a,**kw:calls.append(a) or {'release_ready':False})
    for confirmed,code in [(False,409),('true',422)]:
        assert api.post(base+'/candidate',json={'confirmed':confirmed,'qa_binding_checksum':'a'*64}).status_code==code
    assert not calls
    assert api.post(base+'/candidate',json={'confirmed':True,'qa_binding_checksum':'a'*64}).status_code==200
    assert len(calls)==1
    def stale(*a,**kw):raise ValueError('RELEASE_APPROVAL_STALE')
    monkeypatch.setattr(release_store,'download',stale)
    assert api.get(base+f'/{uuid4()}/download').status_code==409
    monkeypatch.setattr(release_store,'download',lambda *a,**kw:b'exact approved bytes')
    response=api.get(base+f'/{uuid4()}/download')
    assert response.content==b'exact approved bytes'
    assert response.headers['cache-control']=='no-store'


def test_portability_has_no_http_proof_submission():
    app=FastAPI();app.include_router(create_formal_release_router(None,None))
    assert not any('portability' in route.path for route in app.routes)


def test_replay_disabled_by_default(monkeypatch):
    from app.release_replay_worker import destination
    import pytest
    monkeypatch.delenv('WORKBENCH_PORTABILITY_ENABLED',raising=False)
    with pytest.raises(ValueError,match='PORTABILITY_DISABLED'):destination()
