"""Internal execution preparation, never dispatch or a durable execution permit."""
from . import specification_store
from .hpl_compiler import compile_hpl
from .result_query_plan import build_result_query_plan


def load_approved_candidate(queue, conn, task_id, run_id, specification_id, preparing=False):
    """Caller owns transaction; after releasing locks, recheck before dispatch.

    Uses authoritative saved content only. No caller-supplied XML, source path,
    checksum or approval flag can substitute for the saved revision.
    """
    run, naming = specification_store.context(queue, conn, task_id, run_id)
    row = conn.execute('SELECT * FROM platform.specification WHERE task_id=%s ORDER BY version DESC LIMIT 1 FOR SHARE', (task_id,)).fetchone()
    if (not row or str(row['specification_id']) != str(specification_id)
            or row['run_id'] != run['run_id'] or not row['is_current']):
        raise ValueError('CURRENT_SPECIFICATION_REQUIRED')
    approval = conn.execute('SELECT * FROM platform.specification_approval WHERE specification_id=%s FOR SHARE', (row['specification_id'],)).fetchone()
    if not approval or approval['content_checksum'] != row['content_checksum']:
        raise ValueError('SPECIFICATION_APPROVAL_REQUIRED')
    if not naming:
        raise ValueError('NAMING_REQUIRED')
    validation_run = run
    if preparing:
        if run['state'] != 'RUNNING' or run['phase'] != 'HOP_PREPARATION' or run['write_started']:
            raise ValueError('RUN_NOT_PREPARING')
        # Reuse design validation after reservation; this does not mutate the Run.
        validation_run = {**run, 'state':'NEEDS_REVIEW'}
    compiled = compile_hpl(row['spec_json'], validation_run, naming)
    if (compiled['status'] != 'VALIDATED_NOT_APPROVED'
            or compiled['specification_checksum'] != row['content_checksum']):
        raise ValueError('APPROVED_INPUTS_STALE_OR_INVALID')
    result_query = build_result_query_plan(row['spec_json'], validation_run, naming)
    return {'status':'APPROVED_CANDIDATE_ONLY', 'execution_authorized':False,
            'run':run, 'specification_id':str(row['specification_id']),
            'specification_checksum':row['content_checksum'],
            'approval_id':str(approval['approval_id']), 'compiled':compiled,
            'result_query':result_query}
