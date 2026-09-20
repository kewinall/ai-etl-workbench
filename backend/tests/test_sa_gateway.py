import json
from types import SimpleNamespace as NS
import pytest
from app.sa_gateway import complete_sa_review, SAInvocationError


def values():
    profile = dict(enabled=True, provider_type='LITELLM_BEDROCK', region='us-east-1', model_routes={'requirement_gate': 'bedrock/synthetic'})
    run = dict(run_id='run', input_checksum='a'*64, state='NEEDS_REVIEW', write_started=False, matches_current=True,
               approval={'decision': 'APPROVE'}, settings_snapshot={'checksum': 'b'*64, 'model_routes': profile['model_routes'].copy()},
               input_snapshot={'requirement_text': 'load data', 'source_config': {'sources': [{'fields': [{'name': 'id', 'type': 'BIGINT'}]}]},
                               'target_config': {'schema': 'ai_sample', 'table': 'test', 'requirements_v1': {'write_mode': 'APPEND', 'date_scope': 'ALL'}}})
    return run, profile


def response(**kwargs):
    context = json.loads(kwargs['messages'][1]['content'])['context']
    output = dict(version=1, run_id=context['run_id'], input_checksum=context['input_checksum'], context_checksum=context['context_checksum'],
                  status='READY_FOR_REVIEW', summary='Review only', evidence_ids=['requirement'], issues=[])
    return NS(choices=[NS(message=NS(content=json.dumps(output)))], usage=NS(prompt_tokens=3, completion_tokens=4, total_tokens=7))


def test_gateway_schema_and_trace_are_connected_without_execution():
    run, profile = values()
    result, trace = complete_sa_review(run, profile, completion=response)
    assert result['status'] == 'READY_FOR_REVIEW'
    assert trace['usage']['total_tokens'] == 7
    assert trace['status'] == 'VALIDATED_NOT_APPROVED'
    assert trace['execution_authorized'] is False
    assert len(trace['prompt_checksum']) == len(trace['output_checksum']) == 64


def test_proxy_route_uses_same_normalized_model_as_settings():
    run, profile = values()
    profile.update(provider_type='LITELLM_PROXY', endpoint='http://synthetic.invalid/v1', model_routes={'requirement_gate': 'synthetic-alias'})
    run['settings_snapshot']['model_routes']['requirement_gate'] = 'openai/synthetic-alias'
    result, trace = complete_sa_review(run, profile, secret='synthetic-not-real', completion=response)
    assert result['status'] == 'READY_FOR_REVIEW'
    assert trace['model'] == 'openai/synthetic-alias'


@pytest.mark.parametrize('field,value', [('matches_current', False), ('write_started', True), ('approval', None), ('state', 'QUEUED')])
def test_unapproved_or_stale_run_never_calls_provider(field, value):
    run, profile = values()
    run[field] = value
    def unexpected(**kwargs): raise AssertionError('Provider must not be called')
    with pytest.raises(SAInvocationError, match='SA_RUN_NOT_AUTHORIZED'):
        complete_sa_review(run, profile, completion=unexpected)


def test_invalid_output_retains_usage_but_not_raw_secret():
    run, profile = values()
    def invalid(**kwargs):
        return NS(choices=[NS(message=NS(content='{"secret":"private-output"}'))], usage=NS(prompt_tokens=3, completion_tokens=4, total_tokens=7))
    with pytest.raises(SAInvocationError) as caught:
        complete_sa_review(run, profile, completion=invalid)
    assert caught.value.trace['error_code'] == 'SA_OUTPUT_CONTRACT_INVALID'
    assert caught.value.trace['usage']['total_tokens'] == 7
    assert 'private-output' not in str(caught.value.trace)
