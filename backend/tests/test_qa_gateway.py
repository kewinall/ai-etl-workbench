import json
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from app.qa_gateway import complete_qa_review,QAInvocationError
from test_qa_contract import sample


def values():
    _,context,review=sample()
    profile={'enabled':True,'provider_type':'LITELLM_BEDROCK','region':'us-east-1','model_routes':{'qa_review':'bedrock/synthetic-qa'}}
    run=dict(run_id=context['run_id'],state='NEEDS_REVIEW',write_started=True,matches_current=True,
        lease_token=None,outcome_code='HOP_EXECUTED_QA_REQUIRED',settings_snapshot={'model_routes':profile['model_routes'].copy()})
    def response(**kwargs):
        assert kwargs['model']=='bedrock/synthetic-qa'
        assert json.loads(kwargs['messages'][1]['content'])['context']==context
        return NS(choices=[NS(message=NS(content=json.dumps(review)))],usage=NS(prompt_tokens=3,completion_tokens=4,total_tokens=7))
    return run,profile,context,review,response


def test_qa_role_trace_and_advisory_only():
    run,profile,context,_,response=values()
    accepted,trace=complete_qa_review(run,profile,context,completion=response)
    assert accepted['status']=='PASS' and not accepted['qa_approved']
    assert trace['model']=='bedrock/synthetic-qa' and trace['usage']['total_tokens']==7
    assert trace['status']=='VALIDATED_NOT_APPROVED' and not trace['release_ready']


@pytest.mark.parametrize('field,value',[('matches_current',False),('write_started',False),
    ('lease_token','active'),('outcome_code','HOP_EXECUTION_FAILED'),('state','RUNNING')])
def test_ineligible_run_never_calls_provider(field,value):
    run,profile,context,_,_=values();run[field]=value;provider=Mock()
    with pytest.raises(QAInvocationError,match='QA_RUN_NOT_REVIEWABLE'):
        complete_qa_review(run,profile,context,completion=provider)
    provider.assert_not_called()


def test_wrong_route_does_not_fall_back():
    run,profile,context,_,_=values();run['settings_snapshot']['model_routes']['qa_review']='bedrock/other';provider=Mock()
    with pytest.raises(QAInvocationError,match='QA_MODEL_VERSION_MISMATCH'):
        complete_qa_review(run,profile,context,completion=provider)
    provider.assert_not_called()


def test_invalid_output_keeps_usage_not_raw_content():
    run,profile,context,review,response=values();review['summary']='private invalid output';review['evidence_ids']=['invented']
    with pytest.raises(QAInvocationError,match='QA_OUTPUT_CONTRACT_INVALID') as caught:
        complete_qa_review(run,profile,context,completion=response)
    assert caught.value.trace['usage']['total_tokens']==7
    assert 'private invalid output' not in str(caught.value.trace)
