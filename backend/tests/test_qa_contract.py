from copy import deepcopy
from uuid import uuid4
import pytest
from app.qa_contract import REQUIRED_CHECKS,build_qa_context,validate_qa_review


def sample():
    checks=[{'id':name,'status':'PASS','checksum':'a'*64,'summary':'deterministic synthetic check'} for name in REQUIRED_CHECKS]
    context=build_qa_context(uuid4(),'b'*64,checks)
    review={key:context[key] for key in ('run_id','specification_checksum','context_checksum')}
    review.update(version=1,status='PASS',summary='Evidence reviewed',evidence_ids=list(REQUIRED_CHECKS),issues=[])
    return checks,context,review


def test_pass_is_only_advice_and_context_is_immutable():
    _,context,review=sample();before=deepcopy(context)
    accepted=validate_qa_review(review,context)
    assert accepted['advisory_only'] and not accepted['qa_approved'] and not accepted['release_ready']
    assert context==before


@pytest.mark.parametrize('status',['FAIL','MISSING'])
def test_model_cannot_override_program_failure_or_missing_evidence(status):
    checks,context,review=sample();checks[2]['status']=status
    context=build_qa_context(context['run_id'],context['specification_checksum'],checks)
    review['context_checksum']=context['context_checksum']
    with pytest.raises(ValueError,match='QA_'):
        validate_qa_review(review,context)
    review.update(status='FAIL' if status=='FAIL' else 'NEEDS_REVIEW',issues=[{'message':'Blocked','evidence_ids':['hop_execution']}])
    assert validate_qa_review(review,context)['status']==review['status']


@pytest.mark.parametrize('mutation',['run','context','citation','issue','missing_citation'])
def test_rejects_wrong_versions_unknown_evidence_and_unsupported_pass(mutation):
    _,context,review=sample()
    if mutation=='run':review['run_id']=str(uuid4())
    elif mutation=='context':context['evidence'][0]['summary']='modified'
    elif mutation=='citation':review['evidence_ids'].append('invented-node')
    elif mutation=='issue':review['issues']=[{'message':'Unresolved','evidence_ids':['specification']}]
    else:review['evidence_ids'].pop()
    with pytest.raises(ValueError,match='QA_'):validate_qa_review(review,context)


def test_duplicate_checks_are_not_complete_evidence():
    checks,context,_=sample();checks[-1]=checks[0]
    with pytest.raises(ValueError,match='QA_REQUIRED_CHECKS'):
        build_qa_context(context['run_id'],context['specification_checksum'],checks)
