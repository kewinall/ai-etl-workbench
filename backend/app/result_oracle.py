"""Versioned expected-result document reader; no approval or persistence authority.

Callers must obtain pinned checksums from trusted control records, not from the
same untrusted document. Raw oracle rows are never included in returned evidence.
"""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from .expected_result import ResultColumn, compare_expected_result


def _unique(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('ORACLE_DUPLICATE_KEY')
        result[key]=value
    return result


def compare_oracle_document(content, actual, *, document_checksum, specification_checksum, naming_checksum):
    pins=(document_checksum,specification_checksum,naming_checksum)
    if any(not isinstance(pin,str) or not re.fullmatch('[0-9a-f]{64}',pin) for pin in pins):
        raise ValueError('ORACLE_INVALID_BINDING')
    if not isinstance(content,bytes) or len(content)>8*1024*1024:
        raise ValueError('ORACLE_DOCUMENT_LIMIT')
    if sha256(content).hexdigest()!=document_checksum:
        raise ValueError('ORACLE_DOCUMENT_CHANGED')
    try:
        doc=json.loads(content.decode('utf-8'),object_pairs_hook=_unique)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:
        raise ValueError('ORACLE_INVALID_JSON') from exc
    if not isinstance(doc,dict) or set(doc)!={'version','specification_checksum','naming_checksum','columns','rows'}:
        raise ValueError('ORACLE_INVALID_DOCUMENT')
    if type(doc['version']) is not int or doc['version']!=1:
        raise ValueError('ORACLE_UNSUPPORTED_VERSION')
    if doc['specification_checksum']!=specification_checksum or doc['naming_checksum']!=naming_checksum:
        raise ValueError('ORACLE_BINDING_MISMATCH')
    if not isinstance(doc['columns'],list) or not 1<=len(doc['columns'])<=128:
        raise ValueError('ORACLE_INVALID_COLUMNS')
    columns=[]
    for column in doc['columns']:
        if not isinstance(column,dict) or set(column)!={'name','kind','nullable'}:
            raise ValueError('ORACLE_INVALID_COLUMNS')
        columns.append(ResultColumn(**column))
    # Reuse schema validation before interpreting any row or column name.
    compare_expected_result(columns,[],[])
    if not isinstance(doc['rows'],list) or len(doc['rows'])>10000:
        raise ValueError('ORACLE_INVALID_ROWS')
    expected=[]
    for row in doc['rows']:
        if not isinstance(row,dict) or set(row)!={c.name for c in columns}:
            raise ValueError('ORACLE_INVALID_ROWS')
        decoded=dict(row)
        for column in columns:
            value=row[column.name]
            if column.kind=='DECIMAL' and value is not None:
                if not isinstance(value,str) or len(value)>2048 or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?',value):
                    raise ValueError('ORACLE_INVALID_DECIMAL')
                try:decoded[column.name]=Decimal(value)
                except InvalidOperation as exc:raise ValueError('ORACLE_INVALID_DECIMAL') from exc
        expected.append(decoded)
    evidence=compare_expected_result(columns,expected,actual)
    return {**evidence,'oracle_document_checksum':document_checksum,
            'specification_checksum':specification_checksum,'naming_checksum':naming_checksum}
