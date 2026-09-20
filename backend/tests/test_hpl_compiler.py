from copy import deepcopy
from hashlib import sha256
from xml.etree.ElementTree import fromstring
from app.hpl_compiler import compile_hpl
from test_etl_specification import design


def test_candidate_is_deterministic_portable_and_not_executable():
    spec, run, naming = design()
    before = deepcopy((spec, run, naming))
    result = compile_hpl(spec, run, naming)
    assert result == compile_hpl(spec, run, naming)
    assert before == (spec, run, naming)
    assert result['hpl_checksum'] == sha256(result['hpl'].encode()).hexdigest()
    assert result['execution_authorized'] is False
    assert result['compiler_status'] == 'HPL_CANDIDATE_NOT_EXECUTABLE'
    assert 'CSV_BYTES_AND_EXTRA_COLUMNS_POLICY' in result['required_checks']
    root = fromstring(result['hpl'])
    nodes = {node.findtext('name'): node for node in root.findall('transform')}
    assert len(nodes) == 7
    assert nodes['source'].findtext('filename') == '${SOURCE_CSV}'
    assert nodes['source'].findtext('lazy_conversion') == 'N'
    assert nodes['source'].findall('fields/field')[1].findtext('type') == 'BigNumber'
    assert nodes['filter'].findtext('send_true_to') == 'sort'
    assert nodes['filter'].findtext('send_false_to') == 'discard'
    assert [c.findtext('function') for c in nodes['filter'].findall('compare/condition/conditions/condition')] == ['IS NOT NULL', '>']
    assert [f.findtext('type') for f in nodes['aggregate'].findall('fields/field')] == ['SUM', 'COUNT_ANY']
    assert nodes['aggregate'].findtext('group/field/name') == 'category'
    assert nodes['target'].findtext('truncate') == 'N'
    assert nodes['target'].findtext('connection') == 'etl_target'
    assert [f.findtext('column_name') for f in nodes['target'].findall('fields/field')] == spec['output_columns']
    assert len(root.findall('order/hop')) == 6


def test_stale_input_cannot_emit_hpl():
    spec, run, naming = design()
    run['matches_current'] = False
    result = compile_hpl(spec, run, naming)
    assert result['status'] == 'INVALID' and 'hpl' not in result


def test_constant_xml_escaped_not_interpreted_as_nodes():
    spec, run, naming = design()
    spec['filters'] = [{'column': 'category', 'operator': 'NE', 'constant': {'type': 'STRING', 'value': '<SQL>&"'}}]
    root = fromstring(compile_hpl(spec, run, naming)['hpl'])
    assert root.find('.//value/text').text == '<SQL>&"'
    assert root.find('.//SQL') is None


def test_no_filter_omits_discard_and_dangling_routes():
    spec, run, naming = design()
    spec['filters'] = []
    root = fromstring(compile_hpl(spec, run, naming)['hpl'])
    assert len(root.findall('transform')) == 5
    assert len(root.findall('order/hop')) == 4
    assert root.find('.//send_false_to') is None


def test_null_predicate_has_no_contradictory_not_null_guard():
    spec, run, naming = design()
    spec['filters'] = [{'column': 'amount', 'operator': 'IS_NULL', 'constant': None}]
    root = fromstring(compile_hpl(spec, run, naming)['hpl'])
    assert [node.text for node in root.findall('.//function')] == ['IS NULL']


def test_count_non_null_has_distinct_native_code():
    spec, run, naming = design()
    spec['aggregation']['metrics'][1].update(function='COUNT_NON_NULL', column='amount')
    root = fromstring(compile_hpl(spec, run, naming)['hpl'])
    types = [node.text for node in root.findall('.//fields/field/type')]
    assert 'COUNT_ALL' in types and 'COUNT_ANY' not in types
