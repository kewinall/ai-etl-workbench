from copy import deepcopy
from hashlib import sha256
from xml.etree import ElementTree as ET
import pytest
from app.hpl_compiler import compile_hpl
from app.qa_runtime_options import inspect_options
from test_excel_specification import excel_design


def test_excel_reader_selection_and_type_options_are_inspected_not_omitted():
    compiled = compile_hpl(*excel_design())
    result = inspect_options(compiled)
    assert result['version'] == 2 and result['hpl_checksum'] == compiled['hpl_checksum']
    assert len(result['sources']) == 1
    source = result['sources'][0]
    assert source['component'] == 'ExcelInput'
    assert source['file']['name'] == '${SOURCE_XLSX}'
    assert source['sheet'] == {'name': '明細', 'startrow': '1', 'startcol': '0'}
    assert source['options']['noempty'] == 'Y'
    assert source['options']['strict_types'] == 'N'
    assert source['fields'][1]['type'] == 'BigNumber'
    assert source['fields'][1]['precision'] == '4'
    assert 'SEPARATE_ENGINE_PROBES_NOT_THIS_RUN' in result['behavior_reference']['scope']
    assert 'Vertica acceptance' in result['behavior_reference']['limits']
    assert 'upload_id' not in str(result) and 'sample_rows' not in str(result)


@pytest.mark.parametrize('path,value', [
    ('spreadsheet_type', 'SAX_POI'), ('header', 'N'), ('noempty', 'N'), ('stoponempty', 'Y'),
    ('strict_types', 'Y'), ('error_ignored', 'Y'), ('error_line_skipped', 'Y'),
    ('accept_filenames', 'Y'), ('add_to_result_filenames', 'Y'), ('limit', '1'),
    ('file/name', '${SOURCE_CSV}'), ('file/file_required', 'N'), ('file/filemask', '*'),
    ('file/include_subfolders', 'Y'), ('sheets/sheet/name', 'other'), ('sheets/sheet/startrow', '0'),
    ('sheets/sheet/startcol', '1'), ('fields/field/type', 'Integer'), ('fields/field/trim_type', 'both'),
    ('fields/field/repeat', 'Y'), ('fields/field/format', 'changed')])
def test_changed_excel_options_rejected_even_if_xml_checksum_recomputed(path, value):
    compiled = compile_hpl(*excel_design())
    root = ET.fromstring(compiled['hpl'])
    source = root.find("transform[name='source']")
    assert source.find(path) is not None
    source.find(path).text = value
    compiled['hpl'] = ET.tostring(root, encoding='unicode')
    compiled['hpl_checksum'] = sha256(compiled['hpl'].encode()).hexdigest()
    with pytest.raises(ValueError, match='QA_RUNTIME_EXCEL_'):
        inspect_options(compiled)


@pytest.mark.parametrize('tag', ['file', 'sheets/sheet', 'fields/field', 'node'])
def test_duplicate_excel_selection_fields_or_source_rejected(tag):
    compiled = compile_hpl(*excel_design())
    root = ET.fromstring(compiled['hpl'])
    source = root.find("transform[name='source']")
    if tag == 'node':
        root.append(deepcopy(source))
    else:
        holder = source if '/' not in tag else source.find(tag.split('/')[0])
        holder.append(deepcopy(source.find(tag)))
    compiled['hpl'] = ET.tostring(root, encoding='unicode')
    compiled['hpl_checksum'] = sha256(compiled['hpl'].encode()).hexdigest()
    with pytest.raises(ValueError, match='QA_RUNTIME_'):
        inspect_options(compiled)
