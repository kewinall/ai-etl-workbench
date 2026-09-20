from copy import deepcopy
from app.specification_editor import editor_context
from test_etl_specification import design


def test_editor_context_has_bound_fields_without_invented_logic():
    _, run, naming = design()
    before = deepcopy((run, naming))
    result = editor_context(run, naming)
    assert result['status'] == 'EDITOR_CONTEXT_READY'
    assert result['source_columns'][1]['constant_type'] == 'DECIMAL'
    assert result['metric_columns'][0]['id'] == 'total'
    assert 'filters' not in result['binding'] and 'aggregation' not in result['binding']
    assert result['execution_authorized'] is False
    assert before == (run, naming)


def test_missing_stale_or_unconfirmed_context_is_blocked():
    _, run, naming = design()
    assert editor_context(run, None)['status'] == 'BLOCKED'
    run['matches_current'] = False
    assert editor_context(run, naming)['status'] == 'BLOCKED'
    run['matches_current'] = True
    naming['status'] = 'DRAFT'
    assert editor_context(run, naming)['status'] == 'BLOCKED'
