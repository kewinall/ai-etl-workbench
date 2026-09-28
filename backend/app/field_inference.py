"""Conservative suggestions only; never a cast, confirmed schema or full-file proof."""
import re
from datetime import date, datetime
from decimal import Decimal


def infer_field_type(values):
    clean = [value for value in values if value is not None and value != '']
    if not clean:
        return 'VARCHAR(255)'
    text = [format(value, 'f') if isinstance(value, Decimal) and value.is_finite()
            and -18 <= value.as_tuple().exponent <= 38 else str(value) for value in clean]

    def as_text():
        length = max(32, max(len(value.encode('utf-8')) for value in text))
        if length > 65000:
            raise ValueError('欄位樣本超過目前支援的 VARCHAR 位元組長度；請補正來源規格')
        return f'VARCHAR({length})'

    if any(isinstance(value, (dict, list, tuple)) for value in clean):
        raise ValueError('巢狀欄位需要明確展開規格，不能自動判定為純文字')
    if all(value.lower() in ('true', 'false') for value in text):
        return 'BOOLEAN'
    # Do not silently trim or strip leading zeroes from identifiers.
    if any(value != value.strip() or re.match(r'^[+-]?0[0-9]', value) for value in text):
        return as_text()
    if all(re.fullmatch(r'[+-]?[0-9]+', value) for value in text):
        # Keep the lowest signed sentinel out of automatic integer suggestions.
        if all(len(value.lstrip('+-')) <= 19 and -(2**63 - 1) <= int(value) <= 2**63 - 1 for value in text):
            return 'BIGINT'
    if all(re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', value) for value in text):
        numbers = [Decimal(value) for value in text]
        scale = max(max(0, -value.as_tuple().exponent) for value in numbers)
        integer_digits = max(max(1, value.adjusted() + 1) for value in numbers)
        # Preserve the legacy minimum suggestion, but never round to fit it.
        scale = max(4, scale) if any('.' in value for value in text) else scale
        precision = max(18, integer_digits + scale)
        # This is the Workbench compiler subset, not Vertica's engine maximum.
        if precision <= 38 and scale <= 18:
            return f'DECIMAL({precision},{scale})'
        return as_text()
    if all(isinstance(value, datetime) and value.tzinfo is None for value in clean):
        return 'TIMESTAMP'
    if all(isinstance(value, date) and not isinstance(value, datetime) for value in clean):
        return 'DATE'
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            for value in text:
                datetime.strptime(value, fmt)
            return 'TIMESTAMP' if '%H' in fmt else 'DATE'
        except ValueError:
            continue
    return as_text()
