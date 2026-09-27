"""Correction permission boundaries; model/context fixtures are not ETL acceptance."""
from copy import deepcopy
from unittest.mock import Mock
import pytest
from app.qa_revision import offer


@pytest.fixture
def setup(monkeypatch):
    run=dict(run_id='run',task_id='task',state='NEEDS_REVIEW',phase='HOP_EXECUTION',
             write_started=True,lease_token=None,outcome_code='HOP_EXECUTED_QA_REQUIRED',input_checksum='i')
    row=dict(invocation_id='qa',status='VALIDATED_NOT_APPROVED',context_checksum='c',
             input_json={'comparison_id':'comparison'},output_json={'review_checksum':'r'})
    record=Mock(return_value={'review':{'status':'NEEDS_REVIEW'}})
    context=Mock(return_value={'context':{'context_checksum':'c'}})
    monkeypatch.setattr('app.qa_journal.public_record',record)
    monkeypatch.setattr('app.qa_context.load_qa_context',context)
    conn=Mock()
    conn.execute.return_value.fetchone.side_effect=[None,None,None,row]
    return run,row,record,context,conn


@pytest.mark.parametrize('status',['FAIL','NEEDS_REVIEW'])
def test_bound_offer_without_execution(setup,status):
    run,row,record,context,conn=setup
    record.return_value['review']['status']=status
    before=deepcopy(run)
    result=offer(None,conn,run)
    assert result['invocation_id']=='qa' and len(result['checksum'])==64
    assert result['automatic_retry_allowed'] is False and run==before
    assert all(call.args[0].startswith('SELECT') for call in conn.execute.call_args_list)


@pytest.mark.parametrize('field,value',[
    ('state','RUNNING'),('state','CANCELLED'),('phase','REQUIREMENT_GATE'),
    ('write_started',False),('lease_token','active'),('outcome_code','HOP_RESULT_UNKNOWN'),
    ('outcome_code','HOP_EXECUTION_FAILED')])
def test_wrong_execution_state_denied(setup,field,value):
    run,_,_,_,conn=setup
    run[field]=value
    assert offer(None,conn,run) is None
    conn.execute.assert_not_called()


@pytest.mark.parametrize('index',[0,1,2])
def test_child_approval_or_pending_dispatch_denied(setup,index):
    run,_,_,_,conn=setup
    conn.execute.return_value.fetchone.side_effect=[None]*index+[{'exists':1}]
    assert offer(None,conn,run) is None


@pytest.mark.parametrize('status',['QA_RESERVED','QA_OUTCOME_UNKNOWN','STALE_RESULT_NEEDS_REVIEW'])
def test_nonfinal_qa_denied(setup,status):
    run,row,record,_,conn=setup
    row['status']=status
    assert offer(None,conn,run) is None
    record.assert_not_called()


def test_pass_is_not_correction_permission(setup):
    run,_,record,_,conn=setup
    record.return_value['review']['status']='PASS'
    assert offer(None,conn,run) is None


def test_context_drift_denied(setup):
    run,_,_,context,conn=setup
    context.return_value['context']['context_checksum']='changed'
    assert offer(None,conn,run) is None


def test_corrupt_history_denied(setup):
    run,_,record,_,conn=setup
    record.side_effect=ValueError('QA_HISTORY_INTEGRITY_ERROR')
    assert offer(None,conn,run) is None
