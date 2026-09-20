from datetime import datetime,timezone
from unittest.mock import Mock
import pytest
from pydantic import ValidationError
from app.execution_reconciliation import offer,close
from app.run_api import ReconcileExecution
from app.run_queue import RunConflict


def run():
    return dict(run_id='r',task_id='t',project_id='p',state='NEEDS_REVIEW',phase='HOP_EXECUTION',
        write_started=True,lease_token=None,outcome_code='HOP_RESULT_UNKNOWN',
        input_checksum='a'*64,settings_snapshot={'checksum':'b'*64},updated_at=datetime.now(timezone.utc))


@pytest.mark.parametrize('change',[{'state':'RUNNING'},{'write_started':False},{'phase':'REQUIREMENT_GATE'},
    {'lease_token':'live'},{'outcome_code':'HOP_EXECUTED_QA_REQUIRED'}])
def test_offer_rejects_ineligible(change):
    with pytest.raises(RunConflict):offer({**run(),**change})


def test_binding_pins_original_outcome_and_settings():
    row=run();current=offer(row)
    assert current['checksum']!=offer({**row,'settings_snapshot':{'checksum':'c'*64}})['checksum']
    assert current['outcome_code']=='HOP_RESULT_UNKNOWN'


@pytest.mark.parametrize('key',['confirmed','engine_stopped','target_checked'])
def test_confirmation_requires_explicit_true(key):
    queue=Mock();flags=dict(confirmed=True,engine_stopped=True,target_checked=True);flags[key]=False
    with pytest.raises(ValueError,match='CONFIRMATION_REQUIRED'):close(queue,'t','r','a'*64,'b'*64,0,**flags)
    queue.conn.assert_not_called()


@pytest.mark.parametrize('change',[{'observed_row_count':True},{'observed_row_count':-1},{'engine_stopped':'true'},
    {'evidence_sha256':'bad'},{'unexpected':'value'}])
def test_api_rejects_coercions_and_extra_fields(change):
    with pytest.raises(ValidationError):ReconcileExecution(**{**dict(binding_checksum='a'*64,evidence_sha256='b'*64,
        observed_row_count=0,engine_stopped=True,target_checked=True,confirmed=True),**change})
