from copy import deepcopy
import pytest
from app.release_portability import validate_portability
from app.source_binding import execution_sources
from app.sa_contract import digest
from test_formal_release_bundle import proof_fixture


ORDER=dict(version=1,source_ref='source.0',ordinal_column='source_position',direction='ASC',
           semantics='LOGICAL_CSV_RECORD_POSITION')


def fixture():
    candidate,row=proof_fixture()
    row['evidence'].update(version=3,comparison='EXACT_SOURCE_SEQUENCE',source_order=deepcopy(ORDER),
                           result_query_checksum='1'*64,position_mismatch_count=0)
    row['checksum']=digest(row['evidence'])
    return candidate,row


def check(candidate,row,**changes):
    options=dict(expected_checksum='f'*64,expected_count=1,source_order=ORDER,result_query_checksum='1'*64)
    return validate_portability(row,candidate,'d'*64,**{**options,**changes})


def test_v3_single_source_does_not_mean_three_sources():
    config={'sources':[dict(type='CSV',upload_id='synthetic',checksum='a'*64)]}
    assert execution_sources(config,3)==execution_sources(config,1)=={'source_checksum':'a'*64}
    for count in (0,2,3):
        with pytest.raises(ValueError):execution_sources({'sources':config['sources']*count},3)


def test_exact_order_proof_requires_pinned_query_and_retains_contract():
    candidate,row=fixture()
    assert check(candidate,row)['source_order']==ORDER
    for changes in (dict(source_order=None),dict(result_query_checksum=None),dict(result_query_checksum='2'*64),
                    dict(source_order={**ORDER,'ordinal_column':'different'}),dict(source_checksums={'source.0':'d'*64})):
        with pytest.raises(ValueError):check(candidate,row,**changes)


@pytest.mark.parametrize('change',[
    dict(version=1),dict(comparison='EXACT_MULTISET'),dict(position_mismatch_count=1),
    dict(position_mismatch_count=False),dict(result_actual_checksum='0'*64),
    dict(actual_count=0),dict(result_query_checksum='0'*64),
])
def test_edited_proof_cannot_release_even_with_recalculated_checksum(change):
    candidate,row=fixture()
    row['evidence'].update(change);row['checksum']=digest(row['evidence'])
    with pytest.raises(ValueError):check(candidate,row)


def test_legacy_pass_cannot_substitute_for_order_proof():
    candidate,row=proof_fixture()
    with pytest.raises(ValueError):check(candidate,row)
