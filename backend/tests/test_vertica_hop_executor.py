from pathlib import Path
from threading import Event
from hashlib import sha256
import pytest
from app.vertica_hop_executor import vertica_executor
from test_hop_connection_runtime import Repo, snapshot


def test_executor_passes_bound_metadata_and_only_child_secret(tmp_path, monkeypatch):
    data=snapshot()
    source=tmp_path/'source.csv';source.write_bytes(b'a\n1\n')
    hpl=tmp_path/'candidate.hpl';hpl.write_bytes(b'<pipeline><transform><name>target</name></transform></pipeline>')
    prepared={'directory':tmp_path,'source_path':source,'hpl_path':hpl,'binding':{
        'source_checksum':sha256(source.read_bytes()).hexdigest(),'hpl_checksum':sha256(hpl.read_bytes()).hexdigest(),'settings_checksum':data['checksum']}}
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    monkeypatch.setenv('DATABASE_PASSWORD','must-not-inherit')
    monkeypatch.setattr('app.vertica_hop_executor.check_target_claim',lambda *args: {})
    monkeypatch.setattr('app.vertica_hop_executor.require_empty_check',lambda *args: {})
    environments=[]
    def fake_cli(prepared, cancelled, **kwargs):
        assert kwargs['expected_nodes']==['target']
        assert kwargs['environment']['WORKBENCH_VERTICA_PASSWORD']=='synthetic-secret'
        assert 'DATABASE_PASSWORD' not in kwargs['environment']
        assert kwargs['environment']['HOP_SHARED_JDBC_FOLDERS']=='/opt/hop/lib/jdbc'
        assert 'synthetic-secret' not in (tmp_path/'metadata.json').read_text()
        environments.append(kwargs['environment'])
        return {'result':{'status':'COMPLETED'}}
    monkeypatch.setattr('app.vertica_hop_executor.run_hop_cli',fake_cli)
    executor=vertica_executor(Repo(),data)
    assert executor(prepared,Event(),lambda _:None)=={'status':'COMPLETED'}
    assert environments==[{}]
    with pytest.raises(FileExistsError):executor(prepared,Event(),lambda _:None)
