from xml.etree.ElementTree import Element, SubElement, tostring
import pytest
from app.sdm_xlsx_semantics import expected_sdm_cells, validate_sdm_xlsx
from app.sdm_xlsx_structure import NS
from test_etl_specification import design
from test_sdm_xlsx_structure import fixture as structure_fixture


def workbook_fixture(spec,run,naming,mutate=None):
    cells=expected_sdm_cells(spec,run,naming)
    if mutate:mutate(cells)
    parts={}
    for index,values in enumerate(cells,1):
        root=Element('worksheet',xmlns=NS);data=SubElement(root,'sheetData')
        rows={}
        for ref,value in values.items():
            if ref[1:] not in rows:rows[ref[1:]]=SubElement(data,'row',r=ref[1:])
            row=rows[ref[1:]];cell=SubElement(row,'c',r=ref,t='n' if isinstance(value,int) else 'inlineStr')
            if isinstance(value,int):SubElement(cell,'v').text=str(value)
            else:SubElement(SubElement(cell,'is'),'t').text=value
        parts[f'xl/worksheets/sheet{index}.xml']=tostring(root)
    return structure_fixture(parts)


def test_exact_cells_match_but_never_grant_release():
    spec,run,naming=design();result=validate_sdm_xlsx(workbook_fixture(spec,run,naming),spec,run,naming)
    assert result['semantic_equality']=='CANDIDATE_LAYOUT_MATCHED'
    assert result['portability']=='NOT_VERIFIED' and not result['release_ready']


@pytest.mark.parametrize('sheet,cell,value',[(0,'B7','wrong_column'),(0,'C7','VARCHAR(32)'),(0,'E7','錯誤原名'),(0,'A7',9),(1,'B7','other.table'),(1,'B17','a'*64),(0,'A99','unexpected data')])
def test_wrong_mapping_type_source_order_target_checksum_or_extra_cells_rejected(sheet,cell,value):
    spec,run,naming=design()
    content=workbook_fixture(spec,run,naming,lambda cells:cells[sheet].update({cell:value}))
    with pytest.raises(ValueError,match='SDM_XLSX_SPECIFICATION_MISMATCH'):
        validate_sdm_xlsx(content,spec,run,naming)


def alter_part(content,name,change):
    from io import BytesIO
    from zipfile import ZipFile,ZIP_DEFLATED
    from xml.etree.ElementTree import fromstring
    output=BytesIO()
    with ZipFile(BytesIO(content)) as source,ZipFile(output,'w',ZIP_DEFLATED) as target:
        for member in source.namelist():
            raw=source.read(member)
            if member==name:
                root=fromstring(raw);change(root);raw=tostring(root)
            target.writestr(member,raw)
    return output.getvalue()


def test_unused_shared_string_rejected():
    spec,run,naming=design()
    def add(root):SubElement(SubElement(root,f'{{{NS}}}si'),f'{{{NS}}}t').text='synthetic-private-extra'
    content=alter_part(workbook_fixture(spec,run,naming),'xl/sharedStrings.xml',add)
    with pytest.raises(ValueError,match='SDM_XLSX_UNUSED_STRINGS'):
        validate_sdm_xlsx(content,spec,run,naming)


@pytest.mark.parametrize('kind',['orphan','duplicate_row','wrong_row','second_container'])
def test_extra_or_ambiguous_cell_structures_rejected(kind):
    spec,run,naming=design()
    def change(root):
        data=root.find(f'{{{NS}}}sheetData')
        if kind=='orphan':SubElement(root,f'{{{NS}}}c',r='A99',t='str')
        elif kind=='duplicate_row':SubElement(data,f'{{{NS}}}row',r='2')
        elif kind=='wrong_row':data[0].set('r','999')
        else:SubElement(root,f'{{{NS}}}sheetData')
    content=alter_part(workbook_fixture(spec,run,naming),'xl/worksheets/sheet1.xml',change)
    with pytest.raises(ValueError,match='SDM_XLSX_(ORPHAN_CELL|ROW_STRUCTURE|CELL_STRUCTURE)'):
        validate_sdm_xlsx(content,spec,run,naming)
