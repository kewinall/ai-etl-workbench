"""Opt-in actual Hop MergeJoin semantics; not platform compiler or Vertica QA."""
import os
from pathlib import Path
import subprocess
from xml.etree.ElementTree import Element, SubElement, tostring
import pytest

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_JOIN_TEST') != '1',
                                reason='Explicit network-disabled native Join probe required')


def values(parent, **items):
    for name, value in items.items():
        SubElement(parent, name).text = str(value)
    return parent


def probe_xml(kind, exclude_right_null):
    root = Element('pipeline')
    values(SubElement(root, 'info'), name='synthetic_join_probe')
    edges = [('left', 'left_sort'), ('left_sort', 'join'), ('right_sort', 'join'), ('join', 'target')]
    edges += [('right', 'right_filter'), ('right_filter', 'right_sort'), ('right_filter', 'discard')] if exclude_right_null else [('right', 'right_sort')]
    order = SubElement(root, 'order')
    for start, end in edges:
        values(SubElement(order, 'hop'), **{'from': start, 'to': end, 'enabled': 'Y'})
    for side in ('left', 'right'):
        node = values(SubElement(root, 'transform'), name=side, type='CSVInput', copies=1, distribute='Y',
            filename=f'/candidate/{side}.csv', separator=',', enclosure='"', header='Y', encoding='UTF-8',
            lazy_conversion='N', parallel='N', newline_possible='Y', buffer_size=50000)
        fields = SubElement(node, 'fields')
        for name in ('key', 'value'):
            values(SubElement(fields, 'field'), name=f'{side}_{name}', type='String', trim_type='none', length=64, precision=-1)
        node = values(SubElement(root, 'transform'), name=side+'_sort', type='SortRows', copies=1,
            directory='${java.io.tmpdir}', sort_prefix='join_probe', sort_size=10000, unique_rows='N', compress='N')
        values(SubElement(SubElement(node, 'fields'), 'field'), name=side+'_key', ascending='Y',
               case_sensitive='Y', collator_enabled='N', collator_strength=0, presorted='N')
    if exclude_right_null:
        node = values(SubElement(root, 'transform'), name='right_filter', type='FilterRows', copies=1,
            send_true_to='right_sort', send_false_to='discard')
        values(SubElement(SubElement(node, 'compare'), 'condition'), negated='N', leftvalue='right_key', function='IS NOT NULL')
        values(SubElement(root, 'transform'), name='discard', type='Dummy', copies=1)
    node = values(SubElement(root, 'transform'), name='join', type='MergeJoin', copies=1,
        join_type='LEFT OUTER' if kind == 'LEFT' else 'INNER', transform1='left_sort', transform2='right_sort')
    SubElement(SubElement(node, 'keys_1'), 'key').text = 'left_key'
    SubElement(SubElement(node, 'keys_2'), 'key').text = 'right_key'
    values(SubElement(root, 'transform'), name='target', type='Dummy', copies=1)
    return tostring(root, encoding='utf-8')


def wsl_path(path):
    return subprocess.run(['wsl', '-d', 'RockyLinux9', '-u', 'root', '--', 'wslpath', '-a', Path(path).as_posix()],
        check=True, capture_output=True, text=True, timeout=15).stdout.strip()


@pytest.mark.parametrize('kind', ['LEFT', 'INNER'])
@pytest.mark.parametrize('exclude_right_null', [False, True])
@pytest.mark.parametrize('right_all_null', [False, True])
def test_native_join_exact_rows_and_null_behavior(tmp_path, kind, exclude_right_null, right_all_null):
    repo = Path(__file__).resolve().parents[2]
    (tmp_path/'candidate.hpl').write_bytes(probe_xml(kind, exclude_right_null))
    (tmp_path/'left.csv').write_bytes(b'left_key,left_value\n1,L1\n1,L2\n2,unmatched\n,null_left\nA,upper\na,lower\nA ,trailing\n')
    (tmp_path/'right.csv').write_bytes(b'right_key,right_value\n,null_right\n' if right_all_null else
        b'right_key,right_value\n1,R1\n1,R2\n3,right_only\n,null_right\nA,Rupper\n')
    command = ['wsl', '-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'run', '--rm', '--pull', 'never',
        '--network', 'none', '--hostname', 'hop-validation', '--add-host', 'hop-validation:127.0.0.1',
        '--entrypoint', 'java', '-w', '/opt/hop', '-v', wsl_path(repo/'scripts'/'hop')+':/validation:ro',
        '-v', wsl_path(tmp_path)+':/candidate:ro', 'ai-etl-workbench-worker:dev',
        '-cp', 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*', '/validation/ExecuteJoinProbe.java']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
    actual = sorted(line.removeprefix('SYNTHETIC_JOIN_RESULT=') for line in result.stdout.splitlines()
                    if line.startswith('SYNTHETIC_JOIN_RESULT='))
    expected = [] if right_all_null else [f'1|{left}|1|{right}' for left in ('L1', 'L2') for right in ('R1', 'R2')]
    if not right_all_null:
        expected.append('A|upper|A|Rupper')
    if not exclude_right_null:
        expected.append('<NULL>|null_left|<NULL>|null_right')
    if kind == 'LEFT':
        expected.extend(['2|unmatched|<NULL>|<NULL>', 'a|lower|<NULL>|<NULL>', 'A |trailing|<NULL>|<NULL>'])
        if right_all_null:
            expected.extend(['1|L1|<NULL>|<NULL>', '1|L2|<NULL>|<NULL>', 'A|upper|<NULL>|<NULL>'])
        if exclude_right_null:
            expected.append('<NULL>|null_left|<NULL>|<NULL>')
    assert actual == sorted(expected), {'kind': kind, 'filtered_null': exclude_right_null, 'actual': actual, 'expected': sorted(expected)}
    assert f'NATIVE_JOIN_COLLECTED rows={len(expected)} errors=0 database=false release=false' in result.stdout
