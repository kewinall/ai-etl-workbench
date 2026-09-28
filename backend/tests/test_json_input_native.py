"""Real network-disabled reader checks; not Run/Vertica/release acceptance."""
import base64
import json
from decimal import Decimal
import os
from pathlib import Path
import subprocess
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest
from test_join_native import wsl_path
from test_json_input_contract import policy
from app.json_input_compiler import json_input_fragment
from test_json_source_staging import uploaded

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_JSON_TEST') != '1',
                               reason='Explicit network-disabled native JSON probe required')


def execute_json(tmp_path, content, columns, *, root_shape='ARRAY', missing_file=False, expect_failure=False, staged_path=None):
    def values(node, **items):
        for key, value in items.items():
            SubElement(node, key).text = str(value)
        return node
    root = Element('pipeline')
    values(SubElement(root, 'info'), name='json_probe')
    order = SubElement(root, 'order')
    types = {'String': 'VARCHAR(255)', 'Integer': 'BIGINT', 'BigNumber': 'NUMERIC(38,18)', 'Boolean': 'BOOLEAN'}
    fragment = json_input_fragment(policy(root_shape), [
        {'stream_name': name, 'source_name': key, 'data_type': types[kind]} for name, key, kind in columns])
    for start, end in fragment['hops']:
        values(SubElement(order, 'hop'), **{'from': start, 'to': end, 'enabled': 'Y'})
    values(SubElement(order, 'hop'), **{'from': 'source_columns', 'to': 'target', 'enabled': 'Y'})
    values(SubElement(root, 'transform'), name='target', type='Dummy', copies=1)
    root.extend(fragment['transforms'])
    (tmp_path / 'candidate.hpl').write_bytes(tostring(root, encoding='utf-8'))
    if not missing_file:
        (tmp_path / 'input.json').write_bytes(content)
    repo = Path(__file__).resolve().parents[2]
    command = ['wsl', '-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'run', '--rm', '--pull', 'never',
        '--network', 'none', '--hostname', 'hop-validation', '--add-host', 'hop-validation:127.0.0.1',
        '--entrypoint', 'java', '-e', 'TZ=UTC', '-w', '/opt/hop',
        '-v', wsl_path(repo / 'scripts' / 'hop') + ':/validation:ro',
        '-v', wsl_path(tmp_path) + ':/candidate:ro', 'ai-etl-workbench-worker:dev',
        '-cp', 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*', '/validation/ExecuteJsonProbe.java']
    if staged_path:
        offset = command.index('ai-etl-workbench-worker:dev')
        command[offset:offset] = ['-v', wsl_path(staged_path.parent) + ':/staged:ro']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=75)
    if expect_failure:
        assert result.returncode != 0, result.stdout + result.stderr
        assert 'Hop execution failed' in result.stderr
        return []
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [[None if value == 'NULL' else base64.b64decode(value).decode('utf-8')
             for value in line.split('=', 1)[1].split('|')]
            for line in result.stdout.splitlines() if line.startswith('JSON_RESULT=')]
    return rows


def test_native_missing_null_order_chinese_and_whitespace(tmp_path):
    content = '[{"代碼":"002","金額":12.25},{"代碼":"001","金額":null},{"代碼":"  中文  "},{}]'.encode()
    rows = execute_json(tmp_path, content, [('code', '代碼', 'String'), ('amount', '金額', 'BigNumber')])
    assert rows == [['002', '12.25'], ['001', None], ['  中文  ', None], [None, None]]


@pytest.mark.parametrize('token', ['12345678901234567890.123456', '0.123456789012345678'])
def test_native_numeric_token_precision(tmp_path, token):
    rows = execute_json(tmp_path, ('[{"amount":' + token + '}]').encode(),
                        [('amount', 'amount', 'BigNumber')])
    assert Decimal(rows[0][0]) == Decimal(token)


def test_native_single_object_string_number_boolean(tmp_path):
    rows = execute_json(tmp_path, b'{"id":"001","amount":"12345678901234567890.123456","enabled":false}',
                        [('id', 'id', 'String'), ('amount', 'amount', 'BigNumber'),
                         ('enabled', 'enabled', 'Boolean')], root_shape='OBJECT')
    assert rows == [['001', '12345678901234567890.123456', 'false']]


def test_native_literal_property_names_do_not_become_variables(tmp_path):
    names = ['a.b', "a'b", 'a"b', 'a\\b', '${PROBE}', '$[PROBE]', '中文欄位']
    content = json.dumps([{name: str(index) for index, name in enumerate(names)}], ensure_ascii=False).encode()
    columns = [('field_' + str(index), name, 'String')
               for index, name in enumerate(names)]
    rows = execute_json(tmp_path, content, columns)
    assert rows == [[str(index) for index in range(len(names))]]


@pytest.mark.parametrize('content,missing_file', [(b'[{"id":1}]', True), (b'', False), (b'{invalid', False)])
def test_native_missing_empty_malformed_files_fail(tmp_path, content, missing_file):
    execute_json(tmp_path, content, [('id', 'id', 'Integer')], missing_file=missing_file, expect_failure=True)


def test_native_empty_string_null_and_all_null_row_are_distinct(tmp_path):
    rows = execute_json(tmp_path, b'[{"value":""},{"value":null},{}]', [('value', 'value', 'String')])
    assert rows == [[''], [None], [None]]


def test_native_verified_bom_reader_copy_and_exact_integer_boundary(tmp_path):
    from app.json_input_contract import prepare_json_reader_content
    reader, proof = prepare_json_reader_content(b'\xef\xbb\xbf[{"id":9223372036854775807},{"id":-9223372036854775807}]', policy(), ['id'])
    assert proof['normalization'] == 'UTF8_BOM_REMOVED'
    rows = execute_json(tmp_path, reader,
                        [('id', 'id', 'Integer')])
    assert rows == [['9223372036854775807'], ['-9223372036854775807']]


def test_native_unprepared_bom_is_not_misrepresented_as_supported(tmp_path):
    execute_json(tmp_path, b'\xef\xbb\xbf[{"id":1}]', [('id', 'id', 'Integer')], expect_failure=True)


def test_native_reads_verified_attempt_not_reopened_upload(tmp_path, uploaded):
    from uuid import uuid4
    from app.source_staging import stage_json_source
    with stage_json_source(uuid4(), uploaded, policy()) as staged:
        # Change only this test's synthetic upload after the verified snapshot.
        Path(uploaded['path']).write_bytes(b'[{"id":"changed"}]')
        rows = execute_json(tmp_path, b'', [('id', 'id', 'String')], staged_path=staged['path'])
        assert rows == [['001']]
