import pytest
from app.settings_contract import validate_setting


@pytest.mark.parametrize('key,value', [
    ('data_governance_naming_rules', {'sample_schema': 'public'}),
    ('data_governance_naming_rules', {'english_identifier': 'arbitrary'}),
    ('validation_release_policy', {'require_naming_contract': False}),
    ('validation_release_policy', {'require_naming_contract': 1}),
    ('validation_release_policy', {'sample_rows': 11}),
    ('validation_release_policy', {'sample_rows': 0}),
    ('validation_release_policy', {'sample_rows': '10'}),
    ('validation_release_policy', {'sample_rows': True}),
    ('validation_policy', {'post_write_count': False}),
    ('validation_policy', {'max_rows': 11}),
    ('security_secret_vault', {'encryption': 'plaintext'}),
    ('security_secret_vault', {'key_source': 'database'}),
    ('security_secret_vault', {'password': 'must-not-leak'}),
])
def test_invalid_policy_rejected_without_values(key, value):
    with pytest.raises(ValueError) as error:
        validate_setting(key, value)
    assert 'must-not-leak' not in str(error.value)


def test_defaults_and_supported_policy():
    assert validate_setting('data_governance_naming_rules', {}) == {
        'sample_schema': 'ai_sample', 'english_identifier': 'snake_case'}
    assert validate_setting('validation_release_policy', {'sample_rows': 5}) == {
        'sample_rows': 5, 'require_naming_contract': True}


def test_both_http_routes_use_repository_validation_before_database():
    from app.repository import PostgresRepository
    repo = PostgresRepository('not-a-real-database')
    # Invalid policy fails before any connection is attempted.
    with pytest.raises(ValueError, match='必要驗證'):
        repo.update_setting('validation_release_policy', {'require_naming_contract': False})


def test_platform_connection_cannot_be_changed_and_secrets_cannot_be_stored():
    from app.repository import PostgresRepository
    repo = PostgresRepository('not-a-real-database')
    repo.setting = lambda *args: {'platform': 'deployment-db'}
    with pytest.raises(ValueError, match='部署設定'):
        repo.update_setting('data_connections_targets', {'platform': 'other-db'})
    with pytest.raises(ValueError, match='保管庫'):
        repo.update_setting('data_connections_targets', {'platform': 'deployment-db', 'etl_qa': {'password': 'do-not-store'}})
