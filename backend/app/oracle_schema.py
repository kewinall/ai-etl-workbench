"""Oracle output schema must match the existing compiler's supported types."""
from .etl_specification import _type
import re


def oracle_columns(compiled):
    """Use authoritative compiler output order/types, not browser guesses."""
    columns=[]
    for name in compiled['specification']['output_columns']:
        declared=_type(compiled['output_types'].get(name))
        if not declared or declared[0] not in {'STRING','INTEGER','DECIMAL','BOOLEAN'}:
            raise ValueError('ORACLE_OUTPUT_TYPE_UNSUPPORTED')
        columns.append({'name':name,'kind':{'STRING':'TEXT'}.get(declared[0],declared[0]),'nullable':False})
    if len(columns)>128:raise ValueError('ORACLE_OUTPUT_COLUMNS_LIMIT')
    return columns


def validate_oracle_schema(document, compiled):
    columns=document['columns']
    if [column['name'] for column in columns]!=compiled['specification']['output_columns']:
        raise ValueError('ORACLE_OUTPUT_COLUMNS_MISMATCH')
    for column in columns:
        declared=_type(compiled['output_types'].get(column['name']))
        if not declared or declared[0] not in {'STRING','INTEGER','DECIMAL','BOOLEAN'}:
            raise ValueError('ORACLE_OUTPUT_TYPE_UNSUPPORTED')
        expected={'STRING':'TEXT'}.get(declared[0],declared[0])
        if column['kind']!=expected:
            raise ValueError('ORACLE_OUTPUT_TYPE_MISMATCH')
        # Called after document validation by save/approve. Keep exact values;
        # do not imitate database rounding or truncation of the expected answer.
        for row in document.get('rows',[]):
            value=row[column['name']]
            if value is None:continue
            if expected=='TEXT':
                if not isinstance(value,str) or len(value.encode('utf-8'))>declared[2]:
                    raise ValueError('ORACLE_TEXT_WIDTH_EXCEEDED')
            elif expected=='INTEGER':
                # Vertica 24.4 reserves -2^63 for NULL (official PDF p2458).
                if type(value) is not int or not -(2**63)<value<2**63:
                    raise ValueError('ORACLE_INTEGER_RANGE_EXCEEDED')
            elif expected=='DECIMAL':
                if not isinstance(value,str) or not re.fullmatch(r'-?\d+(?:\.\d+)?',value):
                    raise ValueError('ORACLE_INVALID_DECIMAL')
                integer,_,fraction=value.lstrip('-').partition('.')
                if len(integer.lstrip('0'))>declared[2]-declared[3]:
                    raise ValueError('ORACLE_DECIMAL_PRECISION_EXCEEDED')
                if len(fraction.rstrip('0'))>declared[3]:
                    raise ValueError('ORACLE_DECIMAL_SCALE_EXCEEDED')
