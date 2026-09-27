from copy import deepcopy
from uuid import uuid4
import pytest
from app.sa_contract import build_sa_context,validate_sa_review,sa_output_schema,digest
from app.developer_contract import build_context,validate_proposal
from app.developer_gateway import developer_material
from test_source_order_compilation import ordered_design


def fixture():
    spec,run,naming=ordered_design()
    context=build_context(run,naming,dict(approval_id=uuid4(),binding_checksum='c'*64),{'status':'READY_FOR_REVIEW'})
    proposal=dict(version=3,context_checksum=context['context_checksum'],summary='Synthetic ordered design',
        evidence_ids=['requirement','transformation.conditions','source_order.conditions'],specification=spec)
    return proposal,dict(context=context,run=run,naming=naming)


def test_sa_order_contract_is_citable_required_and_secret_free():
    _,captured=fixture();run=captured['run']
    run['input_snapshot']['source_config'].update(path='PRIVATE_PATH',password='PRIVATE_PASSWORD')
    context=build_sa_context(run)
    assert context['version']==4
    assert 'PRIVATE_' not in str(context)
    assert 'source_order.conditions' in sa_output_schema(context)['properties']['evidence_ids']['items']['enum']
    review={k:context[k] for k in ('run_id','input_checksum','context_checksum')}
    review.update(version=1,status='READY_FOR_REVIEW',summary='Reviewed',issues=[],evidence_ids=['requirement'])
    with pytest.raises(ValueError,match='SA_SOURCE_ORDER_EVIDENCE_REQUIRED'):validate_sa_review(review,context)
    review['evidence_ids'].append('source_order.conditions')
    assert validate_sa_review(review,context)['status']=='READY_FOR_REVIEW'


def test_developer_receives_v3_schema_and_versioned_prompt_without_execution_permission():
    proposal,captured=fixture()
    material=developer_material(captured['context'])
    assert captured['context']['version']==3 and material['prompt_version']==6
    assert 'EtlSpecificationV3' in material['prompt']
    assert '$source_order.source.0' in material['prompt']
    assert material['schema']['properties']['version']['const']==3
    result=validate_proposal(proposal,captured)
    assert result['status']=='VALIDATED_NOT_APPROVED'
    assert result['execution_authorized'] is result['release_ready'] is False


@pytest.mark.parametrize('change',['citation','spec_version','proposal_version','ordinal','projection','context_version'])
def test_developer_cannot_drop_or_reinterpret_order(change):
    proposal,captured=fixture()
    if change=='citation':proposal['evidence_ids'].remove('source_order.conditions')
    elif change=='spec_version':proposal['specification']['version']=1
    elif change=='proposal_version':proposal['version']=1
    elif change=='ordinal':proposal['specification']['source_order']['ordinal_column']='amount'
    elif change=='projection':proposal['specification']['output_columns'].remove('source_position')
    else:
        captured['context']['version']=1
        captured['context']['context_checksum']=digest({k:v for k,v in captured['context'].items() if k!='context_checksum'})
    with pytest.raises(ValueError):validate_proposal(proposal,captured)


def test_legacy_context_and_prompt_remain_legacy():
    from test_developer_contract import fixture as legacy
    proposal,captured=legacy()
    before=deepcopy(captured)
    assert developer_material(captured['context'])['prompt_version']==2
    assert validate_proposal(proposal,captured)['status']=='VALIDATED_NOT_APPROVED'
    assert before==captured
