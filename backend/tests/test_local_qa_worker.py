from unittest.mock import Mock
import pytest
from app.local_qa_worker import run_once
from app.local_qa_bridge import handle,public_error
from test_qa_copilot import native_values


def test_consent_required_before_transport():
    transport=Mock()
    with pytest.raises(ValueError,match='CONSENT_REQUIRED'):
        run_once('t','r','c','h',transport=transport)
    transport.assert_not_called()


def test_bridge_error_allowlist_never_exposes_exception_details():
    assert public_error(ValueError('QA_DISPATCH_DISABLED'))=='QA_DISPATCH_DISABLED'
    assert public_error(ValueError('secret database connection string'))=='LOCAL_QA_REQUEST_FAILED'
    assert public_error(RuntimeError('QA_DISPATCH_DISABLED'))=='LOCAL_QA_REQUEST_FAILED'


@pytest.mark.parametrize('failure',[False,True])
def test_worker_claim_check_save_once(failure):
    run,profile,context,_,native=native_values();calls=[]
    def transport(data):
        calls.append(data['action'])
        if data['action']=='claim':return dict(status='DISPATCH_RESERVED',invocation_id='i',claim_token='t',
            run=run,profile=profile,context=context)
        if data['action']=='check':return {'status':'CLAIM_ACTIVE'}
        return {'status':'VALIDATED_NOT_APPROVED'}
    completion=Mock(side_effect=RuntimeError('private')) if failure else Mock(side_effect=native)
    result=run_once('t','r','c','h',authorize_model_call=True,transport=transport,completion=completion)
    assert completion.call_count==1
    assert calls.count('claim')==1
    assert calls[-1]==('uncertain' if failure else 'finish')
    assert result['status']==('QA_OUTCOME_UNKNOWN' if failure else 'VALIDATED_NOT_APPROVED')


def test_bridge_disabled_before_database(monkeypatch):
    monkeypatch.delenv('WORKBENCH_QA_DISPATCH_ENABLED',raising=False)
    with pytest.raises(ValueError,match='QA_DISPATCH_DISABLED'):
        handle(None,{'action':'claim','task_id':'t','run_id':'00000000-0000-0000-0000-000000000001','authorize_model_call':True})


def test_website_mode_only_claims_existing_authorization():
    transport=Mock(return_value={'status':'IDLE'});completion=Mock()
    assert run_once('t','r',website_authorized=True,transport=transport,completion=completion)['status']=='IDLE'
    assert transport.call_args.args[0]['action']=='claim_authorized'
    completion.assert_not_called()
