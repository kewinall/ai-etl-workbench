from io import BytesIO
from zipfile import ZipFile
import pytest
from app.release_bundle import BundleArtifact,MEMBERS
from app.release_content_gate import check_release_content


def artifacts(text='safe'):
    output=BytesIO()
    with ZipFile(output,'w') as z:z.writestr('xl/worksheets/sheet1.xml',f'<x>{text}</x>')
    return [BundleArtifact(k,output.getvalue() if k=='SDM' else b'<safe/>','a'*64,'r','s','n') for k in MEMBERS]


@pytest.mark.parametrize('text,code',[
    ('C:\\Users\\operator\\file','ABSOLUTE_PATH'),('/app/uploads/file','ABSOLUTE_PATH'),
    ('host.docker.internal','HOST_REFERENCE'),('secret&amp;value','DEPLOYMENT_VALUE')])
def test_scans_inside_xlsx(text,code):
    with pytest.raises(ValueError,match=code):check_release_content(artifacts(text),forbidden_values=['secret&value'])


def test_pass_is_not_portability_or_release():
    result=check_release_content(artifacts(),forbidden_values=['private.example'])
    assert result['portability']=='NOT_VERIFIED' and not result['release_ready']


def test_xml_namespace_url_is_not_windows_drive():
    assert check_release_content(artifacts('http://schemas.openxmlformats.org/spreadsheetml/2006/main'),forbidden_values=[])['release_ready'] is False


def xml_artifacts(xml):
    output=BytesIO()
    with ZipFile(output,'w') as z:z.writestr('xl/styles.xml',xml)
    return [BundleArtifact(k,output.getvalue() if k=='SDM' else b'<safe/>','a'*64,'r','s','n') for k in MEMBERS]


def test_standard_attribute_name_is_not_a_value():
    xml='<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs count="1"/></styleSheet>'
    assert check_release_content(xml_artifacts(xml),forbidden_values=['count'])['status']=='CONTENT_SCREEN_PASSED'


@pytest.mark.parametrize('xml',[
    '<x count="count"/>', '<x>count</x>', '<x><!-- count --></x>',
    '<x><?test count?></x>', '<x private_count="1"/>',
    '<x><r>co</r><r>unt</r></x>', '<x>&#99;ount</x>',
    '<x xmlns="private_count"/>',
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs count="count"/></styleSheet>',
])
def test_names_values_comments_entities_and_split_text_remain_screened(xml):
    with pytest.raises(ValueError,match='DEPLOYMENT_VALUE'):
        check_release_content(xml_artifacts(xml),forbidden_values=['count'])


@pytest.mark.parametrize('xml',['<x>','<!DOCTYPE x [<!ENTITY a "safe">]><x>&a;</x>'])
def test_invalid_or_entity_definitions_fail_closed(xml):
    with pytest.raises(ValueError,match='RELEASE_SCREEN_'):
        check_release_content(xml_artifacts(xml),forbidden_values=[])
