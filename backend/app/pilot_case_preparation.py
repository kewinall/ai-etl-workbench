"""Pure, fail-closed preparation of registered standard-v1 cases.

No uploads, database writes, model calls, fault injection or execution here.
The caller must persist upload receipts before creating/binding a Task; a fresh
upload on retry is not the same idempotent Task creation payload.
"""
from copy import deepcopy
from hashlib import sha256
from uuid import UUID, uuid5

from .pilot_fixture_catalog import canonical_bytes, corpus


def registered_case(definition):
    """Only exact frozen definitions are supported, not arbitrary references."""
    case = next((item for item in corpus()
                 if item['definition']['case_key'] == definition.get('case_key')), None)
    if case is None or canonical_bytes(case['definition']) != canonical_bytes(definition):
        raise ValueError('PILOT_REGISTERED_DEFINITION_MISMATCH')
    for part in ('fixture', 'oracle'):
        if sha256(canonical_bytes(case[part])).hexdigest() != definition[part + '_checksum']:
            raise ValueError('PILOT_CORPUS_CHECKSUM_MISMATCH')
    return case


def build_task_payload(project_id, cohort_id, definition, upload_receipts):
    """Receipts must come from the platform upload service, never from an LLM.

    This function checks receipt metadata; source_preflight independently reads
    the real uploaded bytes before a Run. Neither check grants execution.
    Oracle contents deliberately never enter the Task/model context.
    """
    project_id, cohort_id = str(UUID(str(project_id))), str(UUID(str(cohort_id)))
    case = registered_case(definition)
    fixture = case['fixture']
    if len(upload_receipts) != len(fixture['sources']):
        raise ValueError('PILOT_UPLOAD_COVERAGE_MISMATCH')
    sources = []
    for expected, receipt in zip(fixture['sources'], upload_receipts):
        content = expected['content'].encode('utf-8')
        if (receipt.get('source_type') != 'CSV'
                or receipt.get('original_name') != expected['filename']
                or receipt.get('checksum') != sha256(content).hexdigest()
                or type(receipt.get('size')) is not int
                or receipt['size'] != len(content)
                or [field.get('name') for field in receipt.get('fields', [])]
                   != [name for name, _ in expected['fields']]):
            raise ValueError('PILOT_UPLOAD_METADATA_MISMATCH')
        try:
            upload_id = str(UUID(receipt['upload_id']))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise ValueError('PILOT_UPLOAD_ID_INVALID') from None
        if not isinstance(receipt.get('path'), str) or not receipt['path']:
            raise ValueError('PILOT_UPLOAD_PATH_MISSING')
        sources.append({
            'type': 'CSV', 'has_actual_data': True, 'upload_id': upload_id,
            'path': receipt['path'], 'original_name': expected['filename'],
            'checksum': receipt['checksum'], 'size': receipt['size'],
            # Inference is advisory; frozen declared types are authoritative.
            'fields': [{'name': name, 'type': kind} for name, kind in expected['fields']],
        })
    config = {'sources': sources}
    if len(sources) == 1:
        config['csv_input_contract_v1'] = deepcopy(fixture['sources'][0]['csv_contract'])
    else:
        config['csv_input_contracts_v1'] = {'version': 1, 'sources': {
            f'source.{i}': deepcopy(item['csv_contract']) for i, item in enumerate(fixture['sources'])}}
    conditions = {'version': 1, 'write_mode': 'APPEND', 'date_scope': 'ALL',
                  'date_column': '', 'start_date': '', 'end_date_exclusive': '', 'key_columns': []}
    if definition['case_key'].endswith('-date-boundaries'):
        conditions.update(date_scope='RANGE', date_column='event_date',
                          start_date='2026-01-01', end_date_exclusive='2026-02-01')
    target = {'requirements_v1': conditions}
    if len(sources) == 2:
        target['join_contract_v1'] = {'version': 1, 'joins': [{
            'id': 'customer_orders', 'left_source': 'source.0', 'right_source': 'source.1',
            'join_type': 'LEFT', 'keys': [{'left_column': 'customer_id', 'right_column': 'customer_id'}],
            'null_key_policy': 'NEVER_MATCH', 'duplicate_key_policy': 'EXPAND',
            'string_comparison': 'CASE_SENSITIVE_NO_TRIM'}]}
    if definition['scenario'] == 'REQUIREMENT_GAP':
        change = fixture['initial_change']
        path = change['field']
        if path.startswith('requirements_v1.'):
            conditions[path.split('.')[1]] = deepcopy(change['initial'])
        elif path == 'join.keys':
            target['join_contract_v1']['joins'][0]['keys'] = deepcopy(change['initial'])
        elif path == 'csv_input_contract_v1.encoding':
            config['csv_input_contract_v1']['encoding'] = deepcopy(change['initial'])
        else:
            raise ValueError('PILOT_UNSUPPORTED_INITIAL_GAP')
    identity = f'{project_id}:{cohort_id}:{definition["case_key"]}'
    digest = sha256(identity.encode()).hexdigest()
    return {'creation_request_key': str(uuid5(UUID(cohort_id), identity)),
            'project_id': project_id, 'name': 'Pilot / ' + definition['case_key'],
            'requirement': fixture['confirmed_requirement'],
            'operation': 'NEW', 'category': 'STAGE', 'source_type': 'CSV',
            'source_config': config, 'target_type': 'VERTICA',
            'target_schema': 'ai_sample', 'target_table': 'pilot_' + digest[:32],
            'target_config': target, 'model': 'copilot', 'error_test_config': {}}
