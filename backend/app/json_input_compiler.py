"""Hop 2.12 JSON source fragment; not a complete approved pipeline.

An explicit one-row filename parameter avoids JsonInput's early file-list check.
Separate projection avoids its remove-source-field buffer bug for narrow inputs.
"""
import json
import re
from xml.etree.ElementTree import Element, SubElement

from .json_input_contract import JsonInputContractV1


def json_field_path(root_shape, name):
    if root_shape not in ('ARRAY', 'OBJECT') or not isinstance(name, str) or not name.strip():
        raise ValueError('JSON_COMPILER_PATH_INVALID')
    try:
        name.encode('utf-8')
    except UnicodeError:
        raise ValueError('JSON_COMPILER_PATH_INVALID') from None
    # $[...] is Hop variable syntax. $.[] is equivalent JSONPath without that
    # collision; encode dollar signs inside literal names before Hop resolve().
    literal = json.dumps(name, ensure_ascii=False).replace('$', '\\u0024')
    return ('$.[*]' if root_shape == 'ARRAY' else '$.') + '[' + literal + ']'


def json_input_fragment(contract, fields):
    from .etl_specification import _type
    policy = JsonInputContractV1.model_validate(contract)
    if not isinstance(fields, list) or not 0 < len(fields) <= 200 or any(not isinstance(f, dict) for f in fields):
        raise ValueError('JSON_COMPILER_FIELDS_INVALID')
    names = [field.get('stream_name') for field in fields]
    if (any(not isinstance(name, str) or not re.fullmatch('[a-z_][a-z0-9_]{0,62}', name)
            or name == 'json_source_file' for name in names) or len(set(names)) != len(names)):
        raise ValueError('JSON_COMPILER_NAMES_INVALID')
    paths = [json_field_path(policy.root_shape, field.get('source_name')) for field in fields]
    if len(set(paths)) != len(paths):
        raise ValueError('JSON_COMPILER_SOURCE_NAMES_DUPLICATE')

    def values(node, **items):
        for key, value in items.items():
            SubElement(node, key).text = str(value)
        return node

    filename = values(Element('transform'), name='source_file', type='RowGenerator', copies=1,
                      limit=1, never_ending='N')
    values(SubElement(SubElement(filename, 'fields'), 'field'), name='json_source_file', type='String',
           nullif='${SOURCE_JSON}', length=-1, precision=-1, set_empty_string='N')
    source = values(Element('transform'), name='source', type='JsonInput', copies=1,
                    include='N', rownum='N', addresultfile='N', readurl='N',
                    IsIgnoreEmptyFile='N', doNotFailIfNoFile='N', ignoreMissingPath='N',
                    defaultPathLeafToNull='Y', limit=0, IsInFields='Y', IsAFile='Y',
                    valueField='json_source_file', removeSourceField='N')
    holder = SubElement(source, 'fields')
    projection = values(Element('transform'), name='source_columns', type='SelectValues', copies=1)
    selected = values(SubElement(projection, 'fields'), select_unspecified='N')
    for field, path in zip(fields, paths):
        kind = _type(field.get('data_type'))
        if not kind:
            raise ValueError('JSON_COMPILER_TYPE_UNSUPPORTED')
        values(SubElement(holder, 'field'), name=field['stream_name'], path=path,
               type={'STRING': 'String', 'INTEGER': 'Integer', 'DECIMAL': 'BigNumber',
                     'BOOLEAN': 'Boolean', 'DATE': 'Date', 'TIMESTAMP': 'Date'}[kind[0]],
               length=kind[2] if kind[0] in ('STRING', 'DECIMAL') else -1,
               precision=kind[3] if kind[0] == 'DECIMAL' else -1,
               format={'DATE': 'yyyy-MM-dd', 'TIMESTAMP': 'yyyy-MM-dd HH:mm:ss'}.get(kind[0], ''),
               decimal='.', group='', currency='', trim_type='none', repeat='N')
        values(SubElement(selected, 'field'), name=field['stream_name'], rename=field['stream_name'],
               length=-2, precision=-2)
    for index, node in enumerate((filename, source, projection)):
        values(SubElement(node, 'GUI'), xloc=80 + index * 160, yloc=100, draw='Y')
    return {'transforms': [filename, source, projection],
            'hops': [('source_file', 'source'), ('source', 'source_columns')],
            'output_transform': 'source_columns', 'execution_authorized': False}
