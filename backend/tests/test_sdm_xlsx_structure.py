from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import pytest
from app.sdm_xlsx_structure import inspect_sdm_xlsx, PARTS, NS, REL, PACKAGE_REL


def fixture(changes=None):
    # Minimal XML containers for structural tests, not claimed valid Excel files.
    parts={name:b'<root/>' for name in PARTS}
    parts['xl/sharedStrings.xml']=f'<sst xmlns="{NS}"/>'.encode()
    parts['xl/workbook.xml']=(f'<workbook xmlns="{NS}" xmlns:r="{REL[:-1]}"><sheets><sheet name="欄位對照" sheetId="1" r:id="s1"/><sheet name="規則及版本" sheetId="2" r:id="s2"/></sheets></workbook>').encode()
    parts['_rels/.rels']=relationships([('doc','officeDocument','/xl/workbook.xml')])
    parts['xl/_rels/workbook.xml.rels']=relationships(workbook_edges())
    for name in ('xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml'):
        parts[name]=f'<worksheet xmlns="{NS}"><sheetData/></worksheet>'.encode()
    parts.update(changes or {})
    stream=BytesIO()
    with ZipFile(stream,'w',ZIP_DEFLATED) as z:
        for name,value in parts.items():z.writestr(name,value)
    return stream.getvalue()


def relationships(edges):
    return (f'<Relationships xmlns="{PACKAGE_REL}">'+''.join(f'<Relationship Id="{i}" Type="{REL}{kind}" Target="{target}"/>' for i,kind,target in edges)+'</Relationships>').encode()


def workbook_edges():
    return [('styles','styles','/xl/styles.xml'),('theme','theme','/xl/theme/theme1.xml'),
        ('strings','sharedStrings','/xl/sharedStrings.xml'),
        ('s1','worksheet','/xl/worksheets/sheet1.xml'),('s2','worksheet','/xl/worksheets/sheet2.xml')]


def test_structure_is_not_semantics_or_release():
    result=inspect_sdm_xlsx(fixture())
    assert result['semantic_equality']=='NOT_VERIFIED'
    assert not result['qa_passed'] and not result['release_ready']


@pytest.mark.parametrize('xml',[
    '<root><f>1+1</f></root>', '<root><hyperlink ref="A1"/></root>',
    '<root><definedName>secret</definedName></root>', '<root hidden="1"/>',
    '<root state="veryHidden"/>', '<!DOCTYPE root [<!ENTITY a "value">]><root>&a;</root>',
    '<root><externalLink/></root>', '<root><oleObject/></root>', '<broken>',
])
def test_active_hidden_or_invalid_xml_rejected(xml):
    with pytest.raises(ValueError):inspect_sdm_xlsx(fixture({'xl/worksheets/sheet1.xml':xml.encode()}))


@pytest.mark.parametrize('target,mode', [('https://example.invalid/','External'),('/etc/passwd','Internal'),('../source.csv','Internal')])
def test_external_or_unlisted_relationship_rejected(target,mode):
    xml=f'<Relationships><Relationship Id="a" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="{target}" TargetMode="{mode}"/></Relationships>'
    with pytest.raises(ValueError,match='SDM_XLSX_RELATIONSHIP'):
        inspect_sdm_xlsx(fixture({'xl/_rels/workbook.xml.rels':xml.encode()}))


def test_extra_file_and_expansion_rejected(monkeypatch):
    with pytest.raises(ValueError,match='SDM_XLSX_PARTS'):
        inspect_sdm_xlsx(fixture({'xl/vbaProject.bin':b'macro'}))
    monkeypatch.setattr('app.sdm_xlsx_structure.MAX_PART',10)
    with pytest.raises(ValueError):inspect_sdm_xlsx(fixture())


@pytest.mark.parametrize('edges',[[],workbook_edges()[:-1],workbook_edges()+[('s3','worksheet','/xl/worksheets/sheet1.xml')],workbook_edges()[:-1]+[('s2','worksheet','/xl/worksheets/sheet1.xml')]])
def test_missing_duplicate_or_orphan_graph_rejected(edges):
    with pytest.raises(ValueError,match='SDM_XLSX_RELATIONSHIP_GRAPH'):
        inspect_sdm_xlsx(fixture({'xl/_rels/workbook.xml.rels':relationships(edges)}))


@pytest.mark.parametrize('first_id,second_id,sheet_id',[('missing','s2','1'),('s2','s1','1'),('s1','s1','1'),('s1','s2','2')])
def test_sheet_reference_wrong_missing_reused_or_duplicate_identity(first_id,second_id,sheet_id):
    xml=f'<workbook xmlns="{NS}" xmlns:r="{REL[:-1]}"><sheets><sheet name="欄位對照" sheetId="{sheet_id}" r:id="{first_id}"/><sheet name="規則及版本" sheetId="2" r:id="{second_id}"/></sheets></workbook>'
    with pytest.raises(ValueError,match='SDM_XLSX_SHEET_RELATIONSHIP'):
        inspect_sdm_xlsx(fixture({'xl/workbook.xml':xml.encode()}))


def test_empty_package_relationship_rejected():
    with pytest.raises(ValueError,match='SDM_XLSX_RELATIONSHIP_GRAPH'):
        inspect_sdm_xlsx(fixture({'_rels/.rels':relationships([])}))
