from copy import deepcopy

import pytest

from app.sdm_specification import build_sdm_candidate
from app.sdm_xlsx_semantics import expected_sdm_cells
from test_source_order_compilation import ordered_design
from test_etl_specification import design


def test_ordered_sdm_distinguishes_generated_ordinal_from_physical_source():
    args=ordered_design();before=deepcopy(args)
    candidate=build_sdm_candidate(*args)
    document=candidate['document']
    assert document['version']==3
    assert document['source_order']==args[0]['source_order']
    assert document['mappings'][-1]==dict(position=3,target_column='source_position',
        target_type='BIGINT',operation='SOURCE_ORDINAL',source_columns=[],metric_id=None)
    assert [m['operation'] for m in document['mappings'][:2]]==['DIRECT','DIRECT']
    assert document['mappings'][0]['source_columns'][0]['original_name']=='類別'
    assert candidate==build_sdm_candidate(*args)
    assert args==before
    assert not candidate['qa_passed'] and not candidate['release_ready']


def test_ordered_sdm_expected_cells_explain_generation_and_query_order():
    mapping,rules=expected_sdm_cells(*ordered_design())
    assert mapping['D8']=='系統產生來源序號'
    assert 'E8' not in mapping
    assert mapping['F8']=='依 CSV 邏輯資料列位置從 1 產生，非 CSV 原始欄位'
    values=list(rules.values())
    assert 'source_position（BIGINT，不可為 NULL）' in values
    assert any('明確 ORDER BY' in str(v) for v in values)
    assert any('EXACT_SOURCE_SEQUENCE' in str(v) for v in values)
    assert any('標頭不計入' in str(v) for v in values)


def test_ordered_sdm_cannot_hide_or_relabel_order_contract():
    spec,run,naming=ordered_design()
    spec['source_order']['ordinal_column']='record_id'
    with pytest.raises(ValueError,match='SDM_VALID_SPECIFICATION_REQUIRED'):
        build_sdm_candidate(spec,run,naming)


def test_legacy_sdm_does_not_acquire_order_contract():
    document=build_sdm_candidate(*design())['document']
    assert document['version']==1
    assert 'source_order' not in document
    assert 'SOURCE_ORDINAL' not in [m['operation'] for m in document['mappings']]
