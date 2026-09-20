"""Bounded DB-API cursor reader; caller owns query, transaction and cleanup."""
import json
from .expected_result import ResultColumn,compare_expected_result,_cell,MAX_CANONICAL_BYTES


def read_result_rows(cursor,columns):
    compare_expected_result(columns,[],[])
    try:
        description=cursor.description
        names=[entry[0] for entry in description] if description is not None else None
    except Exception:
        raise ValueError('RESULT_METADATA_UNAVAILABLE') from None
    if names!=[column.name for column in columns]:raise ValueError('RESULT_COLUMN_ORDER_MISMATCH')
    rows=[];size=0
    while True:
        try:batch=cursor.fetchmany(100)
        except Exception:raise ValueError('RESULT_READ_INCOMPLETE') from None
        if not isinstance(batch,(list,tuple)) or len(batch)>100:raise ValueError('RESULT_INVALID_BATCH')
        if not batch:break
        if len(rows)+len(batch)>10000:raise ValueError('RESULT_ROW_LIMIT_EXCEEDED')
        for values in batch:
            if not isinstance(values,(list,tuple)) or len(values)!=len(columns):
                raise ValueError('RESULT_ROW_WIDTH_MISMATCH')
            canonical=tuple(_cell(value,column) for value,column in zip(values,columns))
            size+=len(json.dumps(canonical,ensure_ascii=True,separators=(',',':')).encode())
            if size>MAX_CANONICAL_BYTES:raise ValueError('RESULT_CONTENT_LIMIT_EXCEEDED')
            rows.append(dict(zip(names,values)))
    return rows
