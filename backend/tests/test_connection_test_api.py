from contextlib import contextmanager
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.connection_test_api import probe,create_connection_test_router

class Repo:
    def setting(self,*args):return {'etl_qa':dict(connection_id='test-db',host='synthetic',port=5433,database='db',user='reader',tlsmode='require')}
    def secret_version(self,*args):return 'version-1'
    def read_secret_at_version(self,ref,version):
        assert ref=='connection:test-db' and version=='version-1'
        return 'synthetic-secret'

def test_select_one_only_and_no_runtime_authorization(monkeypatch):
    calls=[]
    class DB:
        def cursor(self):return self
        def execute(self,sql):calls.append(sql)
        def fetchone(self):return [1]
    @contextmanager
    def connect(**config):
        assert config['host']=='synthetic' and config['password']=='synthetic-secret'
        assert config['connection_timeout']==10 and config['tlsmode']=='require'
        yield DB()
    monkeypatch.setattr('app.connection_test_api.vertica_python.connect',connect)
    result=probe(Repo(),'test-db')
    assert calls==['SELECT 1']
    assert result['status']=='CONNECTED' and result['execution_authorized'] is False
    assert 'synthetic' not in str(result)

def test_wrong_identity_never_connects(monkeypatch):
    monkeypatch.setattr('app.connection_test_api.vertica_python.connect',lambda **kwargs:pytest.fail('no fallback'))
    with pytest.raises(ValueError):probe(Repo(),'other')

def test_errors_do_not_reveal_connection_or_secret(monkeypatch):
    def fail(**kwargs):raise RuntimeError('host=private.example password=synthetic-secret')
    monkeypatch.setattr('app.connection_test_api.vertica_python.connect',fail)
    app=FastAPI();app.include_router(create_connection_test_router(Repo()))
    response=TestClient(app).post('/api/settings/connections/test-db/test')
    assert response.status_code==409
    assert 'private.example' not in response.text and 'synthetic-secret' not in response.text
