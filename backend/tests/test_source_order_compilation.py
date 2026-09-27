from copy import deepcopy
from xml.etree.ElementTree import fromstring

import pytest

from app.etl_specification import compilation_plan
from app.hpl_compiler import compile_hpl
from app.hwf_compiler import compile_hwf
from app.platform_harness import checksum
from app.result_query_plan import build_result_query_plan
from test_etl_specification import design


def ordered_design():
    spec, run, naming = design()
    columns = naming['contract_json']['columns'][:2] + [
        {'source_name': '$source_order.source.0', 'english_name': 'source_position', 'vertica_type': 'BIGINT'}]
    naming['contract_json']['columns'] = columns
    naming['checksum'] = checksum(columns)
    spec['naming']['checksum'] = naming['checksum']
    order = dict(version=1, source_ref='source.0', ordinal_column='source_position',
                 direction='ASC', semantics='LOGICAL_CSV_RECORD_POSITION')
    spec.update(version=3, filters=[], aggregation=None,
                output_columns=['category', 'amount', 'source_position'], source_order=order)
    target = run['input_snapshot']['target_config']
    target['source_order_v1'] = deepcopy(order)
    target['transformation_contract_v1'] = dict(version=1, filters=[], aggregation=None,
        filter_logic='ALL', filter_null_policy='EXCLUDE_UNKNOWN',
        output_columns=['source.0.類別', 'source.0.金額', '$source_order.source.0'])
    return spec, run, naming


def test_compiler_pins_generated_ordinal_and_ordered_query_without_mutation():
    args = ordered_design()
    before = deepcopy(args)
    result = compile_hwf(*args)
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    root = fromstring(result['hpl'])
    nodes = {n.findtext('name'): n for n in root.findall('transform')}
    source = nodes['source']
    assert source.findtext('rownum_field') == 'source_position'
    assert source.findtext('parallel') == 'N'
    assert source.findtext('copies') == '1'
    assert source.findtext('newline_possible') == 'Y'
    assert len(source.findall('fields/field')) == 2  # generated, not read from CSV
    assert source.findtext('filename') == '${SOURCE_CSV}'
    assert nodes['source_order_sort'].findtext('fields/field/name') == 'source_position'
    assert nodes['source_order_sort'].findtext('unique_rows') == 'N'
    assert result['output_types']['source_position'] == 'BIGINT'
    assert result['execution_authorized'] is False
    query = build_result_query_plan(*args)['plan']
    assert query['sql'].endswith('ORDER BY "source_position" ASC LIMIT 10001;')
    assert query['comparison'] == 'EXACT_SOURCE_SEQUENCE'
    assert query['source_order'] == args[0]['source_order']
    assert args == before


@pytest.mark.parametrize('mutation,code', [
    ('missing_contract', 'SPEC_SOURCE_ORDER_UNCONFIRMED'),
    ('changed_contract', 'SPEC_SOURCE_ORDER_MISMATCH'),
    ('missing_output', 'SPEC_SOURCE_ORDER_OUTPUT_MISSING'),
    ('filter', 'SPEC_SOURCE_ORDER_SCOPE_UNSUPPORTED'),
    ('legacy', 'SPEC_SOURCE_ORDER_MISMATCH'),
    ('wrong_type', 'SPEC_SOURCE_ORDER_NAMING_INVALID'),
])
def test_order_requirement_cannot_be_dropped_or_reinterpreted(mutation, code):
    spec, run, naming = ordered_design()
    target = run['input_snapshot']['target_config']
    if mutation == 'missing_contract':
        del target['source_order_v1']
    elif mutation == 'changed_contract':
        target['source_order_v1']['ordinal_column'] = 'different_position'
    elif mutation == 'missing_output':
        spec['output_columns'].remove('source_position')
    elif mutation == 'filter':
        spec['filters'] = [{'column': 'category', 'operator': 'IS_NOT_NULL', 'constant': None}]
    elif mutation == 'legacy':
        spec['version'] = 1
        del spec['source_order']
    elif mutation == 'wrong_type':
        naming['contract_json']['columns'][-1]['vertica_type'] = 'INTEGER'
        naming['checksum'] = checksum(naming['contract_json']['columns'])
        spec['naming']['checksum'] = naming['checksum']
    result = compile_hpl(spec, run, naming)
    assert result['status'] == 'INVALID'
    assert code in {i['code'] for i in result['issues']}
    assert 'hpl' not in result


def test_original_contract_remains_unordered_and_has_no_generated_field():
    args = design()
    result = compile_hpl(*args)
    assert result['specification'] == args[0]
    assert fromstring(result['hpl']).find('.//rownum_field') is None
    assert build_result_query_plan(*args)['plan']['comparison'] == 'EXACT_MULTISET'


def test_version_is_strict_and_cannot_inject_arbitrary_order_sql():
    for version in (True, [], {}, '3'):
        spec, run, naming = ordered_design()
        spec['version'] = version
        assert compilation_plan(spec, run, naming)['status'] == 'INVALID'
    spec, run, naming = ordered_design()
    spec['source_order']['ordinal_column'] = 'x;DROP TABLE y'
    assert compilation_plan(spec, run, naming)['status'] == 'INVALID'
