import hashlib
import json
from copy import deepcopy
import pytest
from app.sa_failure import safe_code, failure_trace
from app.sa_contract import SAReviewV1
from app.local_sa_worker import run_once
from app.copilot_gateway import CopilotError


def packet():
    record = dict(provider='LOCAL_COPILOT', model='copilot/gpt-5.4', run_id='run',
                  context_checksum='c'*64, input_json=dict(context={'input_checksum':'i'*64},
                  prompt_checksum='p'*64, schema_checksum='s'*64))
    output = {'untrusted':'invalid model output must not be persisted'}
    trace = dict(provider=record['provider'], model=record['model'], run_id='run',
                 context_checksum=record['context_checksum'], input_checksum='i'*64,
                 prompt_checksum='p'*64, schema_checksum='s'*64,
                 output_checksum=hashlib.sha256(json.dumps(output,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                 execution_authorized=False, duration_ms=42,
                 usage=dict(cli_sessions=1, automatic_retries=0, tool_execution_count=0,
                            total_tokens=None, ai_credits=0.25, usage_type='PARTIAL', usage_source='copilot_json_events',
                            private_extra='must not escape'))
    return record, dict(error_code='SA_UNKNOWN_EVIDENCE',failure_stage='RESULT_PERSISTENCE',review=output,trace=trace)


def test_failure_code_never_exposes_exception_text():
    assert safe_code(ValueError('SA_UNKNOWN_EVIDENCE')) == 'SA_UNKNOWN_EVIDENCE'
    assert safe_code(RuntimeError('password=private host.example')) == 'SA_OUTCOME_UNKNOWN'
    assert safe_code(ValueError('password=private')) == 'SA_OUTCOME_UNKNOWN'
    with pytest.raises(ValueError) as error:
        SAReviewV1.model_validate({'secret':'never publish this'})
    assert safe_code(error.value) == 'SA_OUTPUT_CONTRACT_INVALID'


def test_bound_usage_survives_rejected_review_without_review_or_secrets():
    record, data = packet()
    result = failure_trace(record, data)
    assert result['usage']['ai_credits'] == 0.25 and result['usage']['total_tokens'] is None
    assert result['duration_ms'] == 42 and result['automatic_retry'] is False
    assert 'private' not in json.dumps(result) and 'untrusted' not in json.dumps(result)


@pytest.mark.parametrize('key,value', [('provider','wrong'),('model','wrong'),('run_id','wrong'),
    ('context_checksum','wrong'),('input_checksum','wrong'),('prompt_checksum','wrong'),
    ('schema_checksum','wrong'),('output_checksum','wrong'),('duration_ms',True)])
def test_unbound_trace_does_not_invent_usage(key,value):
    record, data = packet(); data['trace'][key] = value
    result = failure_trace(record, data)
    assert result['usage'] is None and result['duration_ms'] is None


@pytest.mark.parametrize('usage', [{'cli_sessions': True}, {'ai_credits': float('nan')}, {'tool_execution_count':1}])
def test_invalid_usage_rejected(usage):
    record, data = packet(); data['trace']['usage'].update(usage)
    assert failure_trace(record, data)['usage'] is None


def test_missing_trace_safe_and_unknown_stage_not_echoed():
    record, data = packet(); data.update(trace=None,error_code='secret',failure_stage='secret')
    result = failure_trace(record,data)
    assert result['error_code']=='SA_OUTCOME_UNKNOWN' and result['failure_stage']=='UNRECORDED'
    assert result['usage'] is None and 'secret' not in json.dumps(result)


def test_worker_preserves_received_trace_after_finish_failure_no_retry():
    calls=[]; invocations=[]
    record,data=packet()
    def transport(value):
        calls.append(deepcopy(value))
        if value['action']=='claim':
            return dict(status='DISPATCH_RESERVED',invocation_id='i',claim_token='t',input_json={},model=record['model'])
        if value['action']=='finish': raise CopilotError('SA_UNKNOWN_EVIDENCE')
        return {'status':'LEASE_ACTIVE'}
    def completion(*args,**kwargs):
        invocations.append(1)
        return data['review'],data['trace']
    result=run_once('task','run',transport=transport,completion=completion)
    assert len(invocations)==1 and result['code']=='SA_UNKNOWN_EVIDENCE'
    assert result['failure_stage']=='RESULT_PERSISTENCE'
    assert calls[-1]['action']=='uncertain' and calls[-1]['failure']['trace']==data['trace']
    assert [call['action'] for call in calls].count('finish')==1
