"""Safe native SA failure diagnostics; never expose exception or model text."""
import hashlib
import json
from pydantic import ValidationError
from .invocation_usage import checked_usage

FAILURE_CODES = frozenset({
    'SA_OUTCOME_UNKNOWN', 'SA_OUTPUT_CONTRACT_INVALID', 'SA_VERSION_MISMATCH',
    'SA_UNKNOWN_EVIDENCE', 'SA_REQUIREMENT_EVIDENCE_REQUIRED', 'SA_CANNOT_OVERRIDE_GATE',
    'SA_MISSING_ISSUE_DETAILS', 'SA_LEASE_LOST', 'SA_RESULT_NOT_WRITABLE',
    'SA_AUTHORIZATION_VERSION_MISMATCH', 'SA_DISPATCH_DISABLED',
    'LOCAL_WORKER_BRIDGE_UNAVAILABLE', 'LOCAL_WORKER_BRIDGE_FAILED', 'LOCAL_WORKER_REQUEST_FAILED',
    'COPILOT_NOT_INSTALLED', 'COPILOT_SAFE_ENTRYPOINT_MISSING', 'COPILOT_EXPLICIT_MODEL_REQUIRED',
    'COPILOT_MCP_CONFIG_UNREADABLE', 'COPILOT_BYOK_NOT_ALLOWED', 'COPILOT_CONTEXT_BINDING_REQUIRED',
    'COPILOT_OUTCOME_UNKNOWN_TIMEOUT', 'COPILOT_CALL_FAILED_OR_OUTPUT_TOO_LARGE',
    'COPILOT_OUTPUT_INCOMPLETE', 'COPILOT_MODEL_MISMATCH', 'COPILOT_TOOL_POLICY_VIOLATION',
    'COPILOT_OUTPUT_SCHEMA_INVALID',
})
FAILURE_STAGES = frozenset({'MODEL_CALL', 'RESULT_CHECK', 'RESULT_PERSISTENCE', 'UNRECORDED'})


def safe_code(error):
    if isinstance(error, ValidationError):
        return 'SA_OUTPUT_CONTRACT_INVALID'
    code = str(error)
    return code if isinstance(error, ValueError) and code in FAILURE_CODES else 'SA_OUTCOME_UNKNOWN'


def failure_trace(record, packet):
    """Accept only bound native usage. An invalid result never becomes an SA review."""
    code, stage = packet.get('error_code'), packet.get('failure_stage')
    result = dict(error_code=code if isinstance(code, str) and code in FAILURE_CODES else 'SA_OUTCOME_UNKNOWN',
                  failure_stage=stage if isinstance(stage, str) and stage in FAILURE_STAGES else 'UNRECORDED',
                  usage=None, duration_ms=None, automatic_retry=False)
    trace, output = packet.get('trace'), packet.get('review')
    if not isinstance(trace, dict) or not isinstance(output, dict):
        return result
    try:
        expected = dict(provider='LOCAL_COPILOT', model=record['model'], run_id=str(record['run_id']),
                        context_checksum=record['context_checksum'],
                        input_checksum=record['input_json']['context']['input_checksum'],
                        prompt_checksum=record['input_json']['prompt_checksum'],
                        schema_checksum=record['input_json']['schema_checksum'],
                        output_checksum=hashlib.sha256(json.dumps(output, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                        execution_authorized=False)
        if record['provider'] != 'LOCAL_COPILOT' or any(trace.get(k) != v for k, v in expected.items()):
            return result
        duration = trace.get('duration_ms')
        if type(duration) is not int or duration < 0:
            return result
        usage = checked_usage(trace.get('usage'))
        if any(type(usage.get(k)) is not int or usage[k] != v for k, v in
               (('cli_sessions', 1), ('automatic_retries', 0), ('tool_execution_count', 0))):
            return result
        result.update(usage=usage, duration_ms=duration)
    except (KeyError, TypeError, ValueError):
        pass
    return result
