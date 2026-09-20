"""Deployment-owned SDM renderer using the existing openpyxl dependency.

Only normalizes bytes produced here. Never normalizes or repairs uploaded XLSX.
The independent existing structure/content gate remains mandatory.
"""
from io import BytesIO
from math import ceil
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import unicodedata
import re
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from .sdm_xlsx_semantics import expected_sdm_cells, validate_sdm_xlsx
from .sdm_xlsx_structure import NS, REL, PACKAGE_REL, PARTS


def _xml(root):
    # OPC parsers expect the package vocabulary in the default namespace.
    raw = ET.tostring(root, encoding='unicode')
    namespace = root.tag.split('}')[0][1:]
    match = re.search(r'xmlns:(ns\d+)="' + re.escape(namespace) + '"', raw)
    if match:
        prefix = match[1]
        raw = raw.replace(match[0], 'xmlns="' + namespace + '"')
        raw = raw.replace('<'+prefix+':', '<').replace('</'+prefix+':', '</')
    return raw.encode('utf-8')


def _owned_package(raw):
    with ZipFile(BytesIO(raw)) as source:
        parts = {name: source.read(name) for name in PARTS if name != 'xl/sharedStrings.xml'}
    workbook = ET.fromstring(parts['xl/workbook.xml'])
    for node in list(workbook):
        if node.tag == f'{{{NS}}}definedNames':
            if len(node):
                raise ValueError('SDM_RENDERER_UNEXPECTED_NAMES')
            workbook.remove(node)
    parts['xl/workbook.xml'] = _xml(workbook)
    parts['xl/sharedStrings.xml'] = f'<sst xmlns="{NS}" count="0" uniqueCount="0"/>'.encode()
    # Inline strings remain inline; the existing validator accepts both forms.
    for name in ('_rels/.rels', 'xl/_rels/workbook.xml.rels'):
        root = ET.fromstring(parts[name])
        for relation in list(root):
            kind = relation.get('Type', '').removeprefix(REL)
            if name == '_rels/.rels' and kind != 'officeDocument':
                root.remove(relation)
            else:
                target = relation.get('Target', '')
                if not target.startswith('/'):
                    relation.set('Target', '/' + ('' if name == '_rels/.rels' else 'xl/') + target)
        if name != '_rels/.rels':
            ET.SubElement(root, f'{{{PACKAGE_REL}}}Relationship', {
                'Id': 'sdmSharedStrings', 'Type': REL+'sharedStrings', 'Target': '/xl/sharedStrings.xml'})
        parts[name] = _xml(root)
    types = ET.fromstring(parts['[Content_Types].xml'])
    ct = 'http://schemas.openxmlformats.org/package/2006/content-types'
    for node in list(types):
        if node.get('PartName', '').startswith('/docProps/'):
            types.remove(node)
    ET.SubElement(types, f'{{{ct}}}Override', {'PartName': '/xl/sharedStrings.xml',
        'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml'})
    parts['[Content_Types].xml'] = _xml(types)
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(parts):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, parts[name])
    return output.getvalue()


def render_sdm_xlsx(payload, run, naming, *, release_binding=None):
    cells = expected_sdm_cells(payload, run, naming, release_binding=release_binding)
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, values, widths in zip(('欄位對照', '規則及版本'), cells,
                                    ((8, 24, 24, 24, 30, 38), (28, 100))):
        sheet = workbook.create_sheet(name)
        sheet.sheet_view.showGridLines = False
        sheet.freeze_panes = 'A6'
        for index, width in enumerate(widths):
            sheet.column_dimensions[chr(65+index)].width = width
        for ref, value in values.items():
            cell = sheet[ref]
            if isinstance(value, str):
                if len(value) > 2048 or any(ord(c)<32 and c not in '\t\n\r' for c in value):
                    raise ValueError('SDM_CELL_TEXT_INVALID')
                cell.value = value
                cell.data_type = 's'  # Formula-looking names remain literal text.
            else:
                cell.value = value
            cell.font = Font(name='Arial', size=15 if cell.row==2 else 11,
                             bold=cell.row in (2, 5), color='FFFFFF' if cell.row==5 else '172B4D')
            cell.alignment = Alignment(horizontal='center' if cell.row==5 else 'right' if type(value) is int else 'left',
                                       vertical='center', wrap_text=cell.row>=5)
            if cell.row==5:
                cell.fill = PatternFill('solid', fgColor='203B58')
            if cell.row>=5:
                units=max(sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1 for ch in line) for line in str(value).split('\n'))
                height=max(24, 17*ceil(units/max(1,widths[cell.column-1]-2))+8)
                sheet.row_dimensions[cell.row].height=max(sheet.row_dimensions[cell.row].height or 0,height)
        sheet.row_dimensions[2].height=26
        sheet.row_dimensions[3].height=22
    raw = BytesIO()
    workbook.save(raw)
    content = _owned_package(raw.getvalue())
    evidence = validate_sdm_xlsx(content, payload, run, naming, release_binding=release_binding)
    return {'content': content, 'evidence': evidence, 'status': 'SDM_DELIVERY_DOCUMENT_NOT_AUTHORIZED' if release_binding else 'SDM_CANDIDATE_NOT_RELEASED',
            'qa_passed': False, 'release_ready': False}
