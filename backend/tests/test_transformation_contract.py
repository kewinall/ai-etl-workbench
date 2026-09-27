from copy import deepcopy
import pytest
from app.transformation_contract import TransformationContractV1, intent_issues, parsed_intent
from app.etl_specification import validate_specification
from app.hpl_compiler import compile_hpl
from app.sa_contract import build_sa_context
from test_etl_specification import design


def intent():
    return {'version': 1,
        'filters': [{'column': 'source.0.金額', 'operator': 'GT', 'constant': {'type': 'DECIMAL', 'value': '100.00'}}],
        'filter_logic': 'ALL', 'filter_null_policy': 'EXCLUDE_UNKNOWN',
        'aggregation': {'group_by': ['source.0.類別'], 'null_policy': 'SQL_NULLS', 'metrics': [
            {'id': 'total', 'function': 'SUM', 'column': 'source.0.金額'},
            {'id': 'count', 'function': 'COUNT_ROWS', 'column': None}]},
        'output_columns': ['source.0.類別', '$metric.total', '$metric.count']}


def confirmed():
    spec, run, naming = design()
    run['input_snapshot']['target_config']['transformation_contract_v1'] = intent()
    return spec, run, naming


def test_matching_source_identity_resolves_through_confirmed_chinese_naming():
    spec, run, naming = confirmed()
    before = deepcopy((spec, run, naming))
    assert compile_hpl(spec, run, naming)['status'] == 'VALIDATED_NOT_APPROVED'
    assert before == (spec, run, naming)
    context = build_sa_context(run)
    assert context['version'] == 3
    assert next(e['value'] for e in context['evidence'] if e['id'] == 'transformation.conditions') == intent()


@pytest.mark.parametrize('field,value,path,node', [
    ('operator', 'GE', 'filters.0.operator', 'filter'),
    ('constant', {'type': 'DECIMAL', 'value': '20.00'}, 'filters.0.constant.value', 'filter'),
])
def test_filter_semantic_mutation_never_compiles(field, value, path, node):
    spec, run, naming = confirmed()
    spec['filters'][0][field] = value
    result = compile_hpl(spec, run, naming)
    assert result['status'] == 'INVALID' and not result['execution_authorized']
    issue = next(i for i in result['issues'] if i['code'] == 'SPEC_TRANSFORMATION_INTENT_MISMATCH')
    assert issue['field_path'] == path and issue['node_id'] == node
    assert issue['requirement_path'] == 'transformation_contract_v1.' + path
    assert issue['expected'] != issue['actual']
    assert not any(k in result for k in ('hpl', 'plan', 'specification_checksum'))


def test_count_rows_cannot_change_to_count_non_null():
    spec, run, naming = confirmed()
    spec['aggregation']['metrics'][1].update(function='COUNT_NON_NULL', column='category')
    result = compile_hpl(spec, run, naming)
    issues = [i for i in result['issues'] if i['code'] == 'SPEC_TRANSFORMATION_INTENT_MISMATCH']
    assert {i['field_path'] for i in issues} == {'aggregation.metrics.1.function', 'aggregation.metrics.1.column'}
    assert all(i['node_id'] == 'aggregate' for i in issues)
    assert 'hpl' not in result


@pytest.mark.parametrize('mutation', ['remove_filter', 'remove_aggregation', 'swap_output', 'remove_metric'])
def test_semantic_structure_changes_are_not_ignored(mutation):
    spec, run, naming = confirmed()
    if mutation == 'remove_filter': spec['filters'] = []
    elif mutation == 'remove_aggregation': spec['aggregation'] = None
    elif mutation == 'swap_output': spec['output_columns'].reverse()
    else: spec['aggregation']['metrics'].pop()
    assert any(i['code'] == 'SPEC_TRANSFORMATION_INTENT_MISMATCH' for i in validate_specification(spec, run, naming)['issues'])


@pytest.mark.parametrize('mutation', ['null', 'unknown', 'duplicate_output', 'duplicate_metric', 'bool_version', 'sql'])
def test_invalid_contract_blocks_gate_without_echoing_untrusted_fields(mutation):
    _, run, _ = confirmed()
    value = run['input_snapshot']['target_config']['transformation_contract_v1']
    if mutation == 'null': run['input_snapshot']['target_config']['transformation_contract_v1'] = None
    elif mutation == 'unknown': value['filters'][0]['column'] = 'source.1.金額'
    elif mutation == 'duplicate_output': value['output_columns'].append(value['output_columns'][0])
    elif mutation == 'duplicate_metric': value['aggregation']['metrics'][1]['id'] = 'total'
    elif mutation == 'bool_version': value['version'] = True
    else: value['sql'] = 'PRIVATE_UNTRUSTED'
    issues = intent_issues(run['input_snapshot'])
    assert len(issues) == 1 and 'PRIVATE_UNTRUSTED' not in str(issues)
    from app.control_worker import check_requirements
    assert check_requirements(run['input_snapshot'])['status'] == 'NEEDS_INPUT'


def test_absence_preserves_legacy_context_and_behavior_but_not_null_contract():
    spec, run, naming = design()
    assert parsed_intent(run['input_snapshot']) is None
    assert build_sa_context(run)['version'] == 2
    assert validate_specification(spec, run, naming)['status'] == 'VALIDATED_NOT_APPROVED'
    run['input_snapshot']['target_config']['transformation_contract_v1'] = None
    assert validate_specification(spec, run, naming)['status'] == 'INVALID'


def test_missing_metric_naming_never_guesses_alias():
    spec, run, naming = confirmed()
    naming['contract_json']['columns'].pop()
    assert 'SPEC_INTENT_NAMING_MISSING' in {i['code'] for i in validate_specification(spec, run, naming)['issues']}


def test_editor_probe_does_not_block_real_intent_but_invalid_contract_still_blocks():
    from app.specification_editor import editor_context
    spec, run, naming = confirmed()
    assert editor_context(run, naming)['status'] == 'EDITOR_CONTEXT_READY'
    run['input_snapshot']['target_config']['transformation_contract_v1'] = None
    assert editor_context(run, naming)['status'] == 'BLOCKED'


def test_two_sources_keep_distinct_qualified_identities():
    from test_join_semantics import join_design
    spec, run, naming = join_design()
    columns = naming['contract_json']['columns']
    refs = [c['source_name'] for c in columns]
    value = {'version': 1, 'filters': [], 'filter_logic': 'ALL', 'filter_null_policy': 'EXCLUDE_UNKNOWN',
             'aggregation': None, 'output_columns': refs}
    run['input_snapshot']['target_config']['transformation_contract_v1'] = value
    assert validate_specification(spec, run, naming)['status'] == 'VALIDATED_NOT_APPROVED'
    spec['output_columns'][0], spec['output_columns'][2] = spec['output_columns'][2], spec['output_columns'][0]
    assert any(i['code'] == 'SPEC_TRANSFORMATION_INTENT_MISMATCH' and i['node_id'] == 'projection'
               for i in validate_specification(spec, run, naming)['issues'])
