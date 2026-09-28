"""Exact scalar checks before Hop; no coercion or rewriting of JSON records."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re


def validate_json_value(value, declared_type):
    from .etl_specification import _type
    kind = _type(declared_type)
    if not kind:
        raise ValueError('JSON_TYPE_UNSUPPORTED')
    if value is None:
        return
    family = kind[0]
    if family == 'STRING':
        if not isinstance(value, str):
            raise ValueError('JSON_STRING_TYPE_OR_LENGTH')
        try:
            size = len(value.encode('utf-8'))
        except UnicodeError:
            raise ValueError('JSON_STRING_INVALID_UNICODE') from None
        if size > kind[2] or '\x00' in value:
            raise ValueError('JSON_STRING_TYPE_OR_LENGTH')
        return
    if family == 'BOOLEAN':
        if type(value) is not bool and not (type(value) is str and value in ('true', 'false')):
            raise ValueError('JSON_BOOLEAN_TYPE')
        return
    if family in ('DATE', 'TIMESTAMP'):
        pattern = r'[0-9]{4}-[0-9]{2}-[0-9]{2}' + (r' [0-9]{2}:[0-9]{2}:[0-9]{2}' if family == 'TIMESTAMP' else '')
        if not isinstance(value, str) or not re.fullmatch(pattern, value):
            raise ValueError('JSON_DATE_FORMAT')
        try:
            datetime.strptime(value, '%Y-%m-%d %H:%M:%S' if family == 'TIMESTAMP' else '%Y-%m-%d')
        except ValueError:
            raise ValueError('JSON_DATE_FORMAT') from None
        return
    # inspect_json retains exact integer/Decimal tokens. A float passed by a
    # caller is not evidence of the original decimal and is never accepted.
    if type(value) not in (int, Decimal, str) or (
            isinstance(value, str) and not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', value)):
        raise ValueError('JSON_NUMBER_TYPE')
    try:
        number = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError('JSON_NUMBER_TYPE') from None
    if not number.is_finite():
        raise ValueError('JSON_NUMBER_NONFINITE')
    if family == 'INTEGER':
        if number != number.to_integral_value() or not -(2**63 - 1) <= number <= 2**63 - 1:
            raise ValueError('JSON_INTEGER_RANGE_OR_FRACTION')
        return
    if family == 'DECIMAL':
        _, digits, exponent = number.as_tuple()
        integer_digits = 0 if number.is_zero() else max(0, len(digits) + exponent)
        if max(0, -exponent) > kind[3] or integer_digits > kind[2] - kind[3]:
            raise ValueError('JSON_DECIMAL_PRECISION')
        return
    raise ValueError('JSON_TYPE_UNSUPPORTED')
