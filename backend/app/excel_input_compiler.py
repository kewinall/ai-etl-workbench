"""Native ExcelInput fragment only; no complete design validation or authority."""
import re
from xml.etree.ElementTree import Element, SubElement
from .excel_input_contract import ExcelInputContractV1
from .etl_specification import _type


def excel_input_transform(contract, fields):
    policy = ExcelInputContractV1.model_validate(contract)
    if not fields or len(fields) > 200:
        raise ValueError('EXCEL_COMPILER_FIELDS_INVALID')
    if any(not isinstance(field, dict) for field in fields):
        raise ValueError('EXCEL_COMPILER_FIELDS_INVALID')
    names = [field.get('stream_name') for field in fields]
    if (any(not isinstance(name, str) or not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', name) for name in names)
            or len(set(names)) != len(names)):
        raise ValueError('EXCEL_COMPILER_NAMES_INVALID')
    def values(parent, **items):
        for key, value in items.items():
            SubElement(parent, key).text = str(value)
        return parent
    node = values(Element('transform'), name='source', type='ExcelInput', copies=1, distribute='Y')
    values(SubElement(node, 'GUI'), xloc=80, yloc=100, draw='Y')
    values(node, spreadsheet_type=policy.engine, header='Y', noempty='Y' if policy.blank_rows == 'SKIP' else 'N',
           stoponempty='N', strict_types='N', error_ignored='N', error_line_skipped='N',
           accept_filenames='N', add_to_result_filenames='N', limit=0)
    values(SubElement(node, 'file'), name='${SOURCE_XLSX}',
           filemask='', exclude_filemask='', file_required='Y', include_subfolders='N')
    values(SubElement(SubElement(node, 'sheets'), 'sheet'), name=policy.worksheet,
           startrow=policy.header_row - 1, startcol=0)
    holder = SubElement(node, 'fields')
    for field in fields:
        kind = _type(field['data_type'])
        if not kind:
            raise ValueError('EXCEL_COMPILER_TYPE_UNSUPPORTED')
        values(SubElement(holder, 'field'), name=field['stream_name'],
               type={'STRING': 'String', 'INTEGER': 'Integer', 'DECIMAL': 'BigNumber',
                     'BOOLEAN': 'Boolean', 'DATE': 'Date', 'TIMESTAMP': 'Date'}[kind[0]],
               length=kind[2] if kind[0] in ('STRING', 'DECIMAL') else -1,
               precision=kind[3] if kind[0] == 'DECIMAL' else -1,
               format={'DATE': 'yyyy-MM-dd', 'TIMESTAMP': 'yyyy-MM-dd HH:mm:ss'}.get(kind[0], ''),
               trim_type='none', repeat='N', decimal='.', group='', currency='')
    return node
