from copy import deepcopy
import json
import pytest
from test_etl_specification import design
from app.sdm_specification import build_sdm_candidate


def test_output_only_order_types_and_aggregate_lineage():
    spec,run,naming=design();before=deepcopy((spec,run,naming))
    result=build_sdm_candidate(spec,run,naming)
    assert result==build_sdm_candidate(spec,run,naming)
    assert before==(spec,run,naming)
    mappings=result['document']['mappings']
    assert [m['target_column'] for m in mappings]==['category','total_amount','row_count']
    assert [m['operation'] for m in mappings]==['GROUP_KEY','SUM','COUNT_ROWS']
    assert mappings[1]['source_columns']==[{'source_ref':'source.0','original_name':'金額','stream_name':'amount','data_type':'NUMERIC(12,2)'}]
    assert mappings[2]['source_columns']==[]
    assert [m['target_type'] for m in mappings]==['VARCHAR(32)','NUMERIC(18,2)','BIGINT']
    assert result['document']['filters']==spec['filters']
    assert result['qa_passed'] is False and result['release_ready'] is False


def test_direct_mapping_and_no_host_paths_or_naming_reason():
    spec,run,naming=design();spec.update(aggregation=None,output_columns=['amount','category'])
    naming['contract_json']['columns']=naming['contract_json']['columns'][:2]
    naming['contract_json']['columns'][0]['reason']='private host path'
    # Recompute the confirmed contract fingerprint after changing this fixture.
    from app.platform_harness import checksum
    naming['checksum']=checksum(naming['contract_json']['columns']);spec['naming']['checksum']=naming['checksum']
    result=build_sdm_candidate(spec,run,naming)
    assert [m['operation'] for m in result['document']['mappings']]==['DIRECT','DIRECT']
    assert 'private host path' not in json.dumps(result)


@pytest.mark.parametrize('change',[{'output_columns':['not_present']},{'joins':[]},{'write_mode':'TRUNCATE'}])
def test_invalid_spec_cannot_generate_candidate(change):
    spec,run,naming=design();spec.update(change)
    with pytest.raises(ValueError,match='SDM_VALID_SPECIFICATION_REQUIRED'):build_sdm_candidate(spec,run,naming)


def test_draft_naming_rejected():
    spec,run,naming=design();naming['status']='DRAFT'
    with pytest.raises(ValueError,match='SDM_VALID_SPECIFICATION_REQUIRED'):build_sdm_candidate(spec,run,naming)
