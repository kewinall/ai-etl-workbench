from copy import deepcopy
from uuid import uuid4
import pytest
from test_etl_specification import design
from app.developer_contract import build_context,validate_proposal


def fixture():
    spec,run,naming=design()
    context=build_context(run,naming,{'approval_id':uuid4(),'binding_checksum':'c'*64},{'status':'READY_FOR_REVIEW'})
    captured={'context':context,'run':run,'naming':naming}
    return {'version':1,'context_checksum':context['context_checksum'],'summary':'Synthetic design',
        'evidence_ids':['requirement'],'specification':spec},captured


def test_supported_proposal_is_advice_not_execution():
    proposal,captured=fixture();result=validate_proposal(proposal,captured)
    assert result['status']=='VALIDATED_NOT_APPROVED' and not result['execution_authorized']


@pytest.mark.parametrize('change',['context','target','sql','reference','naming','write_mode'])
def test_model_cannot_change_bound_inputs_or_introduce_sql(change):
    proposal,captured=fixture();proposal=deepcopy(proposal)
    if change=='context':proposal['context_checksum']='0'*64
    if change=='target':proposal['specification']['target_table']='other'
    if change=='sql':proposal['specification']['sql']='DROP TABLE anything'
    if change=='reference':proposal['evidence_ids']=['invented']
    if change=='naming':proposal['specification']['naming']['checksum']='0'*64
    if change=='write_mode':proposal['specification']['write_mode']='REPLACE'
    with pytest.raises(ValueError):validate_proposal(proposal,captured)


def test_context_does_not_copy_source_paths_secrets_or_samples():
    _,run,naming=design();run['input_snapshot']['source_config'].update(path='PRIVATE_PATH',password='PRIVATE_PASSWORD',sample_rows=['PRIVATE_DATA'])
    context=build_context(run,naming,{'approval_id':uuid4(),'binding_checksum':'c'*64},{'status':'READY_FOR_REVIEW'})
    assert all(value not in str(context) for value in ('PRIVATE_PATH','PRIVATE_PASSWORD','PRIVATE_DATA'))
