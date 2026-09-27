"""Read-only enrichment; never changes executed bytes or attests external DDL drift."""
from hashlib import sha256
from .etl_specification import _type
from .qa_runtime_options import expected_options, inspect_options
from .sa_contract import digest


def expected_contract(spec, details):
    plan = details['compiler_plan']
    source = next(s for s in plan['stages'] if s['component'] == 'CSVInput')
    names = [field['source_name'] for field in source['fields']]
    if details['csv_structure_validation'].get('source_columns_checksum') != digest(names):
        raise ValueError('QA_SOURCE_COLUMN_BINDING_CHANGED')
    columns = [dict(name=name, type=_type(details['output_types'][name])[1], nullable=not(spec['version']==3 and name==spec['source_order']['ordinal_column']))
               for name in spec['output_columns']]
    ddl = (f'CREATE TABLE "{spec["target_schema"]}"."{spec["target_table"]}" (\n'
           + ',\n'.join(f'  "{c["name"]}" {c["type"]}' + ('' if c['nullable'] else ' NOT NULL') for c in columns) + '\n);\n')
    return dict(version=1, runtime_options=expected_options(plan, details['hpl_checksum']),
        header=dict(scope='SAME_BYTES_WHOLE_FILE_PREFLIGHT_NOT_HOP_HEADER_LOOKUP',
                    present=details['csv_input_contract']['header'],
                    matching='POSITIONAL_EXACT_CASE_SENSITIVE_NO_NORMALIZATION',
                    source_columns_checksum=digest(names)),
        target_ddl=dict(scope='COMPILER_DDL_MATCHES_PERSISTED_TARGET_CLAIM_NOT_CURRENT_CATALOG',
                        checksum=sha256(ddl.encode()).hexdigest(), columns=columns,
                        primary_key=[], write_mode=spec['write_mode'],
                        limitation='No attestation against subsequent external DBA schema changes.'))


def inspect_contract(compiled, details, claim):
    expected = expected_contract(compiled['specification'], details)
    if inspect_options(compiled) != expected['runtime_options']:
        raise ValueError('QA_RUNTIME_OPTIONS_CHANGED')
    spec = compiled['specification']
    required = dict(run_id=spec['run_id'], specification_checksum=compiled['specification_checksum'],
                    hpl_checksum=compiled['hpl_checksum'],
                    ddl_checksum=expected['target_ddl']['checksum'],
                    schema_name=spec['target_schema'], table_name=spec['target_table'],
                    settings_checksum=spec['settings_checksum'])
    if not claim or any(str(claim.get(k)) != str(v) for k, v in required.items()):
        raise ValueError('QA_TARGET_DDL_BINDING_CHANGED')
    return expected


def preserve_reviewed_context(record):
    """A successful historical review keeps its version; no retroactive migration."""
    return bool(record and record.get('status') == 'VALIDATED_NOT_APPROVED'
                and (record.get('output_json') or {}).get('review', {}).get('status') == 'PASS'
                and (record.get('input_json') or {}).get('context', {}).get('version') == 3)
