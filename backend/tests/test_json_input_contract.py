import pytest
from app.json_input_contract import validate_json_content
from app.json_input_compiler import json_input_fragment, json_field_path


def policy(root_shape='ARRAY'):
    return dict(version=1, encoding='UTF-8-SIG', bom_handling='REMOVE_UTF8_BOM', root_shape=root_shape, missing_keys='NULL',
                extra_keys='REJECT', nested_values='REJECT', duplicate_keys='REJECT',
                trim_strings='NONE', null_records='PRESERVE', on_error='FAIL')


def test_full_structural_proof_has_no_conversion_or_execution_authority():
    result = validate_json_content(b'[{"id":"001","x":1},{"id":"002"},{}]', policy(), ['id', 'x'])
    assert result['records_expected'] == 3 and result['complete'] is True
    assert result['execution_authorized'] is False and result['type_conversion_verified'] is False
    assert result['column_statistics'][1]['missing_count'] == 2
    assert len(result['contract_checksum']) == len(result['field_names_checksum']) == 64


@pytest.mark.parametrize('content,names,code', [
    (b'{"id":1}', ['id'], 'JSON_ROOT_SHAPE_MISMATCH'),
    (b'[{"id":1,"extra":2}]', ['id'], 'JSON_COLUMN_BINDING_MISMATCH'),
    (b'[{"id":1}]', ['id', 'missing'], 'JSON_COLUMN_BINDING_MISMATCH'),
    (b'[{"x":1,"id":1}]', ['id', 'x'], 'JSON_COLUMN_BINDING_MISMATCH'),
    (b'[{"id":1}]', ['id', 'id'], 'JSON_FIELDS_INVALID'),
    (b'[{"id":1}]', [None], 'JSON_FIELDS_INVALID'),
    (b'[{"id":1}]', [], 'JSON_FIELDS_INVALID'),
    ('not-bytes', ['id'], 'JSON_BYTES_OR_SIZE_INVALID'),
    (b'', ['id'], 'JSON_BYTES_OR_SIZE_INVALID'),
])
def test_content_or_confirmed_columns_cannot_drift(content, names, code):
    with pytest.raises(ValueError, match=code):
        validate_json_content(content, policy(), names)


@pytest.mark.parametrize('changes', [{'version': True}, {'version': '1'}, {'version': 1.0},
                                  {'on_error': 'IGNORE'}, {'extra_keys': 'IGNORE'},
                                  {'trim_strings': 'BOTH'}, {'extra': True}])
def test_strict_policy(changes):
    with pytest.raises(ValueError):
        validate_json_content(b'[{"id":1}]', dict(policy(), **changes), ['id'])


def test_compiler_encodes_literals_and_fail_closed_file_chain():
    result = json_input_fragment(policy(), [{'source_name': '${name}.中文', 'stream_name': 'code', 'data_type': 'VARCHAR(32)'}])
    filename, reader, projection = result['transforms']
    assert filename.findtext('fields/field/nullif') == '${SOURCE_JSON}'
    assert filename.findtext('limit') == '1'
    assert reader.findtext('fields/field/path') == '$.[*]["\\u0024{name}.中文"]'
    assert reader.findtext('doNotFailIfNoFile') == 'N'
    assert reader.findtext('ignoreMissingPath') == 'N'
    assert reader.findtext('defaultPathLeafToNull') == 'Y'
    assert reader.findtext('IsInFields') == reader.findtext('IsAFile') == 'Y'
    assert reader.findtext('removeSourceField') == 'N'
    assert projection.findtext('fields/select_unspecified') == 'N'
    assert result['output_transform'] == 'source_columns' and result['execution_authorized'] is False


@pytest.mark.parametrize('fields', [[], [None], [{'source_name': 'x', 'stream_name': 'json_source_file', 'data_type': 'BIGINT'}],
    [{'source_name': 'x', 'stream_name': 'bad-name', 'data_type': 'BIGINT'}],
    [{'source_name': 'x', 'stream_name': 'code', 'data_type': 'ARBITRARY'}],
    [{'source_name': '', 'stream_name': 'code', 'data_type': 'BIGINT'}]])
def test_compiler_invalid_fields(fields):
    with pytest.raises(ValueError):
        json_input_fragment(policy(), fields)


def test_duplicate_input_or_output_names_rejected():
    first = {'source_name': 'x', 'stream_name': 'code', 'data_type': 'BIGINT'}
    for second in [dict(first, stream_name='code2'), dict(first, source_name='y')]:
        with pytest.raises(ValueError):
            json_input_fragment(policy(), [first, second])


def test_single_object_path_is_not_variable_syntax():
    assert json_field_path('OBJECT', 'a"b') == '$.["a\\"b"]'


@pytest.mark.parametrize('bom', [b'', b'\xef\xbb\xbf'])
def test_bom_normalization_preserves_all_remaining_bytes_and_both_hashes(bom):
    from hashlib import sha256
    from app.json_input_contract import prepare_json_reader_content
    payload = b' [ { "id" : 1e-6 } ] \r\n'
    reader, proof = prepare_json_reader_content(bom + payload, policy(), ['id'])
    assert reader == payload
    assert proof['content_checksum'] == sha256(bom + payload).hexdigest()
    assert proof['reader_content_checksum'] == sha256(payload).hexdigest()
    assert proof['normalization'] == ('UTF8_BOM_REMOVED' if bom else 'NONE')
    assert proof['execution_authorized'] is False
