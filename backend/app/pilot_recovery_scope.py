"""Fail-closed scope for the frozen recovery corpus; grants no SQL authority."""
from hashlib import sha256
import re

from .pilot_fixture_catalog import corpus


def check_scope(current, binding_checksum, definition):
    """Require exact enrolled definition, source bytes, and a never-written root run.

    The caller must additionally lock/check cohort enrollment and target ownership,
    create a NEW target through the normal dispatcher, and verify it is empty.
    This pure check alone must never authorize an ALTER operation.
    """
    cases = [c for c in corpus() if c['definition'] == definition
             and c['definition']['scenario'] == 'EXECUTION_RECOVERY']
    if len(cases) != 1:
        raise ValueError('RECOVERY_FROZEN_CASE_REQUIRED')
    case = cases[0]
    run = current['run']
    spec = current['specification']
    sources = run['input_snapshot']['source_config']['sources']
    expected = case['fixture']['sources']
    columns = [c[0] for c in case['oracle']['columns']]
    if (current['binding_checksum'] != binding_checksum
            or run.get('write_started') is not False or run.get('parent_run_id')
            or spec['target_schema'] != 'ai_sample'
            or not re.fullmatch(r'pilot_[a-f0-9]{32}', spec['target_table'])
            or spec['write_mode'] != 'APPEND' or spec['output_columns'] != columns
            or len(sources) != len(expected)):
        raise ValueError('RECOVERY_SCOPE_INVALID')
    for actual, frozen in zip(sources, expected):
        fields = [{'name': name, 'type': kind} for name, kind in frozen['fields']]
        if (actual.get('checksum') != sha256(frozen['content'].encode('utf-8')).hexdigest()
                or actual.get('fields') != fields or actual.get('type') != 'CSV'):
            raise ValueError('RECOVERY_SOURCE_CHANGED')
    column = case['fixture']['initial_change']['column']
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', column):
        raise ValueError('RECOVERY_COLUMN_INVALID')
    return {'table': spec['target_table'], 'column': column,
            'renamed_to': column + '_missing_fault', 'columns': columns,
            'case_key': definition['case_key']}
