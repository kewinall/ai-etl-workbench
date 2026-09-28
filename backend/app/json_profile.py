"""Strict flat JSON discovery, not an execution contract or source authorization."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from .field_inference import infer_field_type

MAX_ROWS = 100_000
MAX_COLUMNS = 512
MAX_CELLS = 2_000_000


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON_DUPLICATE_KEY: 重複欄位不可靜默覆寫')
        result[key] = value
    return result


def _constant(_value):
    raise ValueError('JSON_NON_FINITE_NUMBER: 不接受 NaN 或 Infinity')


def inspect_json(content: bytes):
    """Scan every supported record; retain numeric precision and array order."""
    try:
        parsed = json.loads(content.decode('utf-8-sig'), parse_float=Decimal,
                            object_pairs_hook=_object, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, InvalidOperation) as exc:
        # Do not expose document fragments or source values in API errors.
        raise ValueError('JSON_INVALID_DOCUMENT: 需要有效 UTF-8 JSON') from exc
    rows = parsed if isinstance(parsed, list) else [parsed]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError('JSON 必須是非空 object 或 object array')
    if len(rows) > MAX_ROWS:
        raise ValueError('JSON_PROFILE_ROW_LIMIT: 請縮小來源檔案')
    names = {}
    for row in rows:
        for name, value in row.items():
            if not name.strip():
                raise ValueError('JSON_EMPTY_COLUMN_NAME: 欄位名稱不得空白')
            if isinstance(value, (dict, list)):
                raise ValueError('巢狀欄位需要明確展開規格，不能自動判定為純文字')
            try:
                name.encode('utf-8')
                if isinstance(value, str):
                    value.encode('utf-8')
            except UnicodeError as exc:
                raise ValueError('JSON_INVALID_UNICODE: 欄位含無效 Unicode') from exc
            names.setdefault(name, None)
            if len(names) > MAX_COLUMNS:
                raise ValueError('JSON_PROFILE_COLUMN_LIMIT: 請縮小來源欄位')
    if not names:
        raise ValueError('JSON_NO_COLUMNS: 至少需要一個欄位')
    if len(names) * len(rows) > MAX_CELLS:
        raise ValueError('JSON_PROFILE_CELL_LIMIT: 請縮小來源規模')
    fields, statistics = [], []
    for name in names:
        values = [row.get(name) for row in rows]
        fields.append({'name': name, 'type': infer_field_type(values)})
        missing = sum(name not in row for row in rows)
        explicit_null = sum(name in row and row[name] is None for row in rows)
        statistics.append({'name': name, 'missing_count': missing,
                           'explicit_null_count': explicit_null,
                           'null_ratio': (missing + explicit_null) / len(rows),
                           'empty_string_count': sum(value == '' for value in values)})
    profile = {'encoding': 'utf-8-sig', 'parser_format': 'JSON',
               'json_profile_version': 1, 'profile_scope': 'ALL_RECORDS',
               'root_shape': 'ARRAY' if isinstance(parsed, list) else 'OBJECT',
               'row_count': len(rows), 'fields': fields, 'column_statistics': statistics,
               'checksum': hashlib.sha256(content).hexdigest(),
               'sample_rows': [{key: str(value) if isinstance(value, Decimal) else value
                                for key, value in row.items()} for row in rows[:5]]}
    return profile, rows
