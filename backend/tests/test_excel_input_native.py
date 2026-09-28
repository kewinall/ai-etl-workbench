"""Opt-in native Hop ExcelInput collector; not full Run/Vertica/release acceptance."""
import base64
from datetime import datetime
from io import BytesIO
import os
from pathlib import Path
import subprocess
from xml.etree.ElementTree import fromstring, tostring
import pytest
from openpyxl import Workbook
from app.excel_input_compiler import excel_input_transform
from test_excel_input_contract import policy, workbook
from test_join_native import wsl_path
from test_excel_source_staging import source
from app.source_staging import stage_excel_source
from uuid import uuid4

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_EXCEL_TEST') != '1',
                               reason='Explicit network-disabled native Excel probe required')


def execute_excel(tmp_path, contract, fields, content, *, staged_path=None, compiled_hpl=None):
    root = fromstring('<pipeline><info><name>excel_probe</name></info><order><hop>'
                      '<from>source</from><to>target</to><enabled>Y</enabled></hop></order>'
                      '<transform><name>target</name><type>Dummy</type><copies>1</copies></transform></pipeline>')
    if compiled_hpl is not None:
        root = fromstring(compiled_hpl)
        target = root.find("transform[name='target']")
        for child in list(target):
            if child.tag not in ('name', 'type', 'copies', 'distribute', 'GUI'):
                target.remove(child)
        target.find('type').text = 'Dummy'
        source = root.find("transform[name='source']")
    else:
        source = excel_input_transform(contract, fields)
        root.append(source)
    source.find('file/name').text = '/staged/source.xlsx' if staged_path else '/candidate/input.xlsx'
    (tmp_path / 'candidate.hpl').write_bytes(tostring(root, encoding='utf-8'))
    (tmp_path / 'input.xlsx').write_bytes(content)
    repo = Path(__file__).resolve().parents[2]
    command = ['wsl', '-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'run', '--rm', '--pull', 'never',
        '--network', 'none', '--hostname', 'hop-validation', '--add-host', 'hop-validation:127.0.0.1',
        '--entrypoint', 'java', '-e', 'TZ=UTC', '-w', '/opt/hop',
        '-v', wsl_path(repo / 'scripts' / 'hop') + ':/validation:ro',
        '-v', wsl_path(tmp_path) + ':/candidate:ro', 'ai-etl-workbench-worker:dev',
        '-cp', 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*', '/validation/ExecuteExcelProbe.java']
    if staged_path:
        command[command.index('ai-etl-workbench-worker:dev'):command.index('ai-etl-workbench-worker:dev')] = [
            '-v', wsl_path(staged_path.parent) + ':/staged:ro']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [[None if value == 'NULL' else base64.b64decode(value).decode('utf-8')
             for value in line.split('=', 1)[1].split('|')]
            for line in result.stdout.splitlines() if line.startswith('EXCEL_RESULT=')]
    return rows, result.stdout + result.stderr


@pytest.mark.parametrize('blank_rows', ['SKIP', 'PRESERVE'])
def test_native_selected_sheet_header_exact_decimal_and_blanks(tmp_path, blank_rows):
    rows, output = execute_excel(tmp_path, dict(policy(), blank_rows=blank_rows),
                                [{'stream_name': 'code', 'data_type': 'VARCHAR(32)'},
                                 {'stream_name': 'amount', 'data_type': 'DECIMAL(26,6)'}], workbook())
    expected = [['001', '12345678901234567890.123456'], ['002', '1.25']]
    if blank_rows == 'PRESERVE':
        expected.insert(1, [None, None])
    assert rows == expected, output
    assert f'EXCEL_COLLECTED rows={len(expected)} errors=0 database=false release=false' in output


@pytest.mark.parametrize('types,values,expected', [
    (['DATE', 'TIMESTAMP'], ['2026-09-28', datetime(2026, 9, 28, 12, 34, 56)],
     ['2026-09-28T00:00:00Z', '2026-09-28T12:34:56Z']),
    (['BOOLEAN', 'BOOLEAN'], [True, False], ['true', 'false']),
    (['BOOLEAN', 'BOOLEAN'], ['true', 'false'], ['true', 'false']),
    (['VARCHAR(32)', 'BIGINT'], ['  中文  ', 123], ['  中文  ', '123']),
    (['BIGINT', 'BIGINT'], ['9223372036854775807', '-9223372036854775807'],
     ['9223372036854775807', '-9223372036854775807']),
    (['DECIMAL(18,4)', 'VARCHAR(32)'], [12.125, None], ['12.125', None]),
])
def test_native_type_boundaries(tmp_path, types, values, expected):
    book = Workbook()
    sheet = book.active
    sheet.title = '明細'
    sheet.append(['說明'])
    sheet.append(['first', 'second'])
    sheet.append(values)
    buffer = BytesIO()
    book.save(buffer)
    book.close()
    fields = [{'stream_name': name, 'data_type': kind} for name, kind in zip(['first', 'second'], types)]
    rows, output = execute_excel(tmp_path, policy(), fields, buffer.getvalue())
    assert rows == [expected], output


def test_native_reads_verified_attempt_copy(tmp_path, source):
    with stage_excel_source(uuid4(), source, policy()) as staged:
        fields = [{'stream_name': name, 'data_type': field['type']}
                  for name, field in zip(['code', 'amount'], source['fields'])]
        rows, output = execute_excel(tmp_path, policy(), fields, b'', staged_path=staged['path'])
        assert rows == [['001', '12345678901234567890.123456'], ['002', '1.25']], output
        directory = staged['directory']
    assert not directory.exists()


def test_native_v4_compiled_filter_aggregation_matches_expected(tmp_path):
    from app.hpl_compiler import compile_hpl
    from test_excel_specification import excel_design
    from decimal import Decimal
    captured = []
    args = excel_design(rows=[['B', '200.25'], ['A', '150.25'], ['A', '20.00'], ['B', '300.25']], capture=captured)
    compiled = compile_hpl(*args)
    assert compiled['status'] == 'VALIDATED_NOT_APPROVED', compiled
    rows, output = execute_excel(tmp_path, policy(), [], captured[0], compiled_hpl=compiled['hpl'])
    assert [(category, Decimal(total), int(count)) for category, total, count in rows] == [
        ('A', Decimal('150.25'), 1), ('B', Decimal('500.50'), 2)], output
