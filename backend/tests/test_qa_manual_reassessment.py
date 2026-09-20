from unittest.mock import Mock
from uuid import uuid4
import pytest
import app.qa_journal as module
from test_qa_authorization_api import fixture


@pytest.mark.parametrize('status,version,count,review,allowed',[
    ('VALIDATED_NOT_APPROVED',2,1,'NEEDS_REVIEW',True),
    ('VALIDATED_NOT_APPROVED',module.PROMPT_VERSION,1,'NEEDS_REVIEW',False),
    ('VALIDATED_NOT_APPROVED',2,2,'NEEDS_REVIEW',False),
    ('QA_RESERVED',2,1,'NEEDS_REVIEW',False),
    ('QA_OUTCOME_UNKNOWN',2,1,'NEEDS_REVIEW',False),
    ('VALIDATED_NOT_APPROVED',2,1,'PASS',False),
    ('VALIDATED_NOT_APPROVED',2,1,'FAIL',False),
])
def test_only_one_changed_prompt_clarification_is_eligible(monkeypatch,status,version,count,review,allowed):
    monkeypatch.setattr(module,'public_record',Mock(return_value={'review':{'status':review}}))
    record=dict(status=status,prompt_version=version,input_json={'prompt_checksum':'a'*64})
    assert module.can_reassess(record,count) is allowed


def test_reassessment_requires_exact_previous_review_and_separate_consent(monkeypatch):
    api,url,offer,journal=fixture(monkeypatch)
    previous=str(uuid4());offer['reassess_invocation_id']=previous
    body={key:offer[key] for key in ('model','context_checksum','prompt_checksum','schema_checksum','comparison_id')}
    body.update(confirmed=True,reassess_invocation_id=str(uuid4()))
    assert api.post(url,json=body).status_code==409
    journal.reserve.assert_not_called()
    body['reassess_invocation_id']=previous;body['confirmed']=False
    assert api.post(url,json=body).status_code==409
    journal.reserve.assert_not_called()
    body['confirmed']=True
    assert api.post(url,json=body).status_code==200
    assert str(journal.reserve.call_args.kwargs['reassess_invocation_id'])==previous
    assert journal.reserve.call_args.kwargs['expected_prompt_checksum']==offer['prompt_checksum']


def test_enrichment_reassessment_is_bounded_and_cannot_change_old_evidence(monkeypatch):
    from copy import deepcopy
    from xml.etree import ElementTree as ET
    from test_qa_execution_details import fixture as details_fixture
    from test_qa_semantics import sample
    from app.qa_execution_details import execution_details
    from app.qa_contract import build_qa_context
    old,_=sample()
    spec,run,compiled,auth=details_fixture(monkeypatch)
    checks=deepcopy(old['evidence'])
    for check in checks:
        if check['id']=='static_validation':check['checksum']=compiled['hpl_checksum']
    semantics=dict(requirement=run['input_snapshot']['requirement_text'],
        conditions=run['input_snapshot']['target_config']['requirements_v1'],specification=spec,
        nodes=[dict(id=n.findtext('name'),component=n.findtext('type')) for n in ET.fromstring(compiled['hpl']).findall('transform')])
    previous=build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    semantics['execution_details']=execution_details(run,compiled,auth)
    current=build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    record=dict(status='VALIDATED_NOT_APPROVED',prompt_version=3,
        input_json={'prompt_checksum':'a'*64,'context':previous})
    monkeypatch.setattr(module,'public_record',Mock(return_value={'review':{'status':'NEEDS_REVIEW'}}))
    assert module.can_reassess(record,2,current)
    assert not module.can_reassess(record,3,current)
    assert not module.can_reassess(record,2,previous)
    changed=deepcopy(current);changed['semantics']['requirement']='Different requirement'
    assert not module.can_reassess(record,2,changed)
    changed=deepcopy(current);changed['evidence'][0]['checksum']='f'*64
    assert not module.can_reassess(record,2,changed)
    changed=deepcopy(current);changed['semantics']['execution_details']['hpl_checksum']='f'*64
    assert not module.can_reassess(record,2,changed)
