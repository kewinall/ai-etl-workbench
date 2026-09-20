"""Pre-execution QA read plan. No connection, execution, provenance or approval.

The future execution adapter must pin this plan before writing and establish
exclusive per-run target ownership. Reading a shared APPEND target is not proof
of the rows written by this run, even if its contents match an oracle.
"""
from hashlib import sha256
import json
from .etl_specification import compilation_plan


def build_result_query_plan(payload, run, naming):
    compiled = compilation_plan(payload, run, naming)
    if compiled['status'] != 'VALIDATED_NOT_APPROVED':
        raise ValueError('RESULT_QUERY_VALID_SPECIFICATION_REQUIRED')
    spec = compiled['specification']
    # Identifiers have passed the specification's strict identifier validator.
    # Read the entire target, not the source predicates: re-filtering would hide
    # incorrect output. No DISTINCT, aggregation, offset or expected-count limit.
    columns = [{'name': name, 'data_type': compiled['output_types'][name]}
               for name in spec['output_columns']]
    projection = ', '.join('"' + column['name'] + '"' for column in columns)
    sql = f'SELECT {projection} FROM "{spec["target_schema"]}"."{spec["target_table"]}" LIMIT 10001;'
    plan = {'version': 1, 'run_id': spec['run_id'],
            'specification_checksum': compiled['specification_checksum'],
            'naming_checksum': spec['naming']['checksum'],
            'settings_checksum': spec['settings_checksum'],
            'columns': columns, 'sql': sql,
            'sql_checksum': sha256(sql.encode()).hexdigest(),
            'comparison': 'EXACT_MULTISET', 'max_accepted_rows': 10000,
            'overflow_row_limit': 10001,
            'required_target_scope': 'EXCLUSIVE_RUN_TARGET'}
    digest = sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'status': 'RESULT_QUERY_PLAN_NOT_EXECUTABLE', 'plan': plan,
            'checksum': digest, 'actual_provenance': 'NOT_VERIFIED',
            'execution_authorized': False, 'qa_passed': False, 'release_ready': False}
