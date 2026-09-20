"""Allowlisted terminal engine evidence, independent of QA/release decisions."""
import re


def validated_hop_outcome(result):
    if not isinstance(result, dict) or set(result) != {'status', 'exit_code', 'errors', 'log_checksum'}:
        raise ValueError('INVALID_HOP_OUTCOME')
    status = result['status']
    if status not in ('COMPLETED', 'FAILED', 'UNKNOWN'):
        raise ValueError('INVALID_HOP_OUTCOME')
    for key in ('exit_code', 'errors'):
        value = result[key]
        if value is not None and (type(value) is not int or not 0 <= value <= 2147483647):
            raise ValueError('INVALID_HOP_OUTCOME')
    checksum = result['log_checksum']
    if checksum is not None and (not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum)):
        raise ValueError('INVALID_HOP_OUTCOME')
    if status == 'COMPLETED' and (result['exit_code'] != 0 or result['errors'] != 0 or checksum is None):
        raise ValueError('INVALID_HOP_OUTCOME')
    if status == 'FAILED' and (checksum is None or not (result['exit_code'] or result['errors'])):
        raise ValueError('INVALID_HOP_OUTCOME')
    outcome = {'COMPLETED':'HOP_EXECUTED_QA_REQUIRED', 'FAILED':'HOP_EXECUTION_FAILED', 'UNKNOWN':'HOP_RESULT_UNKNOWN'}[status]
    return outcome, {**result, 'automatic_retry_allowed':False, 'qa_passed':False, 'release_ready':False}
