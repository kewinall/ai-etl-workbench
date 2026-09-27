"""Explicit correction of an executed, unapproved QA review; never retries Hop."""
from .sa_contract import digest


def offer(queue, conn, run):
    if not (run['state'] == 'NEEDS_REVIEW' and run['phase'] == 'HOP_EXECUTION'
            and run['write_started'] and run['lease_token'] is None
            and run['outcome_code'] == 'HOP_EXECUTED_QA_REQUIRED'):
        return None
    identity = (run['run_id'],)
    if (conn.execute('SELECT 1 FROM platform.task_run WHERE parent_run_id=%s', identity).fetchone()
            or conn.execute('SELECT 1 FROM platform.qa_review_approval WHERE run_id=%s', identity).fetchone()
            or conn.execute("SELECT 1 FROM platform.hop_dispatch_request WHERE run_id=%s AND status IN ('QUEUED','CLAIMED')", identity).fetchone()):
        return None
    row = conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa' ORDER BY created_at DESC,invocation_id DESC LIMIT 1", identity).fetchone()
    if not row or row['status'] != 'VALIDATED_NOT_APPROVED':
        return None
    from .qa_journal import public_record
    from .qa_context import load_qa_context
    try:
        record = public_record(row)
        if record['review']['status'] not in ('FAIL', 'NEEDS_REVIEW'):
            return None
        current = load_qa_context(queue, run['task_id'], run['run_id'],
                                  row['input_json']['comparison_id'], connection=conn)
        if current['context']['context_checksum'] != row['context_checksum']:
            return None
    except (ValueError, KeyError, TypeError):
        return None
    binding = {'run_id': str(run['run_id']), 'input_checksum': run['input_checksum'],
               'invocation_id': str(row['invocation_id']), 'context_checksum': row['context_checksum'],
               'review_checksum': row['output_json']['review_checksum'],
               'automatic_retry_allowed': False}
    return {**binding, 'checksum': digest(binding)}
