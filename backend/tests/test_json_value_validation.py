from decimal import Decimal
import pytest
from app.json_value_validation import validate_json_value
from app.json_input_contract import validate_json_content, prepare_json_reader_content, contract_checksum
from test_json_input_contract import policy


@pytest.mark.parametrize('value,kind', [
    ('001', 'VARCHAR(32)'), (' 中文 ', 'VARCHAR(8)'), ('', 'VARCHAR(1)'), (None, 'BIGINT'),
    (False, 'BOOLEAN'), ('true', 'BOOLEAN'), ('2024-02-29', 'DATE'), ('2026-09-28 12:34:56', 'TIMESTAMP'),
    (9223372036854775807, 'BIGINT'), (-9223372036854775807, 'INTEGER'),
    (Decimal('1.0'), 'BIGINT'), (Decimal('1e3'), 'BIGINT'), ('9223372036854775807', 'BIGINT'),
    (Decimal('12345678901234567890.123456'), 'NUMERIC(26,6)'),
    ('0.123456789012345678', 'DECIMAL(18,18)'), (Decimal('1e-18'), 'DECIMAL(18,18)'),
    (0, 'NUMERIC(1,1)'), (Decimal('0E+100'), 'NUMERIC(1,1)'),
])
def test_supported_exact_values(value, kind):
    validate_json_value(value, kind)


@pytest.mark.parametrize('value,kind,error', [
    ('中文', 'VARCHAR(5)', 'JSON_STRING_TYPE_OR_LENGTH'), (123, 'VARCHAR(32)', 'JSON_STRING_TYPE_OR_LENGTH'),
    ('\x00', 'VARCHAR(1)', 'JSON_STRING_TYPE_OR_LENGTH'), ('\ud800', 'VARCHAR(3)', 'JSON_STRING_INVALID_UNICODE'),
    (1, 'BOOLEAN', 'JSON_BOOLEAN_TYPE'), ('yes', 'BOOLEAN', 'JSON_BOOLEAN_TYPE'),
    ('TRUE', 'BOOLEAN', 'JSON_BOOLEAN_TYPE'), ('2026-02-29', 'DATE', 'JSON_DATE_FORMAT'),
    ('2026-09-28 00:00:00', 'DATE', 'JSON_DATE_FORMAT'), ('2026/09/28', 'DATE', 'JSON_DATE_FORMAT'),
    ('2026-09-28T12:00:00', 'TIMESTAMP', 'JSON_DATE_FORMAT'),
    ('2026-09-28 12:00:00.001', 'TIMESTAMP', 'JSON_DATE_FORMAT'),
    ('2026-09-28 12:00:00Z', 'TIMESTAMP', 'JSON_DATE_FORMAT'),
    ('2026-09-28 24:00:00', 'TIMESTAMP', 'JSON_DATE_FORMAT'),
    (True, 'BIGINT', 'JSON_NUMBER_TYPE'), (1.0, 'BIGINT', 'JSON_NUMBER_TYPE'),
    (' 1', 'BIGINT', 'JSON_NUMBER_TYPE'), ('', 'BIGINT', 'JSON_NUMBER_TYPE'),
    ('1e3', 'BIGINT', 'JSON_NUMBER_TYPE'), ('١', 'BIGINT', 'JSON_NUMBER_TYPE'),
    (9223372036854775808, 'BIGINT', 'JSON_INTEGER_RANGE_OR_FRACTION'),
    (-9223372036854775808, 'BIGINT', 'JSON_INTEGER_RANGE_OR_FRACTION'),
    (Decimal('1.5'), 'BIGINT', 'JSON_INTEGER_RANGE_OR_FRACTION'),
    (Decimal('NaN'), 'BIGINT', 'JSON_NUMBER_NONFINITE'),
    (Decimal('Infinity'), 'NUMERIC(18,4)', 'JSON_NUMBER_NONFINITE'),
    (Decimal('1e100000'), 'NUMERIC(38,18)', 'JSON_DECIMAL_PRECISION'),
    (Decimal('1e-100000'), 'NUMERIC(38,18)', 'JSON_DECIMAL_PRECISION'),
    ('1.23456', 'NUMERIC(18,4)', 'JSON_DECIMAL_PRECISION'),
    ('123.4', 'NUMERIC(3,1)', 'JSON_DECIMAL_PRECISION'), (None, 'FLOAT', 'JSON_TYPE_UNSUPPORTED'),
])
def test_lossy_implicit_or_unsupported_values_rejected(value, kind, error):
    with pytest.raises(ValueError, match=error):
        validate_json_value(value, kind)


def test_full_scan_finds_late_failure_without_leaking_value():
    content = ('[' + ','.join(['{"id":1}'] * 25 + ['{"id":"private-bad-value"}']) + ']').encode()
    with pytest.raises(ValueError) as caught:
        validate_json_content(content, policy(), ['id'], column_types=['BIGINT'])
    assert str(caught.value) == 'JSON_NUMBER_TYPE: record=26, column=1'
    assert 'private' not in str(caught.value)


@pytest.mark.parametrize('types', [[], ['BIGINT', 'BIGINT'], 'BIGINT', [None], ['FLOAT']])
def test_complete_supported_type_coverage_required(types):
    with pytest.raises(ValueError):
        validate_json_content(b'[{"id":null}]', policy(), ['id'], column_types=types)


def test_typed_proof_preserves_nulls_and_exact_reader_bytes():
    content = b'\xef\xbb\xbf[{"id":1e3,"amount":0.123456789012345678},{"id":null},{}]'
    types = ['BIGINT', 'NUMERIC(18,18)']
    reader, proof = prepare_json_reader_content(content, policy(), ['id', 'amount'], column_types=types)
    assert reader == content[3:]
    assert proof['records_expected'] == 3 and proof['column_types_checked'] is True
    assert proof['column_types_checksum'] == contract_checksum(types)
    assert proof['type_conversion_verified'] is False and proof['execution_authorized'] is False
