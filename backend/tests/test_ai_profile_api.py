from copy import deepcopy
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.ai_profile_api import create_ai_profile_router
from app.model_gateway import GatewayError


class Repo:
    def __init__(self):
        self.profile = {'profile_id': 'test-ai', 'display_name': 'Test', 'provider_type': 'LITELLM_BEDROCK', 'enabled': True, 'region': 'us-east-1', 'model_routes': {}, 'secret_ref': 'internal-ref'}
    def ai_profile(self, key): return deepcopy(self.profile) if key == 'test-ai' else None
    def ai_profiles(self): return []
    def upsert_ai_profile(self, data):
        self.profile.update(data)
        return self.profile
    def read_secret(self, _): return 'test-secret'


def client(repo=None, complete=None):
    app = FastAPI()
    kwargs = {'complete': complete} if complete else {}
    app.include_router(create_ai_profile_router(repo or Repo(), **kwargs))
    return TestClient(app)


def payload(**extra):
    return {'display_name': 'Updated', 'model_routes': {'qa_review': 'bedrock/test'}, **extra}


def test_profile_update_sanitizes_response_and_preserves_secret():
    repo = Repo()
    response = client(repo).put('/api/settings/ai-profiles/test-ai', json=payload())
    assert response.status_code == 200
    assert response.json()['secret_configured'] is True
    assert 'internal-ref' not in response.text
    assert 'secret_ref' not in response.json()
    assert repo.profile['model_routes']['qa_review'] == 'bedrock/test'

def test_profile_conflict_returns_409_without_internal_details():
    from app.ai_profile_api import ProfileConflict
    class ConflictRepo(Repo):
        def upsert_ai_profile(self,data):
            assert data['_expected_version']=='stale'
            raise ProfileConflict('AI Profile 已被更新')
    response=client(ConflictRepo()).put('/api/settings/ai-profiles/test-ai',json=payload(),headers={'X-Settings-Version':'stale'})
    assert response.status_code==409
    assert response.json()['detail']=='AI Profile 已被更新'

def test_secret_conflict_is_409_and_does_not_echo_secret(monkeypatch):
    from app.ai_profile_api import ProfileConflict
    monkeypatch.setattr('app.ai_profile_api.encrypt_secret',lambda _: (b'cipher',b'nonce'))
    class ConflictRepo(Repo):
        def update_ai_profile_secret(self,profile_id,cipher,nonce,expected_version=None):
            assert expected_version=='stale'
            raise ProfileConflict('AI Profile 已被更新，機密未儲存')
    response=client(ConflictRepo()).post('/api/settings/ai-profiles/test-ai/secret',json={'secret_value':'synthetic-private'},headers={'X-Settings-Version':'stale'})
    assert response.status_code==409
    assert 'synthetic-private' not in response.text


@pytest.mark.parametrize('extra', [
    {'provider_type': 'unsupported'}, {'display_name': ''},
    {'model_routes': {'unknown': 'model'}},
    {'endpoint': 'http://user:password@host'},
    {'endpoint': 'http://host:wrong-port'},
    {'secret_ref': 'supplied-reference'},
])
def test_invalid_profile_rejected(extra):
    assert client().put('/api/settings/ai-profiles/test-ai', json=payload(**extra)).status_code == 422


def test_health_requires_actual_gateway_response_and_does_not_return_secret():
    calls = []
    def fake(profile, role, messages, secret):
        calls.append((role, secret))
        return {'ok': True}, {'model': 'bedrock/test', 'duration_ms': 1}
    response = client(complete=fake).post('/api/settings/ai-profiles/test-ai/test?role=qa_review')
    assert response.json()['status'] == 'CONNECTED'
    assert calls == [('qa_review', 'test-secret')]
    assert 'test-secret' not in response.text


def test_failed_health_never_reports_configured_as_connected():
    def fake(*args, **kwargs): raise GatewayError('MODEL_ROUTE_MISSING')
    response = client(complete=fake).post('/api/settings/ai-profiles/test-ai/test')
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'MODEL_ROUTE_MISSING'


def test_unknown_profile_never_calls_provider():
    def forbidden(*args, **kwargs): raise AssertionError('must not call')
    assert client(complete=forbidden).post('/api/settings/ai-profiles/missing/test').status_code == 404


def test_validation_error_never_echoes_input_credentials():
    response = client().put('/api/settings/ai-profiles/test-ai', json=payload(endpoint='http://user:private-secret@host'))
    assert response.status_code == 422
    assert 'private-secret' not in response.text
