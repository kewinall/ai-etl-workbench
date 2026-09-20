from copy import deepcopy
import pytest
from app.execution_settings import resolve_settings


class Repo:
    def __init__(self):
        self.project = {'default_ai_profile': 'project-ai', 'default_connection': 'qa'}
        self.profile = {'enabled': True, 'provider_type': 'LITELLM_BEDROCK', 'region': 'us-east-1',
                        'secret_ref': 'not-public', 'model_routes': {role: 'bedrock/test' for role in ('requirement_gate', 'etl_specification', 'qa_review')}}
        self.connections = {'etl_qa': {'connection_id': 'qa', 'host': 'test-host', 'port': '5433', 'database': 'test-db', 'user': 'test-user', 'password': 'must-not-copy'}}
    def get_project(self, _): return self.project
    def setting(self, key, default):
        return {'ai_provider_model_strategy': {'default_profile': 'platform-ai'}, 'data_connections_targets': self.connections}.get(key, default)
    def ai_profile(self, key):
        return deepcopy(self.profile) if key in ('task-ai', 'project-ai', 'platform-ai') else None


def test_tls_setting_is_version_bound_without_default_or_secret():
    repo = Repo()
    missing = resolve_settings(repo, {'project_id': 'p'})['snapshot']
    assert missing['connection']['tlsmode'] is None
    repo.connections['etl_qa']['tlsmode'] = 'disable'
    plain = resolve_settings(repo, {'project_id': 'p'})['snapshot']
    repo.connections['etl_qa']['tlsmode'] = 'verify-full'
    verified = resolve_settings(repo, {'project_id': 'p'})['snapshot']
    assert len({missing['checksum'], plain['checksum'], verified['checksum']}) == 3
    assert verified['connection']['tlsmode'] == 'verify-full'
    assert 'must-not-copy' not in str(verified)


def test_precedence_and_no_secret_in_snapshot():
    repo = Repo()
    result = resolve_settings(repo, {'project_id': 'p'}, {'ai_profile_id': 'task-ai'})
    assert result['status'] == 'CONFIGURED_NOT_TESTED'
    assert result['snapshot']['origins'] == {'ai_profile': 'TASK', 'connection': 'PROJECT'}
    assert 'must-not-copy' not in str(result)
    assert 'not-public' not in str(result)
    assert resolve_settings(repo, {'project_id': 'p'})['snapshot']['ai_profile_id'] == 'project-ai'
    repo.project = {}
    assert resolve_settings(repo, {'project_id': 'p'})['status'] == 'BLOCKED'


def test_platform_fallback_and_invalid_explicit_selection():
    repo = Repo()
    repo.project = {'project_id': 'p'}
    assert resolve_settings(repo, {'project_id': 'p'})['snapshot']['ai_profile_id'] == 'platform-ai'
    result = resolve_settings(repo, {'project_id': 'p'}, {'ai_profile_id': ''})
    assert result['status'] == 'BLOCKED'
    assert result['snapshot'] is None


def test_unconfigured_legacy_reference_never_uses_environment(monkeypatch):
    monkeypatch.setenv('VERTICA_HOST', 'developer-db')
    repo = Repo()
    repo.connections = {'etl_qa': 'qa'}
    result = resolve_settings(repo, {'project_id': 'p'})
    assert result['issues'] == [{'code': 'CONNECTION_NOT_CONFIGURED'}]
    assert result['snapshot'] is None


def test_missing_qa_route_blocks_and_checksum_tracks_change():
    repo = Repo()
    first = resolve_settings(repo, {'project_id': 'p'})['snapshot']['checksum']
    repo.profile['region'] = 'us-west-2'
    assert resolve_settings(repo, {'project_id': 'p'})['snapshot']['checksum'] != first
    del repo.profile['model_routes']['qa_review']
    assert {'code': 'MODEL_ROUTE_MISSING', 'role': 'qa_review'} in resolve_settings(repo, {'project_id': 'p'})['issues']


def test_platform_database_cannot_be_etl_target():
    repo = Repo()
    repo.connections['platform'] = {**repo.connections['etl_qa'], 'connection_id': 'platform'}
    result = resolve_settings(repo, {'project_id': 'p'}, {'connection_id': 'platform'})
    assert result['snapshot'] is None
    assert {'code': 'ETL_CONNECTION_NOT_ALLOWED'} in result['issues']


@pytest.mark.parametrize('group', ['ai_provider_model_strategy', 'data_connections_targets'])
@pytest.mark.parametrize('bad_value', [None, [], '', 'secret-bearing-invalid-setting', 42, False])
def test_malformed_settings_block_without_exposing_values(group, bad_value):
    repo = Repo()
    original = repo.setting
    repo.setting = lambda key, default: bad_value if key == group else original(key, default)
    result = resolve_settings(repo, {'project_id': 'p'})
    assert result == {'status': 'BLOCKED', 'issues': [{'code': 'SETTINGS_GROUP_INVALID', 'group': group}], 'snapshot': None}


@pytest.mark.parametrize('override', [[], '', False, 1])
def test_malformed_task_settings_do_not_fall_back(override):
    assert resolve_settings(Repo(), {'project_id': 'p'}, override) == {
        'status': 'BLOCKED', 'issues': [{'code': 'TASK_SETTINGS_INVALID'}], 'snapshot': None}


@pytest.mark.parametrize('value', ['', None, 'missing-connection'])
def test_explicit_invalid_connection_does_not_use_project_default(value):
    result = resolve_settings(Repo(), {'project_id': 'p'}, {'connection_id': value})
    assert result['status'] == 'BLOCKED' and result['snapshot'] is None
    assert {'code': 'CONNECTION_NOT_CONFIGURED'} in result['issues']
