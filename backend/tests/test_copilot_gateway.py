import json
import pytest
from app.copilot_gateway import parse_output, CopilotError, command_for
from app.model_gateway import completion_options, complete_json, GatewayError
from app.local_sa_worker import run_once


def events(*, model='gpt-5.4', tool=False):
    rows = [{'type': 'assistant.message', 'data': {'model': model, 'content': '{"version":1}', 'outputTokens': 9}},
            {'type': 'session.usage_checkpoint', 'data': {'totalNanoAiu': 250000000}},
            {'type': 'result', 'usage': {'premiumRequests': 1}}]
    if tool:
        rows.insert(0, {'type': 'tool.execution_start', 'data': {'toolName': 'shell'}})
    return '\n'.join(json.dumps(row) for row in rows)


def test_copilot_events_record_partial_usage_without_invented_tokens():
    review, usage = parse_output(events(), 'copilot/gpt-5.4')
    assert review == {'version': 1}
    assert usage['output_tokens'] == 9
    assert usage['total_tokens'] is None
    assert usage['ai_credits'] == 0.25
    assert usage['automatic_retries'] == 0


def test_copilot_wrong_model_and_tools_are_rejected():
    with pytest.raises(CopilotError, match='MODEL_MISMATCH'):
        parse_output(events(model='other'), 'copilot/gpt-5.4')
    with pytest.raises(CopilotError, match='TOOL_POLICY'):
        parse_output(events(tool=True), 'copilot/gpt-5.4')


def test_copilot_route_never_falls_through_to_litellm():
    profile = {'enabled': True, 'provider_type': 'LOCAL_COPILOT', 'model_routes': {'requirement_gate': 'gpt-5.4'}}
    assert completion_options(profile, 'requirement_gate')['model'] == 'copilot/gpt-5.4'
    with pytest.raises(GatewayError, match='NATIVE_WORKER_REQUIRED'):
        complete_json(profile, 'requirement_gate', [])
    with pytest.raises(GatewayError, match='EXPLICIT_MODEL'):
        completion_options({**profile, 'model_routes': {'requirement_gate': 'auto'}}, 'requirement_gate')


def test_native_command_has_no_tools_or_shell_interpolation(monkeypatch, tmp_path):
    monkeypatch.setattr('app.copilot_gateway.shutil.which', lambda _: '/safe/copilot')
    monkeypatch.setenv('COPILOT_HOME', str(tmp_path))
    command = command_for('copilot/gpt-5.4', 'untrusted & $(payload)', str(tmp_path))
    assert '--available-tools=' in command
    assert '--allow-all-tools' not in command
    assert '--disable-builtin-mcps' in command
    assert command[command.index('-p')+1] == 'untrusted & $(payload)'


def test_native_worker_claims_and_finishes_once_without_credentials():
    calls = []
    def transport(data):
        calls.append(data['action'])
        if data['action'] == 'claim':
            return {'status': 'DISPATCH_RESERVED', 'invocation_id': 'i', 'claim_token': 't', 'input_json': {}, 'model': 'copilot/gpt-5.4'}
        return {'status': 'VALIDATED_NOT_APPROVED' if data['action'] == 'finish' else 'LEASE_ACTIVE'}
    def complete(payload, model, *, before_call):
        before_call()
        return {'version': 1}, {'model': model}
    assert run_once('task', 'run', transport=transport, completion=complete)['status'] == 'VALIDATED_NOT_APPROVED'
    assert calls == ['claim', 'heartbeat', 'heartbeat', 'finish']


def test_native_worker_failure_never_replays():
    calls = []
    def transport(data):
        calls.append(data['action'])
        return {'status': 'DISPATCH_RESERVED', 'invocation_id': 'i', 'claim_token': 't', 'input_json': {}, 'model': 'copilot/gpt-5.4'}
    def failure(*args, **kwargs):
        raise CopilotError('COPILOT_OUTCOME_UNKNOWN_TIMEOUT')
    result = run_once('task', 'run', transport=transport, completion=failure)
    assert result['status'] == 'OUTCOME_REQUIRES_RECONCILIATION'
    assert calls == ['claim', 'uncertain']
