from copy import deepcopy
from uuid import uuid4
import pytest
from app.etl_specification import compilation_plan, validate_specification, FilterConstantV1
from app.platform_harness import checksum


def design():
    run_id, contract_id = uuid4(), uuid4()
    columns = [
        {'source_name': '類別', 'english_name': 'category', 'vertica_type': 'VARCHAR(32)'},
        {'source_name': '金額', 'english_name': 'amount', 'vertica_type': 'NUMERIC(12,2)'},
        {'source_name': '$metric.total', 'english_name': 'total_amount', 'vertica_type': 'NUMERIC(18,2)'},
        {'source_name': '$metric.count', 'english_name': 'row_count', 'vertica_type': 'BIGINT'},
    ]
    naming = {'task_id': 'spec-test', 'contract_id': contract_id, 'version': 1, 'status': 'CONFIRMED', 'contract_json': {'columns': columns}, 'checksum': checksum(columns)}
    run = {'task_id': 'spec-test', 'run_id': run_id, 'input_checksum': 'a'*64, 'settings_snapshot': {'checksum': 'b'*64}, 'matches_current': True,
           'approval': {'decision': 'APPROVE'}, 'state': 'NEEDS_REVIEW', 'write_started': False, 'gate_result': {'status': 'CHECKED'},
           'input_snapshot': {'requirement_text': '按類別彙總金額大於 100 的資料，輸出總額與筆數', 'source_type': 'CSV', 'source_config': {
               'sources': [{'type': 'CSV', 'has_actual_data': False, 'fields': [{'name': '類別', 'type': 'VARCHAR(32)'}, {'name': '金額', 'type': 'NUMERIC(12,2)'}]}],
               'csv_input_contract_v1': {'version': 1, 'encoding': 'UTF-8', 'delimiter': ',', 'header': True, 'extra_columns': 'REJECT'}},
               'target_config': {'schema': 'ai_sample', 'table': 'totals', 'requirements_v1': {'write_mode': 'APPEND', 'date_scope': 'ALL'}}}}
    spec = {'version': 1, 'run_id': str(run_id), 'input_checksum': 'a'*64, 'settings_checksum': 'b'*64,
            'naming': {'contract_id': str(contract_id), 'version': 1, 'checksum': naming['checksum']}, 'source_ref': 'source.0',
            'target_schema': 'ai_sample', 'target_table': 'totals', 'write_mode': 'APPEND',
            'filters': [{'column': 'amount', 'operator': 'GT', 'constant': {'type': 'DECIMAL', 'value': '100.00'}}],
            'filter_logic': 'ALL', 'filter_null_policy': 'EXCLUDE_UNKNOWN',
            'aggregation': {'group_by': ['category'], 'null_policy': 'SQL_NULLS', 'metrics': [
                {'id': 'total', 'function': 'SUM', 'column': 'amount', 'output_column': 'total_amount'},
                {'id': 'count', 'function': 'COUNT_ROWS', 'column': None, 'output_column': 'row_count'}]},
            'output_columns': ['category', 'total_amount', 'row_count']}
    return spec, run, naming


def codes(result):
    return {item['code'] for item in result['issues']}


def test_filter_aggregate_plan_exact_and_deterministic_without_mutation():
    spec, run, naming = design()
    before = deepcopy((spec, run, naming))
    result = compilation_plan(spec, run, naming)
    assert result == compilation_plan(spec, run, naming)
    assert (spec, run, naming) == before
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    assert result['execution_authorized'] is False
    assert result['compiler_status'] == 'PLAN_ONLY_HPL_NOT_GENERATED'
    assert [stage['component'] for stage in result['plan']['stages']] == ['CSVInput', 'FilterRows', 'SortRows', 'GroupBy', 'SelectValues', 'TableOutput']
    assert result['plan']['stages'][1]['predicates'] == spec['filters']
    assert result['plan']['stages'][0]['fields'][1] == {'source_name': '金額', 'stream_name': 'amount', 'data_type': 'NUMERIC(12,2)'}
    assert result['plan']['stages'][1]['on_false'] == 'DISCARD'
    assert result['plan']['stages'][2]['columns'] == ['category']
    assert result['plan']['stages'][2]['case_sensitive'] is True
    assert result['output_types'] == {'category': 'VARCHAR(32)', 'total_amount': 'NUMERIC(18,2)', 'row_count': 'BIGINT'}
    assert 'row_limit' not in str(result) and 'First 10' not in str(result)
    assert result['plan']['edges'][2] == {'from': 'sort', 'to': 'aggregate'}


@pytest.mark.parametrize('field,value', [('sql', 'SELECT * FROM business'), ('joins', []), ('row_limit', 10), ('filters', [{'column': 'amount', 'operator': 'SQL', 'constant': None}]), ('target_table', 'x;drop table x'), ('filter_logic', 'OR'), ('version', True)])
def test_unsupported_or_arbitrary_code_not_silently_dropped(field, value):
    spec, run, naming = design(); spec[field] = value
    assert codes(compilation_plan(spec, run, naming)) == {'SPEC_SCHEMA_INVALID'}


@pytest.mark.parametrize('field,value', [('input_checksum', 'c'*64), ('settings_checksum', 'c'*64), ('run_id', str(uuid4()))])
def test_exact_run_identity_required(field, value):
    spec, run, naming = design(); spec[field] = value
    assert 'SPEC_VERSION_MISMATCH' in codes(validate_specification(spec, run, naming))


@pytest.mark.parametrize('field,value', [('matches_current', False), ('approval', None), ('state', 'RUNNING'), ('write_started', True)])
def test_stale_unapproved_and_writing_runs_rejected(field, value):
    spec, run, naming = design(); run[field] = value
    assert 'SPEC_INPUT_NOT_APPROVED' in codes(validate_specification(spec, run, naming))


@pytest.mark.parametrize('field,value,expected', [('status', 'DRAFT', 'SPEC_NAMING_UNCONFIRMED'), ('task_id', 'other', 'SPEC_NAMING_UNCONFIRMED'), ('version', 2, 'SPEC_NAMING_VERSION_MISMATCH'), ('checksum', 'c'*64, 'SPEC_NAMING_VERSION_MISMATCH')])
def test_naming_must_be_exact_current_confirmed_task_contract(field, value, expected):
    spec, run, naming = design(); naming[field] = value
    assert expected in codes(validate_specification(spec, run, naming))


def test_modified_naming_columns_cannot_reuse_checksum():
    spec, run, naming = design(); naming['contract_json']['columns'][0]['english_name'] = 'different'
    assert 'SPEC_NAMING_VERSION_MISMATCH' in codes(validate_specification(spec, run, naming))


def test_missing_csv_contract_blocks_regardless_of_historical_gate():
    spec, run, naming = design(); run['input_snapshot']['source_config'].pop('csv_input_contract_v1')
    assert 'SPEC_GATE_BLOCKED' in codes(validate_specification(spec, run, naming))


def test_filter_unknown_column_and_type_are_reported():
    spec, run, naming = design(); spec['filters'][0]['column'] = 'unknown'
    assert 'SPEC_FILTER_COLUMN_UNKNOWN' in codes(validate_specification(spec, run, naming))
    spec['filters'][0]['column'] = 'category'
    assert 'SPEC_FILTER_TYPE_MISMATCH' in codes(validate_specification(spec, run, naming))


def test_group_and_projection_cannot_reference_pre_aggregation_fields():
    spec, run, naming = design(); spec['output_columns'].append('amount')
    assert 'SPEC_OUTPUT_COLUMNS_INVALID' in codes(validate_specification(spec, run, naming))
    spec['aggregation']['group_by'] = ['category', 'category']
    assert 'SPEC_GROUP_COLUMNS_INVALID' in codes(validate_specification(spec, run, naming))


def test_metric_alias_collision_and_type_loss_are_rejected():
    spec, run, naming = design(); spec['aggregation']['metrics'][0]['output_column'] = 'category'
    result = validate_specification(spec, run, naming)
    assert {'SPEC_METRIC_COLLISION', 'SPEC_METRIC_NAMING_MISSING', 'SPEC_METRIC_TYPE_MISMATCH'} <= codes(result)
    spec, run, naming = design(); naming['contract_json']['columns'][2]['vertica_type'] = 'NUMERIC(8,2)'
    naming['checksum'] = checksum(naming['contract_json']['columns']); spec['naming']['checksum'] = naming['checksum']
    assert 'SPEC_METRIC_TYPE_MISMATCH' in codes(validate_specification(spec, run, naming))


@pytest.mark.parametrize('kind,value', [('INTEGER', True), ('INTEGER', '10'), ('DECIMAL', 1.1), ('DECIMAL', 'NaN'), ('DECIMAL', '1e3'), ('DATE', '2026-02-30'), ('BOOLEAN', 'false'), ('STRING', 1)])
def test_constants_are_exact_not_coerced(kind, value):
    with pytest.raises(ValueError):
        FilterConstantV1.model_validate({'type': kind, 'value': value})


def test_null_predicate_is_explicit():
    spec, run, naming = design(); spec['filters'] = [{'column': 'amount', 'operator': 'IS_NULL', 'constant': None}]
    assert validate_specification(spec, run, naming)['status'] == 'VALIDATED_NOT_APPROVED'
    spec['filters'][0]['constant'] = {'type': 'INTEGER', 'value': 1}
    assert 'SPEC_SCHEMA_INVALID' in codes(validate_specification(spec, run, naming))


def test_plain_projection_does_not_add_filter_or_calculation():
    spec, run, naming = design(); spec.update(filters=[], aggregation=None, output_columns=['category', 'amount'])
    naming['contract_json']['columns'] = naming['contract_json']['columns'][:2]
    naming['checksum'] = checksum(naming['contract_json']['columns']); spec['naming']['checksum'] = naming['checksum']
    result = compilation_plan(spec, run, naming)
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    assert [stage['component'] for stage in result['plan']['stages']] == ['CSVInput', 'SelectValues', 'TableOutput']


def test_source_type_cannot_silently_change_via_naming():
    spec, run, naming = design(); run['input_snapshot']['source_config']['sources'][0]['fields'][1]['type'] = 'BOOLEAN'
    assert 'SPEC_SOURCE_TYPE_MISMATCH' in codes(validate_specification(spec, run, naming))


@pytest.mark.parametrize('column,changed_type', [(0, 'VARCHAR(8)'), (1, 'NUMERIC(8,2)'), (1, 'NUMERIC(12,1)')])
def test_confirmed_naming_still_cannot_narrow_source_metadata(column, changed_type):
    spec, run, naming = design()
    naming['contract_json']['columns'][column]['vertica_type'] = changed_type
    naming['checksum'] = checksum(naming['contract_json']['columns']); spec['naming']['checksum'] = naming['checksum']
    assert 'SPEC_SOURCE_TYPE_NARROWING' in codes(validate_specification(spec, run, naming))


def test_write_mode_never_downgraded_and_date_range_never_ignored():
    spec, run, naming = design(); spec['write_mode'] = 'REPLACE'
    result = validate_specification(spec, run, naming)
    assert {'SPEC_TARGET_MISMATCH', 'SPEC_WRITE_MODE_UNSUPPORTED'} <= codes(result)
    run['input_snapshot']['target_config']['requirements_v1']['date_scope'] = 'RANGE'
    assert 'SPEC_DATE_RANGE_FILTER_MISMATCH' in codes(validate_specification(spec, run, naming))


def test_bigint_source_cannot_be_narrowed_to_integer_by_naming():
    spec, run, naming = design()
    run['input_snapshot']['source_config']['sources'][0]['fields'][1]['type'] = 'BIGINT'
    naming['contract_json']['columns'][1]['vertica_type'] = 'INTEGER'
    naming['checksum'] = checksum(naming['contract_json']['columns']); spec['naming']['checksum'] = naming['checksum']
    assert 'SPEC_SOURCE_TYPE_NARROWING' in codes(validate_specification(spec, run, naming))
