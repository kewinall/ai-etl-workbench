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


def test_ordered_editor_preserves_contract_and_separates_generated_column():
    from test_source_order_compilation import ordered_design
    spec,run,naming=ordered_design();before=deepcopy((run,naming))
    result=editor_context(run,naming)
    assert result['status']=='EDITOR_CONTEXT_READY',result
    assert result['binding']['version']==3
    assert result['binding']['source_order']==spec['source_order']
    assert result['generated_columns']==[{'source_name':'$source_order.source.0','name':'source_position','data_type':'BIGINT'}]
    assert [c['name'] for c in result['source_columns']]==['category','amount']
    assert result['metric_columns']==[]
    assert not result['execution_authorized']
    assert (run,naming)==before


def test_ordered_editor_rejects_missing_or_invalid_generated_naming():
    from test_source_order_compilation import ordered_design
    from app.platform_harness import checksum
    for kind in ('missing','wrong_type','wrong_name'):
        _,run,naming=ordered_design()
        columns=naming['contract_json']['columns']
        if kind=='missing':columns.pop()
        elif kind=='wrong_type':columns[-1]['vertica_type']='VARCHAR(32)'
        else:columns[-1]['english_name']='other_position'
        naming['checksum']=checksum(columns)
        assert editor_context(run,naming)['status']=='BLOCKED'
