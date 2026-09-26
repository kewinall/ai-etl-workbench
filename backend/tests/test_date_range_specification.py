from copy import deepcopy
import pytest
from app.etl_specification import validate_specification
from app.hpl_compiler import compile_hpl
from app.platform_harness import checksum
from test_etl_specification import design, codes


def date_design(kind='DATE'):
    spec, run, naming = design()
    run['input_snapshot']['source_config']['sources'][0]['fields'].append({'name': '日期', 'type': kind})
    columns = naming['contract_json']['columns']
    columns.append({'source_name': '日期', 'english_name': 'event_date', 'vertica_type': kind})
    naming['checksum'] = checksum(columns)
    spec['naming']['checksum'] = naming['checksum']
    run['input_snapshot']['target_config']['requirements_v1'].update(
        date_scope='RANGE', date_column='日期', start_date='2026-09-01', end_date_exclusive='2026-10-01')
    spec['filters'].extend([
        {'column': 'event_date', 'operator': 'GE', 'constant': {'type': 'DATE', 'value': '2026-09-01'}},
        {'column': 'event_date', 'operator': 'LT', 'constant': {'type': 'DATE', 'value': '2026-10-01'}}])
    return spec, run, naming


@pytest.mark.parametrize('kind', ['DATE', 'TIMESTAMP'])
def test_exact_range_compiles_without_changing_approved_inputs(kind):
    from xml.etree import ElementTree as ET
    spec, run, naming = date_design(kind)
    before = deepcopy((spec, run, naming))
    result = compile_hpl(spec, run, naming)
    assert result['status'] == 'VALIDATED_NOT_APPROVED', result
    assert not result['execution_authorized']
    assert (spec, run, naming) == before
    root = ET.fromstring(result['hpl'])
    predicates = root.findall("./transform[type='FilterRows']/compare/condition/conditions/condition")
    comparisons = [(p.findtext('function'), p.findtext('value/text'), p.findtext('value/mask'))
                   for p in predicates if p.findtext('leftvalue') == 'event_date' and p.find('value') is not None]
    assert comparisons == [('>=', '2026-09-01', 'yyyy-MM-dd'), ('<', '2026-10-01', 'yyyy-MM-dd')]


@pytest.mark.parametrize('change', ['missing_start', 'missing_end', 'inclusive_end', 'exclusive_start',
                                  'wrong_date', 'wrong_column', 'duplicate', 'extra', 'null', 'string'])
def test_changed_or_incomplete_interval_is_rejected(change):
    spec, run, naming = date_design()
    if change == 'missing_start': spec['filters'].pop(1)
    elif change == 'missing_end': spec['filters'].pop(2)
    elif change == 'inclusive_end': spec['filters'][2]['operator'] = 'LE'
    elif change == 'exclusive_start': spec['filters'][1]['operator'] = 'GT'
    elif change == 'wrong_date': spec['filters'][1]['constant']['value'] = '2026-09-02'
    elif change == 'wrong_column': spec['filters'][1]['column'] = 'category'
    elif change == 'duplicate': spec['filters'].append(deepcopy(spec['filters'][1]))
    elif change == 'extra': spec['filters'].append({'column': 'event_date', 'operator': 'NE', 'constant': {'type': 'DATE', 'value': '2026-09-15'}})
    elif change == 'null': spec['filters'][1].update(operator='IS_NULL', constant=None)
    elif change == 'string': spec['filters'][1]['constant']['type'] = 'STRING'
    result = compile_hpl(spec, run, naming)
    assert 'SPEC_DATE_RANGE_FILTER_MISMATCH' in codes(result)
    assert 'hpl' not in result


def test_range_cannot_be_lexical_string_comparison():
    spec, run, naming = date_design('VARCHAR(32)')
    assert 'SPEC_DATE_RANGE_COLUMN_TYPE' in codes(validate_specification(spec, run, naming))


def test_range_revision_cannot_reuse_old_specification_or_approval():
    spec, run, naming = date_design()
    run['input_snapshot']['target_config']['requirements_v1']['start_date'] = '2026-09-02'
    run['input_checksum'] = 'c' * 64
    run['approval'] = None
    found = codes(validate_specification(spec, run, naming))
    assert {'SPEC_VERSION_MISMATCH', 'SPEC_INPUT_NOT_APPROVED', 'SPEC_DATE_RANGE_FILTER_MISMATCH'} <= found
