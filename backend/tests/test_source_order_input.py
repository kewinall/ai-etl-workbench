from copy import deepcopy
import pytest
from app.control_worker import check_requirements
from app.source_order_input import order_evidence, order_issues
from app.run_api import ReviseRun, public_run
from test_source_order_compilation import ordered_design


def test_order_input_is_explicit_safe_and_legacy_absence_is_preserved():
    _,run,_=ordered_design()
    snapshot=run['input_snapshot']
    assert not order_issues(snapshot)
    assert check_requirements(snapshot)['status']=='CHECKED'
    public=public_run(run)
    assert public['input_summary']['source_order_v1']==snapshot['target_config']['source_order_v1']
    assert '$source_order.source.0' in public['input_summary']['transformation_source_refs']
    old=deepcopy(snapshot);old['target_config'].pop('source_order_v1')
    assert order_evidence(old) is None and order_issues(old)==[]


@pytest.mark.parametrize('change',['null','multiple','database','missing_intent','missing_ordinal','filter','bad_name'])
def test_incomplete_or_unsupported_order_input_stops_at_gate(change):
    _,run,_=ordered_design();snapshot=run['input_snapshot'];target=snapshot['target_config']
    if change=='null': target['source_order_v1']=None
    elif change=='multiple': snapshot['source_config']['sources']*=2
    elif change=='database': snapshot['source_config']['sources'][0]['type']='TABLE'
    elif change=='missing_intent': target.pop('transformation_contract_v1')
    elif change=='missing_ordinal': target['transformation_contract_v1']['output_columns'].pop()
    elif change=='filter': target['transformation_contract_v1']['filters']=[dict(column='source.0.類別',operator='IS_NULL',constant=None)]
    elif change=='bad_name': target['source_order_v1']['ordinal_column']='x;drop table y'
    assert order_issues(snapshot)
    assert check_requirements(snapshot)['status']=='NEEDS_INPUT'


def test_revision_schema_rejects_arbitrary_or_coerced_order_input():
    _,run,_=ordered_design()
    base=dict(request_key='order-revision-01',input_checksum='a'*64,requirement_text='依來源順序',target_schema='ai_sample',target_table='ordered',
              source_order_v1=run['input_snapshot']['target_config']['source_order_v1'])
    assert ReviseRun.model_validate(base).source_order_v1.ordinal_column=='source_position'
    for mutation in (dict(version=True),dict(direction='DESC'),dict(sql='ORDER BY 1')):
        with pytest.raises(ValueError):ReviseRun.model_validate({**base,'source_order_v1':{**base['source_order_v1'],**mutation}})
