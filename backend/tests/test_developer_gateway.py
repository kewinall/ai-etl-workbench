from unittest.mock import Mock
import pytest
from test_developer_contract import fixture
from app.developer_gateway import complete_developer,DeveloperInvocationError


def setup():
    proposal,captured=fixture()
    captured['run']['settings_snapshot']['model_routes']={'etl_specification':'copilot/test-model'}
    profile={'enabled':True,'provider_type':'LOCAL_COPILOT','model_routes':{'etl_specification':'test-model'}}
    return proposal,captured,profile


def native(proposal):
    def call(payload,model,*,before_call):
        before_call()
        return proposal,dict(provider='LOCAL_COPILOT',model=model,run_id=payload['context']['run_id'],
            input_checksum=payload['context']['input_checksum'],context_checksum=payload['context']['context_checksum'],
            prompt_checksum=payload['prompt_checksum'],schema_checksum=payload['schema_checksum'],
            usage={'output_tokens':123,'cli_sessions':1,'automatic_retries':0,'tool_execution_count':0})
    return call


def test_native_adapter_uses_exact_route_and_one_call():
    proposal,captured,profile=setup();call=Mock(side_effect=native(proposal));guard=Mock()
    result,trace=complete_developer(captured,profile,native_completion=call,before_call=guard)
    assert result==proposal and trace['model']=='copilot/test-model' and not trace['execution_authorized']
    assert trace['usage']['output_tokens']==123 and call.call_count==1
    assert guard.call_count>=1


def test_changed_route_never_falls_back_or_calls_provider():
    proposal,captured,profile=setup();profile['model_routes']['etl_specification']='other';call=Mock()
    with pytest.raises(DeveloperInvocationError,match='MODEL_VERSION_MISMATCH'):
        complete_developer(captured,profile,native_completion=call,before_call=Mock())
    call.assert_not_called()


def test_invalid_output_preserves_usage_but_does_not_retry():
    proposal,captured,profile=setup();proposal['specification']['target_table']='other'
    call=Mock(side_effect=native(proposal))
    with pytest.raises(DeveloperInvocationError,match='OUTPUT_INVALID') as caught:
        complete_developer(captured,profile,native_completion=call,before_call=Mock())
    assert call.call_count==1 and caught.value.trace['usage']['output_tokens']==123
    assert 'other' not in str(caught.value)


def test_guard_failure_never_invokes_cli():
    _,captured,profile=setup();call=Mock()
    with pytest.raises(DeveloperInvocationError,match='OUTCOME_UNKNOWN'):
        complete_developer(captured,profile,native_completion=call,before_call=Mock(side_effect=ValueError('private')))
    call.assert_not_called()
