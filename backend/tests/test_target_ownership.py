from contextlib import contextmanager
from unittest.mock import Mock
import pytest
from app.target_ownership import check_target_claim, target_rebuild_guard


class Repo:
    def __init__(self, *rows):
        self.connection=Mock()
        self.connection.execute.return_value.fetchone.side_effect=rows
    @contextmanager
    def conn(self):
        yield self.connection


def sample():
    claim=dict(run_id='r',project_id='p',task_id='t',schema_name='ai_sample',table_name='result',
        settings_checksum='s',specification_checksum='c',hpl_checksum='h',ddl_checksum='d',
        registry_created_at=1,registry_rebuilt_at=2)
    registry=dict(task_id='t',ddl_checksum='d',created_at=1,rebuilt_at=2)
    binding={k:claim[k] for k in ('run_id','settings_checksum','specification_checksum','hpl_checksum')}
    return claim,registry,binding


def test_registered_unchanged_claim_is_required():
    claim,registry,binding=sample()
    assert check_target_claim(Repo(claim,registry),binding)==claim
    with pytest.raises(ValueError,match='PRE_EXECUTION_TARGET_CLAIM_REQUIRED'):
        check_target_claim(Repo(None),binding)


@pytest.mark.parametrize('field',['settings_checksum','specification_checksum','hpl_checksum'])
def test_different_binding_is_rejected(field):
    claim,registry,binding=sample();binding[field]='changed'
    with pytest.raises(ValueError,match='TARGET_CLAIM_BINDING_CHANGED'):
        check_target_claim(Repo(claim),binding)


@pytest.mark.parametrize('field',['task_id','ddl_checksum','created_at','rebuilt_at'])
def test_rebuilt_or_reassigned_table_is_rejected(field):
    claim,registry,binding=sample();registry[field]='changed'
    with pytest.raises(ValueError,match='REGISTERED_TARGET_CHANGED'):
        check_target_claim(Repo(claim,registry),binding)


def test_rebuild_guard_rejects_claim_before_entering_body():
    with pytest.raises(ValueError,match='RUN_TARGET_CANNOT_BE_REBUILT'):
        with target_rebuild_guard(Repo({'exists':True}),'ai_sample','result'):
            pytest.fail('rebuild body must not run')
