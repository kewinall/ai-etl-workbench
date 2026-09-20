from unittest.mock import Mock
import pytest
import app.pilot_hop_worker as worker
from app.hop_dispatch import require_sa_trace


def test_no_request_no_ddl_or_hop(monkeypatch):
    monkeypatch.setattr(worker,'claim',Mock(return_value=None));prepare=Mock();monkeypatch.setattr(worker,'prepare_new_target',prepare)
    assert worker.run_once(Mock(),Mock())=={'status':'IDLE'}
    prepare.assert_not_called()


@pytest.mark.parametrize('failure',['prepare','hop','comparison',None])
def test_single_attempt_preserves_failure_without_retry(monkeypatch,failure):
    request=dict(task_id='t',run_id='r',specification_id='s',authorization_id='a')
    monkeypatch.setattr(worker,'claim',Mock(return_value=request))
    prepare=Mock(side_effect=ValueError('private') if failure=='prepare' else None,return_value={})
    hop=Mock(return_value={'status':'HOP_FAILED' if failure=='hop' else 'HOP_EXECUTED_QA_REQUIRED'})
    compare=Mock(side_effect=ValueError('private') if failure=='comparison' else None)
    finish=Mock()
    for name,value in [('prepare_new_target',prepare),('execute_once',hop),('record_bound_comparison',compare),('finish',finish),('vertica_executor',Mock())]:monkeypatch.setattr(worker,name,value)
    result=worker.run_once(Mock(),Mock())
    assert result['status']==('COMPLETED' if failure is None else 'NEEDS_REVIEW')
    assert prepare.call_count==1 and hop.call_count<=1 and compare.call_count<=1
    finish.assert_called_once()
    assert 'private' not in str(result)


def test_sa_trace_is_not_optional_or_unbound():
    with pytest.raises(ValueError,match='TRACE_REQUIRED'):require_sa_trace(None)
    sa=dict(provider='LOCAL_COPILOT',model='copilot/test',context_checksum='c'*64,run_id='r',
        input_json=dict(context={'input_checksum':'i'*64},prompt_checksum='p'*64,schema_checksum='s'*64),output_json={'trace':{}})
    with pytest.raises(ValueError,match='BINDING_CHANGED'):require_sa_trace(sa)
