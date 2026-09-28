from io import BytesIO
import pytest
from openpyxl import Workbook
from app.excel_input_contract import validate_excel_content
from app.excel_input_compiler import excel_input_transform


def policy(**changes):
    return dict(version=1, engine='POI', worksheet='明細', header_row=2,
                blank_rows='SKIP', missing_cells='NULL', extra_columns='REJECT',
                formulas='REJECT', trim_strings='NONE', on_error='FAIL', **changes)


def workbook(value='001'):
    book = Workbook()
    sheet = book.create_sheet('明細')
    sheet.append(['說明'])
    sheet.append(['代碼', '金額'])
    sheet.append([value, '12345678901234567890.123456'])
    sheet.append([None, None])
    sheet.append(['002', '1.25'])
    buffer = BytesIO()
    book.save(buffer)
    book.close()
    return buffer.getvalue()


@pytest.mark.parametrize('blank_rows,expected', [('SKIP', 2), ('PRESERVE', 3)])
def test_full_structure_and_no_execution_authority(blank_rows, expected):
    contract = policy()
    contract['blank_rows'] = blank_rows
    result = validate_excel_content(workbook(), contract, ['代碼', '金額'])
    assert result['records_expected'] == expected
    assert result['rows_scanned'] == 3
    assert result['blank_rows'] == 1
    assert result['execution_authorized'] is False
    assert result['type_conversion_verified'] is False


@pytest.mark.parametrize('value,error', [('=1+1', 'EXCEL_FORMULA_REJECTED'), ('#DIV/0!', 'EXCEL_CELL_ERROR_REJECTED')])
def test_formula_and_cell_error_fail_closed(value, error):
    with pytest.raises(ValueError, match=error):
        validate_excel_content(workbook(value), policy(), ['代碼', '金額'])


def test_scan_limit_is_not_complete_proof():
    with pytest.raises(ValueError, match='EXCEL_SCAN_LIMIT_EXCEEDED'):
        validate_excel_content(workbook(), policy(), ['代碼', '金額'], max_rows=1)


def test_header_and_unknown_policy_rejected():
    with pytest.raises(ValueError, match='EXCEL_HEADER_MISMATCH'):
        validate_excel_content(workbook(), policy(), ['wrong', '金額'])
    with pytest.raises(ValueError):
        validate_excel_content(workbook(), dict(policy(), silently_trim=True), ['代碼', '金額'])


def test_native_fragment_explicit_engine_offset_and_exact_number():
    node = excel_input_transform(policy(), [{'stream_name': 'code', 'data_type': 'VARCHAR(32)'},
                                           {'stream_name': 'amount', 'data_type': 'DECIMAL(26,6)'}])
    assert node.findtext('type') == 'ExcelInput'
    assert node.findtext('spreadsheet_type') == 'POI'
    assert node.findtext('sheets/sheet/startrow') == '1'
    assert node.findtext('fields/field/type') == 'String'
    assert node.findall('fields/field')[1].findtext('type') == 'BigNumber'
    assert node.findtext('error_ignored') == 'N'
    assert node.findtext('stoponempty') == 'N'
    assert node.findtext('file/name') == '${SOURCE_XLSX}'
    assert node.find('files') is None


@pytest.mark.parametrize('version', [True, '1', 1.0, 2])
def test_version_is_exact_integer(version):
    with pytest.raises(ValueError):
        validate_excel_content(workbook(), dict(policy(), version=version), ['代碼', '金額'])


@pytest.mark.parametrize('field', [None, {'stream_name': []}, {'stream_name': 'bad-name'}])
def test_bad_compiler_fields_rejected(field):
    with pytest.raises(ValueError):
        excel_input_transform(policy(), [field])
