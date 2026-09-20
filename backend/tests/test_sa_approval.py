from copy import deepcopy
from uuid import uuid4
from unittest.mock import Mock
import pytest
from test_etl_specification import design
from app.sa_contract import build_sa_context,digest
from app.sa_approval import handoff_binding,approve
from app.run_queue import RunConflict


def fixture():
    _,run,_=design();run.update(project_id=uuid4(),outcome_code='SA_REVIEW_REQUIRES_APPROVAL')
    context=build_sa_context(run)
    review=dict(version=1,run_id=str(run['run_id']),input_checksum=run['input_checksum'],context_checksum=context['context_checksum'],
        status='READY_FOR_REVIEW',summary='Synthetic handoff unit fixture',evidence_ids=['requirement'],issues=[])
    record=dict(invocation_id=uuid4(),run_id=run['run_id'],task_id=run['task_id'],role='pilot_sa',status='VALIDATED_NOT_APPROVED',
        input_json={'context':context},context_checksum=context['context_checksum'],output_json={'review':review,'output_checksum':digest(review)})
    return run,record


def test_handoff_is_version_bound_and_not_execution_approval():
    run,record=fixture();binding=handoff_binding(run,record)
    assert binding['review_checksum']==digest(record['output_json']['review'])
    assert binding['checksum']==digest({k:v for k,v in binding.items() if k!='checksum'})


@pytest.mark.parametrize('change',[{'matches_current':False},{'write_started':True},{'state':'RUNNING'},
    {'approval':None},{'outcome_code':'SA_REQUIREMENT_NEEDS_INPUT'}])
def test_ineligible_run_is_rejected(change):
    run,record=fixture()
    with pytest.raises(RunConflict):handoff_binding({**run,**change},record)


@pytest.mark.parametrize('field',['status','context','checksum','review'])
def test_stale_or_tampered_record_rejected(field):
    run,record=fixture();record=deepcopy(record)
    if field=='status':record['status']='STALE_RESULT_NEEDS_REVIEW'
    if field=='context':record['input_json']['context']['context_checksum']='0'*64
    if field=='checksum':record['output_json']['output_checksum']='0'*64
    if field=='review':record['output_json']['review']['status']='NEEDS_INPUT'
    with pytest.raises(ValueError):handoff_binding(run,record)


def test_explicit_human_confirmation_required():
    queue=Mock()
    with pytest.raises(ValueError,match='CONFIRMATION_REQUIRED'):approve(queue,'task',uuid4(),'a'*64)
    queue.conn.assert_not_called()


def test_history_does_not_become_stale_just_because_execution_advanced():
    run,record=fixture();before=handoff_binding(run,record)
    run.update(state='RUNNING',write_started=True,outcome_code=None)
    assert handoff_binding(run,record,require_pending=False)==before
    with pytest.raises(RunConflict):handoff_binding(run,record)
