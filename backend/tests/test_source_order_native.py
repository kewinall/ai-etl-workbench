"""Opt-in real Hop source ordinal test; collector, not Vertica/release proof."""
import base64
from decimal import Decimal
import os
from pathlib import Path
import subprocess
from xml.etree.ElementTree import fromstring, tostring

import pytest

from app.hpl_compiler import compile_hpl
from test_source_order_compilation import ordered_design
from test_join_native import wsl_path

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_SOURCE_ORDER_TEST') != '1',
                               reason='Explicit network-disabled native source-order probe required')


@pytest.mark.parametrize('header', [True, False])
def test_real_logical_record_ordinals_survive_multiline_and_duplicates(tmp_path, header):
    args = ordered_design()
    args[1]['input_snapshot']['source_config']['csv_input_contract_v1']['header'] = header
    root = fromstring(compile_hpl(*args)['hpl'])
    root.find("./transform[name='source']/filename").text = '/candidate/input.csv'
    target = root.find("./transform[name='target']")
    for child in list(target):
        if child.tag not in ('name', 'type', 'copies', 'distribute', 'GUI'):
            target.remove(child)
    target.find('type').text = 'Dummy'
    (tmp_path / 'candidate.hpl').write_bytes(tostring(root, encoding='utf-8'))
    text = ('類別,金額\n' if header else '') + 'Z,30\n"A\nB",10\nZ,30\n'
    (tmp_path / 'input.csv').write_bytes(text.encode('utf-8'))
    repo = Path(__file__).resolve().parents[2]
    command = ['wsl', '-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'run', '--rm', '--pull', 'never',
        '--network', 'none', '--hostname', 'hop-validation', '--add-host', 'hop-validation:127.0.0.1',
        '--entrypoint', 'java', '-w', '/opt/hop',
        '-v', wsl_path(repo / 'scripts' / 'hop') + ':/validation:ro',
        '-v', wsl_path(tmp_path) + ':/candidate:ro', 'ai-etl-workbench-worker:dev',
        '-cp', 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*', '/validation/ExecuteSourceOrderProbe.java']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [[base64.b64decode(value).decode('utf-8') for value in line.split('=', 1)[1].split('|')]
            for line in result.stdout.splitlines() if line.startswith('SOURCE_ORDER_RESULT=')]
    actual = [(category, Decimal(amount), int(position)) for category, amount, position in rows]
    assert actual == [('Z', Decimal(30), 1), ('A\nB', Decimal(10), 2), ('Z', Decimal(30), 3)]
    assert 'SOURCE_ORDER_COLLECTED rows=3 errors=0 database=false release=false' in result.stdout
