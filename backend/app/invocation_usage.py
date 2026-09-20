"""Allowlisted provider usage; unknown counts remain unavailable, never zero."""
import math


def checked_usage(usage):
    if usage is None:
        usage = {}
    if not isinstance(usage, dict):
        raise ValueError('MODEL_USAGE_INVALID')
    result = {}
    for key in ('input_tokens', 'output_tokens', 'total_tokens', 'attempts',
                'transient_retries', 'output_corrections', 'cli_sessions',
                'automatic_retries', 'tool_execution_count'):
        value = usage.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('MODEL_USAGE_INVALID')
        if key in usage:
            result[key] = value
    for key in ('ai_credits', 'premium_requests'):
        value = usage.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError('MODEL_USAGE_INVALID')
        if key in usage:
            result[key] = value
    for key, allowed in (('usage_type', {'PARTIAL', 'COMPLETE', 'EXACT', 'UNAVAILABLE'}),
                         ('usage_source', {'copilot_json_events', 'litellm'}),
                         ('usage_scope', {'received_responses'})):
        if key in usage:
            if usage[key] not in allowed:
                raise ValueError('MODEL_USAGE_INVALID')
            result[key] = usage[key]
    return result
