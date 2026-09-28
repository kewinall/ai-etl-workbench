"""Opt-in native Hop ExcelInput collector; not full Run/Vertica/release acceptance."""
import base64
import os
from pathlib import Path
import subprocess
from xml.etree.ElementTree import fromstring, tostring
import pytest
from app.excel_input_compiler import excel_input_transform
from test_excel_input_contract import policy, workbook
from test_join_native import wsl_path

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_EXCEL_TEST') != '1',
                               reason='Explicit network-disabled native Excel probe required')


@pytest.mark.parametrize('blank_rows', ['SKIP', 'PRESERVE'])
def test_native_selected_sheet_header_exact_decimal_and_blanks(tmp_path, blank_rows):
    contract = dict(policy(), blank_rows=blank_rows)
    root = fromstring('<pipeline><info><name>excel_probe</name></info><order><hop>'
                      '<from>source</from><to>target</to><enabled>Y</enabled></hop></order>'
                      '<transform><name>target</name><type>Dummy</type><copies>1</copies></transform></pipeline>')
    source = excel_input_transform(contract, [{'stream_name': 'code', 'data_type': 'VARCHAR(32)'},
                                              {'stream_name': 'amount', 'data_type': 'DECIMAL(26,6)'}])
    source.find('file/name').text = '/candidate/input.xlsx'
    root.append(source)
    (tmp_path / 'candidate.hpl').write_bytes(tostring(root, encoding='utf-8'))
    (tmp_path / 'input.xlsx').write_bytes(workbook())
    repo = Path(__file__).resolve().parents[2]
    command = ['wsl', '-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'run', '--rm', '--pull', 'never',
        '--network', 'none', '--hostname', 'hop-validation', '--add-host', 'hop-validation:127.0.0.1',
        '--entrypoint', 'java', '-w', '/opt/hop',
        '-v', wsl_path(repo / 'scripts' / 'hop') + ':/validation:ro',
        '-v', wsl_path(tmp_path) + ':/candidate:ro', 'ai-etl-workbench-worker:dev',
        '-cp', 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*', '/validation/ExecuteExcelProbe.java']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [[None if value == 'NULL' else base64.b64decode(value).decode('utf-8')
             for value in line.split('=', 1)[1].split('|')]
            for line in result.stdout.splitlines() if line.startswith('EXCEL_RESULT=')]
    expected = [['001', '12345678901234567890.123456'], ['002', '1.25']]
    if blank_rows == 'PRESERVE':
        expected.insert(1, [None, None])
    assert rows == expected, result.stdout + result.stderr
    assert f'EXCEL_COLLECTED rows={len(expected)} errors=0 database=false release=false' in result.stdout
