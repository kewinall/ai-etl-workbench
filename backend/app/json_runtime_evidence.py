"""Read the private launcher's JSON setting receipt, not data or QA success."""

MARKER = b'WORKBENCH_JSON_READER_V1 INCLUDE_NULLS=Y'


def require_json_runtime_receipt(log):
    if not isinstance(log, bytes) or len(log) > 10 * 1024 * 1024:
        raise ValueError('JSON_RUNTIME_RECEIPT_REQUIRED')
    receipts = [line for line in log.splitlines() if line.startswith(b'WORKBENCH_JSON_READER_')]
    if receipts != [MARKER]:
        raise ValueError('JSON_RUNTIME_RECEIPT_REQUIRED')
    return {'version': 1, 'scope': 'PRIVATE_LAUNCHER_SYSTEM_PROPERTY_RECEIPT',
            'HOP_JSON_INPUT_INCLUDE_NULLS': 'Y', 'qa_passed': False}
