"""Read only a compiler-generated query pinned by completed execution evidence.

This establishes query identity, not exclusive table ownership or QA approval.
The caller must obtain the plan from trusted saved specification data and the
pin from load_execution_oracle, never from an HTTP request.
"""
from hashlib import sha256
import json
from .execution_oracle import load_execution_oracle
from .result_query_plan import build_result_query_plan
from . import specification_store


def load_bound_result_query(queue, task_id, run_id):
    with queue.conn() as conn:
        pinned = load_execution_oracle(queue, task_id, run_id, connection=conn)
        run, naming = specification_store.context(queue, conn, task_id, run_id)
        row = conn.execute('''SELECT s.spec_json FROM platform.specification s
            JOIN platform.task_run_execution_authorization a USING(specification_id)
            WHERE a.run_id=%s AND s.run_id=%s AND s.task_id=%s FOR SHARE OF s,a''',
            (run_id, run_id, task_id)).fetchone()
        if not row or not naming:
            raise ValueError('EXECUTED_SPECIFICATION_REQUIRED')
        # Completed execution was checked under the Task lock above. Reconstruct
        # its pre-write query only; never mutate state or re-authorize execution.
        result = build_result_query_plan(row['spec_json'], {**run, 'write_started': False}, naming)
        if result['checksum'] != pinned['result_query_checksum']:
            raise ValueError('RESULT_QUERY_BINDING_CHANGED')
    return result, pinned


def execute_bound_result_query(cursor, result_query, execution_oracle):
    plan = result_query['plan']
    digest = sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if (digest != result_query.get('checksum')
            or digest != execution_oracle.get('result_query_checksum')
            or sha256(plan['sql'].encode()).hexdigest() != plan.get('sql_checksum')):
        raise ValueError('RESULT_QUERY_BINDING_CHANGED')
    # This API does not accept parameters or SQL overrides. The complete target
    # projection and overflow sentinel were selected before Hop execution.
    cursor.execute(plan['sql'])
    return {'query_checksum': digest, 'sql_checksum': plan['sql_checksum'],
            'actual_provenance': 'NOT_VERIFIED', 'qa_passed': False,
            'release_ready': False}
