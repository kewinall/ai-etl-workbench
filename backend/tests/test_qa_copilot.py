from unittest.mock import Mock
import pytest
from app.qa_gateway import complete_qa_review,QAInvocationError
from app.copilot_gateway import complete_copilot,CopilotError
from test_qa_gateway import values


def native_values():
    run,profile,context,review,_=values()
    profile.update(provider_type='LOCAL_COPILOT',model_routes={'qa_review':'gpt-5.4'})
    run['settings_snapshot']['model_routes']={'qa_review':'copilot/gpt-5.4'}
    def native(payload,model,*,before_call):
        before_call()
        trace={key:context[key] for key in ('run_id','specification_checksum','context_checksum')}
        trace.update(provider='LOCAL_COPILOT',model=model,prompt_checksum=payload['prompt_checksum'],
            schema_checksum=payload['schema_checksum'],usage={'output_tokens':9,'input_tokens':None,'total_tokens':None})
        return review,trace
    return run,profile,context,review,native


def test_native_qa_requires_worker_and_guard():
    run,profile,context,_,native=native_values()
    with pytest.raises(QAInvocationError,match='QA_NATIVE_COPILOT_WORKER_REQUIRED'):
        complete_qa_review(run,profile,context,native_completion=native)


def test_native_qa_keeps_partial_usage_and_validates_contract():
    run,profile,context,review,native=native_values();guard=Mock()
    accepted,trace=complete_qa_review(run,profile,context,native_completion=native,before_call=guard)
    assert accepted['qa_approved'] is False and trace['usage']['input_tokens'] is None
    assert trace['usage']['output_tokens']==9 and guard.call_count==2
    review['evidence_ids']=['invented']
    with pytest.raises(QAInvocationError,match='QA_OUTPUT_CONTRACT_INVALID'):
        complete_qa_review(run,profile,context,native_completion=native,before_call=guard)


def test_native_failure_never_retries():
    run,profile,context,_,_=native_values();native=Mock(side_effect=RuntimeError('private error'))
    with pytest.raises(QAInvocationError,match='QA_COPILOT_OUTCOME_UNKNOWN'):
        complete_qa_review(run,profile,context,native_completion=native,before_call=lambda:None)
    assert native.call_count==1


def test_bad_binding_rejected_before_starting_cli(monkeypatch):
    process=Mock();monkeypatch.setattr('app.copilot_gateway.subprocess.Popen',process)
    with pytest.raises(CopilotError,match='COPILOT_CONTEXT_BINDING_REQUIRED'):
        complete_copilot({'context':{}},'copilot/gpt-5.4',before_call=lambda:None)
    process.assert_not_called()
