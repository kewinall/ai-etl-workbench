from copy import deepcopy
from hashlib import sha256
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.qa_runtime_options import inspect_options
from test_json_specification import json_design


def test_json_three_node_options_are_independently_inspected():
    compiled = compile_hpl(*json_design())
    details = inspect_options(compiled)
    assert details['version'] == 3
    assert len(details['sources']) == 1
    source = details['sources'][0]
    assert source['component'] == 'JsonInput'
    assert source['fields'][0]['path'] == '$.[*]["類別"]'
    assert source['options']['defaultPathLeafToNull'] == 'Y'
    assert source['options']['removeSourceField'] == 'N'
    assert source['filename']['field']['nullif'] == '${SOURCE_JSON}'
    assert [f['name'] for f in source['projection']['fields']] == ['category', 'amount']
    assert 'json_source_file' not in [f['name'] for f in source['projection']['fields']]
    assert source['launcher_requirement']['receipt_required'] is True
    assert 'not this Run' in details['behavior_reference']['limits']


def test_generic_catalog_stays_closed_but_exact_reviewed_json_fragment_is_allowed():
    from app.hop_generation_rules import validate_pipeline_graph
    compiled = compile_hpl(*json_design()); root = ET.fromstring(compiled['hpl'])
    assert len(validate_pipeline_graph(root)) == 2
    assert validate_pipeline_graph(root, json_compilation=compiled) == []
    root.find("transform[name='source']/readurl").text = 'Y'
    assert validate_pipeline_graph(root, json_compilation=compiled)
    compiled['hpl'] = ET.tostring(root, encoding='unicode')
    compiled['hpl_checksum'] = sha256(compiled['hpl'].encode()).hexdigest()
    assert validate_pipeline_graph(root, json_compilation=compiled)


def test_reviewed_json_does_not_allow_extra_row_generator_or_script():
    from app.hop_generation_rules import validate_pipeline_graph
    compiled = compile_hpl(*json_design()); root = ET.fromstring(compiled['hpl'])
    extra = deepcopy(root.find("transform[name='source_file']")); extra.find('name').text = 'other'
    root.append(extra)
    compiled['hpl'] = ET.tostring(root, encoding='unicode')
    compiled['hpl_checksum'] = sha256(compiled['hpl'].encode()).hexdigest()
    assert any('RowGenerator' in error for error in validate_pipeline_graph(root, json_compilation=compiled))
    extra.find('type').text = 'ScriptValueMod'
    compiled['hpl'] = ET.tostring(root, encoding='unicode')
    compiled['hpl_checksum'] = sha256(compiled['hpl'].encode()).hexdigest()
    assert any('ScriptValueMod' in error for error in validate_pipeline_graph(root, json_compilation=compiled))


@pytest.mark.parametrize('node,path,value', [
    ('source', 'doNotFailIfNoFile', 'Y'), ('source', 'ignoreMissingPath', 'Y'),
    ('source', 'defaultPathLeafToNull', 'N'), ('source', 'removeSourceField', 'Y'),
    ('source', 'readurl', 'Y'), ('source', 'IsIgnoreEmptyFile', 'Y'), ('source', 'limit', '1'),
    ('source', 'IsInFields', 'N'), ('source', 'IsAFile', 'N'), ('source', 'valueField', 'other'),
    ('source', 'fields/field/path', '$[*]'), ('source', 'fields/field/type', 'Integer'),
    ('source', 'fields/field/trim_type', 'both'), ('source', 'fields/field/repeat', 'Y'),
    ('source', 'fields/field/format', 'changed'), ('source', 'fields/field/length', '1'),
    ('source_file', 'fields/field/nullif', '${SOURCE_CSV}'), ('source_file', 'limit', '2'),
    ('source_file', 'never_ending', 'Y'), ('source_file', 'copies', '2'),
    ('source_columns', 'fields/select_unspecified', 'Y'), ('source_columns', 'fields/field/name', 'json_source_file'),
    ('source_columns', 'fields/field/rename', 'other'), ('source_columns', 'fields/field/precision', '2'),
])
def test_changed_json_options_rejected_with_recomputed_xml_checksum(node, path, value):
    compiled = compile_hpl(*json_design()); root = ET.fromstring(compiled['hpl'])
    element = root.find(f"transform[name='{node}']/{path}")
    assert element is not None
    element.text = value
    compiled['hpl'] = ET.tostring(root, encoding='unicode')
    compiled['hpl_checksum'] = sha256(compiled['hpl'].encode()).hexdigest()
    with pytest.raises(ValueError, match='QA_RUNTIME_JSON_'):
        inspect_options(compiled)


@pytest.mark.parametrize('mutation', ['node', 'field', 'option', 'unknown_option', 'hop', 'disabled_hop', 'plan_source', 'plan_edge'])
def test_duplicate_or_changed_json_topology_rejected(mutation):
    compiled = compile_hpl(*json_design()); root = ET.fromstring(compiled['hpl'])
    source = root.find("transform[name='source']")
    if mutation == 'node': root.append(deepcopy(source))
    elif mutation == 'field': source.find('fields').append(deepcopy(source.find('fields/field')))
    elif mutation == 'option': source.append(deepcopy(source.find('readurl')))
    elif mutation == 'unknown_option': ET.SubElement(source, 'ignore_errors').text = 'Y'
    elif mutation == 'hop': root.find('order').append(deepcopy(root.find('order/hop')))
    elif mutation == 'disabled_hop': root.find('order/hop/enabled').text = 'N'
    elif mutation == 'plan_source': compiled['plan']['stages'][0]['parameter'] = 'SOURCE_CSV'
    elif mutation == 'plan_edge': compiled['plan']['edges'][0]['to'] = 'source_columns'
    compiled['hpl'] = ET.tostring(root, encoding='unicode')
    compiled['hpl_checksum'] = sha256(compiled['hpl'].encode()).hexdigest()
    with pytest.raises(ValueError, match='QA_RUNTIME_'):
        inspect_options(compiled)
