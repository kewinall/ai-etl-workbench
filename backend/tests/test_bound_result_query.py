from copy import deepcopy
from unittest.mock import Mock
import pytest
from app.bound_result_query import execute_bound_result_query
from app.result_query_plan import build_result_query_plan
from test_etl_specification import design


def test_executes_exact_pinned_projection_without_claiming_qa():
    plan = build_result_query_plan(*design())
    cursor = Mock()
    result = execute_bound_result_query(cursor, plan, {'result_query_checksum': plan['checksum']})
    cursor.execute.assert_called_once_with(plan['plan']['sql'])
    assert result['actual_provenance'] == 'NOT_VERIFIED'
    assert not result['qa_passed'] and not result['release_ready']


@pytest.mark.parametrize('mutation', ['sql', 'pin', 'checksum', 'sql_checksum'])
def test_changed_query_or_execution_pin_never_touches_database(mutation):
    plan = deepcopy(build_result_query_plan(*design()))
    pin = {'result_query_checksum': plan['checksum']}
    if mutation == 'sql':
        plan['plan']['sql'] = 'SELECT 1'
    elif mutation == 'pin':
        pin['result_query_checksum'] = '0' * 64
    elif mutation == 'checksum':
        plan['checksum'] = '0' * 64
    else:
        plan['plan']['sql_checksum'] = '0' * 64
    cursor = Mock()
    with pytest.raises(ValueError, match='RESULT_QUERY_BINDING_CHANGED'):
        execute_bound_result_query(cursor, plan, pin)
    cursor.execute.assert_not_called()
