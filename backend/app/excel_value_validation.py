"""Reject implicit/lossy XLSX conversions before native execution; never rewrite cells."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re


def validate_excel_value(value, declared_type):
    from .etl_specification import _type
    kind = _type(declared_type)
    if not kind:
        raise ValueError('EXCEL_TYPE_UNSUPPORTED')
    if value is None:
        return
    family = kind[0]
    if family == 'STRING':
        if not isinstance(value, str) or len(value.encode('utf-8')) > kind[2] or '\x00' in value:
            raise ValueError('EXCEL_STRING_TYPE_OR_LENGTH')
        return
    if family == 'BOOLEAN':
        if type(value) is not bool and not (type(value) is str and value in ('true', 'false')):
            raise ValueError('EXCEL_BOOLEAN_TYPE')
        return
    if family in ('DATE', 'TIMESTAMP'):
        if isinstance(value, str):
            pattern = r'\d{4}-\d{2}-\d{2}' + (r' \d{2}:\d{2}:\d{2}' if family == 'TIMESTAMP' else '')
            if not re.fullmatch(pattern, value):
                raise ValueError('EXCEL_DATE_FORMAT')
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S' if family == 'TIMESTAMP' else '%Y-%m-%d')
            except ValueError:
                raise ValueError('EXCEL_DATE_FORMAT') from None
        if not isinstance(value, date):
            raise ValueError('EXCEL_DATE_TYPE')
        if isinstance(value, datetime) and (value.tzinfo is not None or value.microsecond
                or (family == 'DATE' and (value.hour or value.minute or value.second))):
            raise ValueError('EXCEL_DATE_PRECISION')
        return
    if type(value) not in (int, float, str) or isinstance(value, str) and not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('EXCEL_NUMBER_TYPE')
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('EXCEL_NUMBER_TYPE') from None
    if not number.is_finite():
        raise ValueError('EXCEL_NUMBER_NONFINITE')
    # XLSX numerical cells are IEEE doubles, unlike exact decimal text cells.
    # Never promise to reconstruct a long identifier/decimal already rounded by Excel.
    if type(value) in (int, float) and len(number.as_tuple().digits) > 15:
        raise ValueError('EXCEL_NUMERIC_PRECISION_REQUIRES_TEXT')
    if family == 'INTEGER':
        if number != number.to_integral_value() or not -(2**63 - 1) <= number <= 2**63 - 1:
            raise ValueError('EXCEL_INTEGER_RANGE_OR_FRACTION')
        return
    if family == 'DECIMAL':
        _, digits, exponent = number.as_tuple()
        fraction = max(0, -exponent)
        integer = max(0, len(digits) + exponent)
        if fraction > kind[3] or integer > kind[2] - kind[3]:
            raise ValueError('EXCEL_DECIMAL_PRECISION')
        return
    raise ValueError('EXCEL_TYPE_UNSUPPORTED')
