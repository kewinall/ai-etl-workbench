from copy import deepcopy
import pytest
from app.result_query_plan import build_result_query_plan
from test_etl_specification import design


def test_exact_target_projection_no_filtering_or_duplicate_elimination():
    spec, run, naming = design()
    before = deepcopy((spec, run, naming))
    result = build_result_query_plan(spec, run, naming)
    assert result == build_result_query_plan(spec, run, naming)
    assert (spec, run, naming) == before
    assert result['plan']['sql'] == 'SELECT "category", "total_amount", "row_count" FROM "ai_sample"."totals" LIMIT 10001;'
    assert result['plan']['columns'] == [
        {'name': 'category', 'data_type': 'VARCHAR(32)'},
        {'name': 'total_amount', 'data_type': 'NUMERIC(18,2)'},
        {'name': 'row_count', 'data_type': 'BIGINT'}]
    assert result['plan']['max_accepted_rows'] < result['plan']['overflow_row_limit']
    assert result['plan']['required_target_scope'] == 'EXCLUSIVE_RUN_TARGET'
    assert result['actual_provenance'] == 'NOT_VERIFIED'
    assert not result['execution_authorized'] and not result['qa_passed'] and not result['release_ready']


@pytest.mark.parametrize('field,value', [('target_table', 'totals; DROP TABLE t'), ('output_columns', ['*']), ('sql', 'SELECT 1'), ('row_limit', 1)])
def test_arbitrary_query_input_is_rejected(field, value):
    spec, run, naming = design()
    spec[field] = value
    with pytest.raises(ValueError, match='RESULT_QUERY_VALID_SPECIFICATION_REQUIRED'):
        build_result_query_plan(spec, run, naming)


def test_stale_input_rejected_and_output_order_changes_fingerprint():
    spec, run, naming = design()
    first = build_result_query_plan(spec, run, naming)
    spec['output_columns'].reverse()
    second = build_result_query_plan(spec, run, naming)
    assert first['checksum'] != second['checksum']
    assert first['plan']['sql_checksum'] != second['plan']['sql_checksum']
    run['matches_current'] = False
    with pytest.raises(ValueError, match='RESULT_QUERY_VALID_SPECIFICATION_REQUIRED'):
        build_result_query_plan(spec, run, naming)
