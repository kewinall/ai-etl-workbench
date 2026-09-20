from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from unittest.mock import Mock
import pytest
from app import bound_comparison as bc
from app.target_preflight import empty_target_sql


class Queue:
    def __init__(self,rows,writes):
        self.connection=Mock()
        self.connection.execute.return_value.fetchone.side_effect=rows
        self.connection.execute.return_value.fetchall.return_value=writes
    @contextmanager
    def conn(self):yield self.connection


@pytest.mark.parametrize('change',['none','missing','late','sql','settings','task'])
def test_capture_requires_prewrite_target_and_matching_checks(change,monkeypatch):
    now=datetime.now(timezone.utc)
    claim=dict(task_id='task',project_id='project',schema_name='ai_sample',table_name='target',created_at=now)
    empty=dict(task_id='task',project_id='project',created_at=now+timedelta(seconds=1),
        settings_checksum='s',hpl_checksum='h',sql_checksum=sha256(empty_target_sql(claim).encode()).hexdigest())
    if change=='missing':empty=None
    elif change=='late':empty['created_at']=now+timedelta(seconds=3)
    elif change=='sql':empty['sql_checksum']='changed'
    elif change=='settings':empty['settings_checksum']='changed'
    elif change=='task':empty['task_id']='other'
    queue=Queue([{'settings_snapshot':{'checksum':'s'}},{'binding':{'settings_checksum':'s','hpl_checksum':'h'}},empty],
        [{'created_at':now+timedelta(seconds=2)}])
    monkeypatch.setattr(bc,'load_bound_result_query',lambda *args:({'checksum':'q'},{'binding_checksum':'b'}))
    monkeypatch.setattr(bc,'check_target_claim',lambda *args:claim)
    if change=='none':
        assert bc.capture_binding(queue,None,'task','run')[2]=={'checksum':'s'}
    else:
        with pytest.raises(ValueError,match='RESULT_TARGET_PROVENANCE'):
            bc.capture_binding(queue,None,'task','run')


def test_unproven_target_never_opens_connection(monkeypatch):
    monkeypatch.setattr(bc,'capture_binding',Mock(side_effect=ValueError('RESULT_TARGET_PROVENANCE_REQUIRED')))
    connect=Mock();monkeypatch.setattr(bc.vertica_python,'connect',connect)
    with pytest.raises(ValueError,match='RESULT_TARGET_PROVENANCE_REQUIRED'):
        bc.record_bound_comparison(None,None,'task','run')
    connect.assert_not_called()
