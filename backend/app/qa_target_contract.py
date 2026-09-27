"""Multi-source target DDL evidence, not a current catalog attestation."""
from hashlib import sha256
from .etl_specification import _type


def expected_target(spec, details):
    columns = [dict(name=n, type=_type(details['output_types'][n])[1], nullable=not(spec['version']==3 and n==spec['source_order']['ordinal_column']))
               for n in spec['output_columns']]
    ddl = (f'CREATE TABLE "{spec["target_schema"]}"."{spec["target_table"]}" (\n'
           + ',\n'.join(f'  "{c["name"]}" {c["type"]}' + ('' if c['nullable'] else ' NOT NULL') for c in columns) + '\n);\n')
    return dict(version=1, scope='COMPILER_DDL_MATCHES_PERSISTED_TARGET_CLAIM_NOT_CURRENT_CATALOG',
                checksum=sha256(ddl.encode()).hexdigest(), columns=columns,
                primary_key=[], defaults=[], constraints=[], write_mode=spec['write_mode'],
                limitation='No attestation against subsequent external DBA schema changes.')


def inspect_target(compiled, details, claim):
    spec = compiled['specification']; expected = expected_target(spec, details)
    required = dict(run_id=spec['run_id'], specification_checksum=compiled['specification_checksum'],
                    hpl_checksum=compiled['hpl_checksum'], ddl_checksum=expected['checksum'],
                    schema_name=spec['target_schema'], table_name=spec['target_table'],
                    settings_checksum=spec['settings_checksum'])
    if not claim or any(str(claim.get(k)) != str(v) for k,v in required.items()):
        raise ValueError('QA_TARGET_DDL_BINDING_CHANGED')
    return expected


def should_enrich(record):
    if not record:
        return True
    details = record['input_json']['context'].get('semantics', {}).get('execution_details') or {}
    if details.get('target_contract'):
        return True
    return (record.get('status') == 'VALIDATED_NOT_APPROVED'
            and (record.get('output_json') or {}).get('review', {}).get('status') == 'NEEDS_REVIEW')
