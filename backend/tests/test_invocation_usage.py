import pytest
from app.invocation_usage import checked_usage


def test_native_usage_preserves_partial_counts_and_credits_without_private_fields():
    usage = {'input_tokens':None, 'output_tokens':123, 'ai_credits':0.25, 'premium_requests':1,
             'cli_sessions':1, 'automatic_retries':0, 'tool_execution_count':0,
             'usage_type':'PARTIAL', 'usage_source':'copilot_json_events', 'private':'secret'}
    result = checked_usage(usage)
    assert result == {k:v for k,v in usage.items() if k != 'private'}
    assert 'total_tokens' not in result


@pytest.mark.parametrize('usage', [[], {'ai_credits':float('nan')}, {'ai_credits':float('inf')},
    {'premium_requests':True}, {'cli_sessions':-1}, {'output_tokens':1.2}, {'usage_source':'private'}])
def test_invalid_usage_rejected(usage):
    with pytest.raises(ValueError, match='USAGE_INVALID'): checked_usage(usage)


def test_qa_trace_keeps_copilot_accounting_and_legacy_nullable_fields():
    from app.qa_journal import checked_trace
    record = dict(provider='LOCAL_COPILOT', model='copilot/test', prompt_version=1,
                  context_checksum='c'*64, run_id='run',
                  input_json={'prompt_checksum':'a'*64, 'schema_checksum':'b'*64})
    trace = {k:v for k,v in record.items() if k != 'input_json'}
    trace.update(record['input_json'])
    trace.update(status='VALIDATED_NOT_APPROVED', output_checksum='d'*64, duration_ms=1,
                 usage={'cli_sessions':1, 'automatic_retries':0, 'tool_execution_count':0,
                        'ai_credits':0.25, 'premium_requests':1, 'usage_type':'PARTIAL',
                        'usage_source':'copilot_json_events'})
    result = checked_trace(trace, record)
    assert result['usage']['ai_credits'] == 0.25
    assert result['usage']['cli_sessions'] == 1
    assert result['usage']['input_tokens'] is None
    assert result['usage']['total_tokens'] is None


def test_existing_litellm_usage_enum_is_preserved():
    usage={'usage_type':'EXACT','usage_source':'litellm','usage_scope':'received_responses',
           'input_tokens':10,'output_tokens':5,'total_tokens':15}
    assert checked_usage(usage)==usage
    usage.update(usage_type='UNAVAILABLE',total_tokens=None)
    assert checked_usage(usage)==usage
