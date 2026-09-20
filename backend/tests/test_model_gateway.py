from types import SimpleNamespace as NS
import pytest
from app.model_gateway import complete_json, completion_options, GatewayError, public_profile


def profile(**extra):
    return {'enabled': True, 'provider_type': 'LITELLM_BEDROCK', 'region': 'us-east-1',
            'model_routes': {'sa': 'bedrock/amazon.nova-micro-v1:0'}, **extra}


def response(content='{}'):
    return NS(choices=[NS(message=NS(content=content))], usage=NS(prompt_tokens=2, completion_tokens=3, total_tokens=5))


def test_missing_role_never_falls_back():
    with pytest.raises(GatewayError, match='MODEL_ROUTE_MISSING'):
        completion_options(profile(model_routes={'etl_specification': 'another-model'}), 'sa')


def test_region_and_credentials_are_passed_only_to_provider():
    seen = {}
    def call(**kwargs):
        seen.update(kwargs)
        return response()
    _, usage = complete_json(profile(secret_ref='vault-ref'), 'sa', [], secret='{"aws_access_key_id":"id-value","aws_secret_access_key":"private-value"}', completion=call)
    assert seen['aws_region_name'] == 'us-east-1'
    assert seen['aws_secret_access_key'] == 'private-value'
    assert seen['num_retries'] == 0
    assert 'private-value' not in str(usage)
    assert 'secret_ref' not in public_profile(profile(secret_ref='vault-ref'))


def test_proxy_endpoint_and_key():
    opts = completion_options(profile(provider_type='LITELLM_PROXY', endpoint='http://gateway:4000/v1', model_routes={'sa': 'nova-sa'}), 'sa', 'key')
    assert opts['model'] == 'openai/nova-sa'
    assert opts['api_base'] == 'http://gateway:4000/v1'
    assert opts['api_key'] == 'key'


@pytest.mark.parametrize('extra,code', [
    ({'region': None}, 'BEDROCK_MODEL_OR_REGION_MISSING'),
    ({'enabled': False}, 'AI_PROFILE_DISABLED'),
    ({'timeout_seconds': 0}, 'MODEL_TIMEOUT_INVALID'),
    ({'secret_ref': 'missing'}, 'AI_SECRET_UNAVAILABLE'),
    ({'provider_type': 'other'}, 'AI_PROVIDER_UNSUPPORTED'),
])
def test_configuration_fail_closed(extra, code):
    with pytest.raises(GatewayError, match=code):
        completion_options(profile(**extra), 'sa')


def test_retry_budget_and_error_masking():
    calls = []
    class TemporaryError(Exception):
        status_code = 503
    def fail(**kwargs):
        calls.append(kwargs)
        raise TemporaryError('private-key hostname should not leak')
    with pytest.raises(GatewayError, match='^MODEL_TEMPORARY_FAILURE$'):
        complete_json(profile(), 'sa', [], completion=fail, sleep=lambda _: None)
    assert len(calls) == 3


def test_output_correction_once_and_usage_includes_both_responses():
    results = iter([response('not JSON'), response('{"ok":true}')])
    messages = [{'role': 'user', 'content': 'input'}]
    data, usage = complete_json(profile(), 'sa', messages, completion=lambda **kw: next(results))
    assert data == {'ok': True}
    assert usage['total_tokens'] == 10
    assert usage['output_corrections'] == 1
    assert len(messages) == 1
    with pytest.raises(GatewayError, match='MODEL_OUTPUT_INVALID'):
        complete_json(profile(), 'sa', [], completion=lambda **kw: response('[]'))


def test_authentication_failure_not_retried():
    calls = []
    def fail(**kwargs):
        calls.append(1)
        raise RuntimeError('secret')
    with pytest.raises(GatewayError, match='^MODEL_CALL_FAILED$'):
        complete_json(profile(), 'sa', [], completion=fail)
    assert len(calls) == 1
