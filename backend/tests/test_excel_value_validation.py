from datetime import datetime, timezone
import pytest
from app.excel_value_validation import validate_excel_value


@pytest.mark.parametrize('value,kind', [
    ('001', 'VARCHAR(32)'), (' 中文 ', 'VARCHAR(8)'), (None, 'BOOLEAN'), (False, 'BOOLEAN'), ('true', 'BOOLEAN'),
    ('2026-09-28', 'DATE'), (datetime(2026, 9, 28, 12, 34, 56), 'TIMESTAMP'),
    (12.125, 'DECIMAL(18,4)'), ('12345678901234567890.123456', 'DECIMAL(26,6)'),
    ('9223372036854775807', 'BIGINT'),
])
def test_exact_supported_values(value, kind):
    validate_excel_value(value, kind)


@pytest.mark.parametrize('value,kind,error', [
    ('中文', 'VARCHAR(5)', 'EXCEL_STRING_TYPE_OR_LENGTH'),
    (123, 'VARCHAR(32)', 'EXCEL_STRING_TYPE_OR_LENGTH'),
    (1, 'BOOLEAN', 'EXCEL_BOOLEAN_TYPE'), ('yes', 'BOOLEAN', 'EXCEL_BOOLEAN_TYPE'),
    ('2026-02-30', 'DATE', 'EXCEL_DATE_FORMAT'),
    (datetime(2026, 9, 28, 1), 'DATE', 'EXCEL_DATE_PRECISION'),
    (datetime(2026, 9, 28, tzinfo=timezone.utc), 'TIMESTAMP', 'EXCEL_DATE_PRECISION'),
    (1234567890123456, 'BIGINT', 'EXCEL_NUMERIC_PRECISION_REQUIRES_TEXT'),
    ('9223372036854775808', 'BIGINT', 'EXCEL_INTEGER_RANGE_OR_FRACTION'),
    (1.5, 'BIGINT', 'EXCEL_INTEGER_RANGE_OR_FRACTION'),
    ('1.23456', 'DECIMAL(18,4)', 'EXCEL_DECIMAL_PRECISION'),
    ('123.4', 'DECIMAL(3,1)', 'EXCEL_DECIMAL_PRECISION'),
    (float('inf'), 'DECIMAL(18,4)', 'EXCEL_NUMBER_NONFINITE'),
])
def test_implicit_or_lossy_values_fail(value, kind, error):
    with pytest.raises(ValueError, match=error):
        validate_excel_value(value, kind)
