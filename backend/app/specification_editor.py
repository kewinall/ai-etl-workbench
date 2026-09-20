"""Safe field-based editor context, not a generated or approved ETL design."""
import re
from .etl_specification import validate_specification, _type, IDENTIFIER


def editor_context(run, naming):
    blocked = {'status': 'BLOCKED', 'execution_authorized': False}
    if not naming:
        return {**blocked, 'issues': [{'code': 'SPEC_NAMING_MISSING', 'message': '請先確認來源及聚合輸出的命名契約。'}]}
    target = run['input_snapshot'].get('target_config') or {}
    columns = naming['contract_json'].get('columns') or []
    source = []
    metrics = []
    fields = (run['input_snapshot'].get('source_config') or {}).get('sources') or []
    originals = [f['name'] for f in fields[0].get('fields', [])] if len(fields) == 1 else []
    mapping = {c.get('source_name'): c for c in columns}
    for name in originals:
        column = mapping.get(name, {})
        kind = _type(column.get('vertica_type'))
        source.append({'source_name': name, 'name': column.get('english_name', ''), 'data_type': column.get('vertica_type', ''), 'constant_type': kind[0] if kind else None})
    for column in columns:
        name = column.get('source_name', '')
        if name in originals:
            continue
        if not name.startswith('$metric.') or not re.fullmatch(IDENTIFIER, name[8:]):
            return {**blocked, 'issues': [{'code': 'SPEC_EDITOR_NAMING_UNSUPPORTED', 'message': '命名契約含非來源、非聚合的欄位，請先補正。'}]}
        metrics.append({'id': name[8:], 'output_column': column['english_name'], 'data_type': column['vertica_type']})
    binding = {'version': 1, 'run_id': str(run['run_id']), 'input_checksum': run['input_checksum'],
               'settings_checksum': run['settings_snapshot']['checksum'],
               'naming': {'contract_id': str(naming['contract_id']), 'version': naming['version'], 'checksum': naming['checksum']},
               'source_ref': 'source.0', 'target_schema': target.get('schema'), 'target_table': target.get('table'),
               'write_mode': (target.get('requirements_v1') or {}).get('write_mode'),
               'filter_logic': 'ALL', 'filter_null_policy': 'EXCLUDE_UNKNOWN'}
    # Probe existing invariant validator; this is not returned as a proposed design.
    # Metric coverage alone is expected to be incomplete until the user specifies it.
    probe = validate_specification({**binding, 'filters': [], 'aggregation': None, 'output_columns': [c['name'] for c in source]}, run, naming)
    issues = [issue for issue in probe['issues'] if issue['code'] != 'SPEC_NAMING_COVERAGE_MISMATCH']
    if issues:
        return {**blocked, 'issues': issues}
    return {'status': 'EDITOR_CONTEXT_READY', 'binding': binding, 'source_columns': source, 'metric_columns': metrics,
            'execution_authorized': False, 'issues': []}
