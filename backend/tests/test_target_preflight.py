from contextlib import contextmanager
from unittest.mock import Mock, MagicMock
import pytest
from app import target_preflight
from test_hop_connection_runtime import Repo as SecretRepo, snapshot


class Repo(SecretRepo):
    def __init__(self, binding):
        self.connection=Mock()
        self.connection.execute.return_value.fetchone.side_effect=[{'run_id':'run'}, {**binding,'fresh':True}]
    @contextmanager
    def conn(self):yield self.connection


@pytest.mark.parametrize('nonempty',[False,True])
def test_bound_empty_check_records_only_empty_target(nonempty,monkeypatch):
    data=snapshot();binding={'run_id':'run','settings_checksum':data['checksum'],'hpl_checksum':'h'*64}
    repo=Repo(binding)
    claim={'schema_name':'ai_sample','table_name':'test_target','task_id':'task','project_id':'project'}
    monkeypatch.setattr(target_preflight,'check_target_claim',lambda *args:claim)
    database=MagicMock();cursor=database.__enter__.return_value.cursor.return_value
    cursor.fetchone.return_value=[1] if nonempty else None
    connect=Mock(return_value=database);monkeypatch.setattr(target_preflight.vertica_python,'connect',connect)
    if nonempty:
        with pytest.raises(ValueError,match='PILOT_TARGET_NOT_EMPTY'):
            target_preflight.verify_empty_target(repo,binding,data)
        repo.connection.execute.assert_not_called()
    else:
        assert target_preflight.verify_empty_target(repo,binding,data)['status']=='EMPTY_TARGET_CONFIRMED_NOT_EXECUTED'
        assert 'synthetic-secret' not in repr(repo.connection.execute.call_args_list)
    cursor.execute.assert_called_once_with('SELECT 1 FROM "ai_sample"."test_target" LIMIT 1;')
    assert connect.call_args.kwargs['connection_timeout']==10
    assert connect.call_args.kwargs['password']=='synthetic-secret'


@pytest.mark.parametrize('row',[None,{'fresh':False},{'fresh':True,'settings_checksum':'changed','hpl_checksum':'h'}])
def test_missing_stale_or_changed_check_is_rejected(row):
    binding={'run_id':'run','settings_checksum':'s','hpl_checksum':'h'}
    repo=Repo(binding);repo.connection.execute.return_value.fetchone.side_effect=[row]
    with pytest.raises(ValueError,match='FRESH_EMPTY_TARGET_CHECK_REQUIRED'):
        target_preflight.require_empty_check(repo,binding)


@pytest.mark.parametrize('claim',[{'schema_name':'business','table_name':'safe'},
    {'schema_name':'ai_sample','table_name':'safe; DROP TABLE t'},
    {'schema_name':'ai_sample','table_name':None}])
def test_non_pilot_or_injected_target_rejected(claim):
    with pytest.raises(ValueError,match='INVALID_CLAIMED_TARGET'):
        target_preflight.empty_target_sql(claim)
