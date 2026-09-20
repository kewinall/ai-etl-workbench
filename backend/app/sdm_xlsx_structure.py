"""Bounded structural inspection for this platform's two-sheet SDM renderer.

Does not establish semantic equality, confidentiality, QA or release approval.
No extraction to disk and no external relationship resolution.
"""
from hashlib import sha256
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

PARTS = frozenset(('xl/workbook.xml','xl/styles.xml','xl/theme/theme1.xml',
    'xl/sharedStrings.xml','xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml',
    '_rels/.rels','xl/_rels/workbook.xml.rels','[Content_Types].xml'))
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
PACKAGE_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
MAX_PART = 4 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
REL_TARGETS = {'officeDocument':'/xl/workbook.xml','styles':'/xl/styles.xml',
    'theme':'/xl/theme/theme1.xml','sharedStrings':'/xl/sharedStrings.xml',
    'worksheet':None}


def inspect_sdm_xlsx(content):
    if type(content) is not bytes or not 0 < len(content) <= MAX_TOTAL:
        raise ValueError('SDM_XLSX_SIZE')
    try:
        with ZipFile(BytesIO(content)) as archive:
            members=archive.infolist()
            if len(members)!=len(PARTS) or {m.filename for m in members}!=PARTS:
                raise ValueError('SDM_XLSX_PARTS')
            if sum(m.file_size for m in members)>MAX_TOTAL:
                raise ValueError('SDM_XLSX_SIZE')
            roots={}
            for member in members:
                if member.flag_bits & 1 or member.file_size>MAX_PART or (member.external_attr>>16)&0o170000==0o120000:
                    raise ValueError('SDM_XLSX_UNSAFE_PART')
                with archive.open(member) as stream:
                    raw=stream.read(MAX_PART+1)
                if len(raw)>MAX_PART or len(raw)!=member.file_size:
                    raise ValueError('SDM_XLSX_SIZE')
                xml=raw.decode('utf-8-sig')
                if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
                    raise ValueError('SDM_XLSX_XML_DECLARATION')
                root=ET.fromstring(xml);roots[member.filename]=root
                for node in root.iter():
                    tag=node.tag.rsplit('}',1)[-1]
                    if tag in {'f','hyperlink','externalLink','oleObject','definedName'}:
                        raise ValueError('SDM_XLSX_ACTIVE_CONTENT')
                    if node.get('hidden') in ('1','true') or node.get('state') in ('hidden','veryHidden'):
                        raise ValueError('SDM_XLSX_HIDDEN_CONTENT')
                if member.filename.endswith('.rels'):
                    ids=set()
                    for relation in root:
                        kind=relation.get('Type','').removeprefix(REL)
                        target=relation.get('Target')
                        permitted=REL_TARGETS.get(kind)
                        if (relation.get('TargetMode','Internal')!='Internal' or kind not in REL_TARGETS
                            or (target not in ('/xl/worksheets/sheet1.xml','/xl/worksheets/sheet2.xml') if kind=='worksheet' else target!=permitted)
                            or not relation.get('Id') or relation.get('Id') in ids):
                            raise ValueError('SDM_XLSX_RELATIONSHIP')
                        ids.add(relation.get('Id'))
            sheets=roots['xl/workbook.xml'].findall(f'{{{NS}}}sheets/{{{NS}}}sheet')
            if [s.get('name') for s in sheets]!=['欄位對照','規則及版本']:
                raise ValueError('SDM_XLSX_SHEETS')
            expected_edges = {
                '_rels/.rels': {(REL+'officeDocument','/xl/workbook.xml')},
                'xl/_rels/workbook.xml.rels': {
                    (REL+'styles','/xl/styles.xml'), (REL+'theme','/xl/theme/theme1.xml'),
                    (REL+'sharedStrings','/xl/sharedStrings.xml'),
                    (REL+'worksheet','/xl/worksheets/sheet1.xml'),
                    (REL+'worksheet','/xl/worksheets/sheet2.xml'),
                },
            }
            for name, expected in expected_edges.items():
                root=roots[name]
                edges=[(r.get('Type'),r.get('Target')) for r in root]
                if (root.tag!=f'{{{PACKAGE_REL}}}Relationships' or len(edges)!=len(expected)
                    or set(edges)!=expected or any(r.tag!=f'{{{PACKAGE_REL}}}Relationship' for r in root)):
                    raise ValueError('SDM_XLSX_RELATIONSHIP_GRAPH')
            relationships={r.get('Id'):r.get('Target') for r in roots['xl/_rels/workbook.xml.rels']}
            sheet_ids=[s.get('sheetId') for s in sheets]
            if (roots['xl/workbook.xml'].tag!=f'{{{NS}}}workbook'
                or any(not value or not value.isdecimal() or int(value)<1 for value in sheet_ids)
                or len(set(sheet_ids))!=2
                or [relationships.get(s.get(f'{{{REL[:-1]}}}id')) for s in sheets]
                   !=['/xl/worksheets/sheet1.xml','/xl/worksheets/sheet2.xml']):
                raise ValueError('SDM_XLSX_SHEET_RELATIONSHIP')
            for name in ('xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml'):
                if roots[name].tag!=f'{{{NS}}}worksheet':
                    raise ValueError('SDM_XLSX_WORKSHEET_ROOT')
    except (BadZipFile, ET.ParseError, UnicodeError, RuntimeError, NotImplementedError, EOFError):
        raise ValueError('SDM_XLSX_INVALID') from None
    return {'status':'STRUCTURE_CHECKED_NOT_RELEASED','checksum':sha256(content).hexdigest(),
            'part_count':len(PARTS),'semantic_equality':'NOT_VERIFIED',
            'portability':'NOT_VERIFIED','qa_passed':False,'release_ready':False}
