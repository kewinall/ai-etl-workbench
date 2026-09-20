from unittest.mock import Mock
import pytest
from app.local_developer_worker import run_once
from app.local_developer_bridge import handle, public_error


def test_disabled_bridge_never_touches_database(monkeypatch):
    monkeypatch.delenv('WORKBENCH_DEVELOPER_DISPATCH_ENABLED', raising=False)
    with pytest.raises(ValueError, match='DISABLED'):
        handle(None, {'task_id':'t', 'run_id':'00000000-0000-0000-0000-000000000001', 'action':'claim'})


def test_idle_does_not_invoke_model():
    completion = Mock()
    assert run_once('t','r', transport=Mock(return_value={'status':'IDLE'}), completion=completion)['status'] == 'IDLE'
    completion.assert_not_called()


@pytest.mark.parametrize('failure', [False, True])
def test_one_call_no_retry_and_save_or_unknown(failure):
    actions = []
    def transport(data):
        actions.append(data['action'])
        if data['action'] == 'claim':
            return dict(status='DISPATCH_RESERVED', invocation_id='i', claim_token='token',
                        model='copilot/test', prompt_version=1, payload={})
        if data['action'] == 'check': return {'status':'CLAIM_ACTIVE'}
        if data['action'] == 'finish':
            assert data['trace']['prompt_version'] == 1
            return {'status':'VALIDATED_NOT_APPROVED'}
        return {'status':'DEVELOPER_OUTCOME_UNKNOWN'}
    completion = Mock(side_effect=RuntimeError('private')) if failure else Mock(return_value=({'version':1}, {}))
    result = run_once('t','r', transport=transport, completion=completion)
    assert completion.call_count == 1 and actions.count('claim') == 1
    assert actions[-1] == ('uncertain' if failure else 'finish')
    assert result['status'] == ('DEVELOPER_OUTCOME_UNKNOWN' if failure else 'VALIDATED_NOT_APPROVED')


def test_error_details_masked():
    assert public_error(ValueError('private database URI')) == 'LOCAL_DEVELOPER_REQUEST_FAILED'
    assert public_error(ValueError('DEVELOPER_DISPATCH_DISABLED')) == 'DEVELOPER_DISPATCH_DISABLED'
