"""Bounded role routing. No model fallback and no provider errors in public output."""
import json
import time
import re
from copy import deepcopy
from urllib.parse import urlsplit


class GatewayError(ValueError):
    pass


def public_profile(profile):
    allowed = ('profile_id', 'display_name', 'provider_type', 'endpoint', 'region',
               'model_routes', 'enabled', 'updated_at')
    return {**{key: profile.get(key) for key in allowed},
            'secret_configured': bool(profile.get('secret_ref'))}


def completion_options(profile, role, secret=None):
    if profile.get('enabled') is not True:
        raise GatewayError('AI_PROFILE_DISABLED')
    model = (profile.get('model_routes') or {}).get(role)
    if not isinstance(model, str) or not model.strip():
        raise GatewayError('MODEL_ROUTE_MISSING')
    timeout = profile.get('timeout_seconds', 90)
    if type(timeout) not in (int, float) or not 1 <= timeout <= 120:
        raise GatewayError('MODEL_TIMEOUT_INVALID')
    options = {'model': model, 'timeout': timeout, 'num_retries': 0}
    provider = profile.get('provider_type')
    if provider == 'LOCAL_COPILOT':
        name = model.removeprefix('copilot/')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}', name) or name == 'auto':
            raise GatewayError('COPILOT_EXPLICIT_MODEL_REQUIRED')
        if profile.get('endpoint') or profile.get('secret_ref') or secret:
            raise GatewayError('COPILOT_LOCAL_LOGIN_ONLY')
        options['model'] = 'copilot/' + name
    elif provider == 'LITELLM_BEDROCK':
        if not model.startswith('bedrock/') or not profile.get('region'):
            raise GatewayError('BEDROCK_MODEL_OR_REGION_MISSING')
        if profile.get('endpoint'):
            raise GatewayError('BEDROCK_ENDPOINT_UNSUPPORTED_USE_PROXY_PROFILE')
        options['aws_region_name'] = profile['region']
        if profile.get('secret_ref') and not secret:
            raise GatewayError('AI_SECRET_UNAVAILABLE')
        if secret:
            try:
                credentials = json.loads(secret)
                keys = ('aws_access_key_id', 'aws_secret_access_key')
                if not isinstance(credentials, dict) or any(not isinstance(credentials.get(k), str) or not credentials[k].strip() for k in keys):
                    raise ValueError()
                options.update({key: credentials[key] for key in keys})
                if credentials.get('aws_session_token'):
                    options['aws_session_token'] = credentials['aws_session_token']
            except (ValueError, TypeError):
                raise GatewayError('BEDROCK_SECRET_FORMAT_INVALID') from None
        # No secret: the deployment's AWS credential chain is used deliberately.
    elif provider == 'LITELLM_PROXY':
        endpoint = profile.get('endpoint') or ''
        parsed = urlsplit(endpoint)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise GatewayError('PROXY_ENDPOINT_INVALID')
        if not secret:
            raise GatewayError('AI_SECRET_UNAVAILABLE')
        options.update(api_base=endpoint, api_key=secret)
        options['model'] = 'openai/' + model.removeprefix('openai/')
    else:
        raise GatewayError('AI_PROVIDER_UNSUPPORTED')
    return options


def complete_json(profile, role, messages, *, secret=None, completion=None, sleep=time.sleep, max_output_tokens=None):
    options = completion_options(profile, role, secret)
    if profile.get('provider_type') == 'LOCAL_COPILOT':
        raise GatewayError('COPILOT_NATIVE_WORKER_REQUIRED')
    if max_output_tokens is not None:
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 8192:
            raise GatewayError('MODEL_OUTPUT_LIMIT_INVALID')
        options['max_tokens'] = max_output_tokens
    if completion is None:
        from litellm import completion
    conversation = deepcopy(messages)
    started = time.monotonic()
    transient_retries = 0
    corrections = 0
    attempts = 0
    usage_rows = []
    while True:
        attempts += 1
        try:
            response = completion(**options, messages=conversation)
        except Exception as exc:
            status = getattr(exc, 'status_code', None)
            transient = status in (408, 429, 500, 502, 503, 504) or isinstance(exc, TimeoutError)
            if transient and transient_retries < 2:
                transient_retries += 1
                sleep(0.25 * (2 ** (transient_retries - 1)))
                continue
            raise GatewayError('MODEL_TEMPORARY_FAILURE' if transient else 'MODEL_CALL_FAILED') from None
        usage_rows.append(getattr(response, 'usage', None))
        try:
            data = json.loads(response.choices[0].message.content)
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, TypeError, AttributeError, IndexError):
            if corrections == 0:
                corrections = 1
                conversation.append({'role': 'user', 'content': '輸出格式不合法。請只回傳一個有效 JSON object，不要 Markdown 或解說。'})
                continue
            raise GatewayError('MODEL_OUTPUT_INVALID') from None
        fields = {'input_tokens': 'prompt_tokens', 'output_tokens': 'completion_tokens', 'total_tokens': 'total_tokens'}
        usage = {key: sum(getattr(row, attr) for row in usage_rows) if all(getattr(row, attr, None) is not None for row in usage_rows) else None for key, attr in fields.items()}
        return data, {**usage, 'provider': profile['provider_type'], 'model': options['model'],
                      'duration_ms': round((time.monotonic() - started) * 1000), 'attempts': attempts,
                      'transient_retries': transient_retries, 'output_corrections': corrections,
                      'usage_type': 'EXACT' if all(v is not None for v in usage.values()) and not transient_retries else 'UNAVAILABLE',
                      'usage_source': 'litellm', 'usage_scope': 'received_responses'}
