import json
from decimal import Decimal

import pytest

from app import json_profile, source_profiler, task_uploads


def test_full_scan_includes_late_columns_and_wider_types(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    records = [{'金額': 1} for _ in range(20)] + [{'金額': 'not-a-number', '後段': '001'}]
    upload = task_uploads.save_and_profile('synthetic.json', json.dumps(records).encode())
    assert upload['fields'] == [{'name': '金額', 'type': 'VARCHAR(32)'},
                                {'name': '後段', 'type': 'VARCHAR(32)'}]
    assert upload['row_count'] == 21 and upload['profile_scope'] == 'ALL_RECORDS'
    profile, rows = source_profiler._profile_json(upload)
    assert profile['fields'] == upload['fields']
    assert profile['column_statistics'] == upload['column_statistics']
    assert len(rows) == 10 and len(upload['sample_rows']) == 5


def test_exact_precision_missing_null_empty_and_row_order():
    data = b'[{"id":"002","x":0.123456789012345678},{"id":"001","x":null},{"id":"003"},{"id":"004","x":""}]'
    profile, rows = json_profile.inspect_json(data)
    assert [row['id'] for row in rows] == ['002', '001', '003', '004']
    assert rows[0]['x'] == Decimal('0.123456789012345678')
    assert profile['fields'][1]['type'] == 'DECIMAL(19,18)'
    assert profile['sample_rows'][0]['x'] == '0.123456789012345678'
    assert profile['column_statistics'][1] == {
        'name': 'x', 'missing_count': 1, 'explicit_null_count': 1,
        'null_ratio': 0.5, 'empty_string_count': 1}


@pytest.mark.parametrize('content,code', [
    (b'{"x":1,"x":2}', 'JSON_DUPLICATE_KEY'),
    (b'{"x":1,"\\u0078":2}', 'JSON_DUPLICATE_KEY'),
    (b'{"x":NaN}', 'JSON_NON_FINITE_NUMBER'),
    (b'{"x":1e99999999999999999999999999}', 'JSON_INVALID_DOCUMENT'),
    (b'{"x":Infinity}', 'JSON_NON_FINITE_NUMBER'),
    (b'{"x":-Infinity}', 'JSON_NON_FINITE_NUMBER'),
    (b'{"x":{"private":1}}', '巢狀'),
    (b'[{"x":[]}]', '巢狀'),
    (b'[]', '非空 object'), (b'{}', 'JSON_NO_COLUMNS'),
    (b'[{},3]', '非空 object'), (b'null', '非空 object'),
    (b'{" ":1}', 'JSON_EMPTY_COLUMN_NAME'),
    (b'{"x":"\\ud800"}', 'JSON_INVALID_UNICODE'),
    (b'{"\\ud800":1}', 'JSON_INVALID_UNICODE'),
    (b'{"x":"private-value",}', 'JSON_INVALID_DOCUMENT'),
    (b'{"x":"\xff"}', 'JSON_INVALID_DOCUMENT'),
])
def test_ambiguous_or_unsupported_documents_fail_closed(content, code):
    with pytest.raises(ValueError, match=code) as error:
        json_profile.inspect_json(content)
    assert 'private-value' not in str(error.value)


def test_nested_value_beyond_previous_sample_is_rejected():
    content = json.dumps([{'x': 1}] * 20 + [{'x': {'late': 2}}]).encode()
    with pytest.raises(ValueError, match='巢狀'):
        json_profile.inspect_json(content)


@pytest.mark.parametrize('setting,value,content,code', [
    ('MAX_ROWS', 1, b'[{"x":1},{"x":2}]', 'ROW_LIMIT'),
    ('MAX_COLUMNS', 1, b'{"x":1,"y":2}', 'COLUMN_LIMIT'),
    ('MAX_CELLS', 1, b'{"x":1,"y":2}', 'CELL_LIMIT'),
])
def test_explicit_bounded_scope(monkeypatch, setting, value, content, code):
    monkeypatch.setattr(json_profile, setting, value)
    with pytest.raises(ValueError, match=code):
        json_profile.inspect_json(content)


def test_bom_single_object_and_string_nonfinite_are_not_normalized():
    profile, rows = json_profile.inspect_json(b'\xef\xbb\xbf{"x":" NaN ","id":"0001"}')
    assert profile['root_shape'] == 'OBJECT' and profile['row_count'] == 1
    assert rows == [{'x': ' NaN ', 'id': '0001'}]
    assert profile['fields'][0]['type'] == 'VARCHAR(32)'
