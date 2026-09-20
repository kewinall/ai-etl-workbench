"""Bounded, exact multiset comparison for Pilot result evidence.

Caller supplies rows read from the authorized execution and a versioned oracle.
This primitive neither queries a database nor grants QA/release approval.
"""
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import re

MAX_CANONICAL_BYTES = 8 * 1024 * 1024  # per expected/actual side, including duplicates


@dataclass(frozen=True)
class ResultColumn:
    name: str
    kind: str  # TEXT, INTEGER, DECIMAL, BOOLEAN
    nullable: bool = False


def _cell(value, column):
    if value is None:
        if not column.nullable:
            raise ValueError('RESULT_NULL_NOT_ALLOWED')
        return ('NULL', '')
    if column.kind == 'TEXT' and isinstance(value, str):
        if len(value) > 16384:
            raise ValueError('RESULT_CELL_TOO_LARGE')
        return ('TEXT', value)
    if column.kind == 'BOOLEAN' and type(value) is bool:
        return ('BOOLEAN', str(value))
    if column.kind == 'INTEGER' and type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise ValueError('RESULT_INTEGER_OUT_OF_RANGE')
        return ('INTEGER', str(value))
    if column.kind == 'DECIMAL' and (type(value) is int or isinstance(value, Decimal)):
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError('RESULT_NONFINITE_DECIMAL')
        parts = number.as_tuple()
        if len(parts.digits) > 1024 or abs(parts.exponent) > 1024:
            raise ValueError('RESULT_DECIMAL_TOO_LARGE')
        # Never normalize() under the ambient Decimal context: it can round values.
        canonical = format(number, 'f')
        if '.' in canonical:
            canonical = canonical.rstrip('0').rstrip('.')
        if number == 0:
            canonical = '0'
        return ('DECIMAL', canonical)
    raise ValueError('RESULT_TYPE_MISMATCH')


def _rows(rows, columns):
    if not isinstance(rows, (list, tuple)) or len(rows) > 10000:
        raise ValueError('RESULT_ROW_LIMIT_OR_INVALID_CONTAINER')
    names = {column.name for column in columns}
    result = Counter()
    total_bytes = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != names:
            raise ValueError('RESULT_COLUMN_MISMATCH')
        canonical = tuple(_cell(row[column.name], column) for column in columns)
        total_bytes += len(json.dumps(canonical, ensure_ascii=True, separators=(',', ':')).encode())
        if total_bytes > MAX_CANONICAL_BYTES:
            raise ValueError('RESULT_CONTENT_LIMIT_EXCEEDED')
        result[canonical] += 1
    return result


def compare_expected_result(columns, expected, actual):
    if not isinstance(columns, (list, tuple)) or not 1 <= len(columns) <= 128:
        raise ValueError('RESULT_INVALID_COLUMNS')
    if any(not isinstance(c, ResultColumn) or not isinstance(c.name, str) or not re.fullmatch(r'[a-z_][a-z0-9_]{0,127}', c.name)
           or not isinstance(c.kind, str) or c.kind not in {'TEXT', 'INTEGER', 'DECIMAL', 'BOOLEAN'} or type(c.nullable) is not bool
           for c in columns) or len({c.name for c in columns}) != len(columns):
        raise ValueError('RESULT_INVALID_COLUMNS')
    wanted, observed = _rows(expected, columns), _rows(actual, columns)
    missing, unexpected = wanted-observed, observed-wanted
    def digest(rows):
        value = {'columns':[(c.name,c.kind,c.nullable) for c in columns], 'rows':sorted(rows.items())}
        return sha256(json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
    return {
        'version':1, 'comparison':'EXACT_MULTISET',
        'status':'MATCH' if wanted == observed else 'MISMATCH',
        'expected_count':len(expected), 'actual_count':len(actual),
        'missing_count':sum(missing.values()), 'unexpected_count':sum(unexpected.values()),
        'expected_checksum':digest(wanted), 'actual_checksum':digest(observed),
        'qa_passed':False, 'release_ready':False,
    }
