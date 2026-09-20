from pathlib import Path
import pytest
from app.bootstrap import configure_environment
from app.migrations import migration_body, migration_fingerprints


def test_database_password_is_url_encoded(tmp_path, monkeypatch):
    password = tmp_path / 'password'
    password.write_text('a@b:/?#%')
    monkeypatch.setenv('DATABASE_PASSWORD_FILE', str(password))
    monkeypatch.setenv('DATABASE_HOST', 'postgres')
    monkeypatch.setenv('DATABASE_USER', 'workbench')
    monkeypatch.setenv('DATABASE_NAME', 'workbench')
    monkeypatch.delenv('PLATFORM_SETTINGS_ENCRYPTION_KEY_FILE', raising=False)
    monkeypatch.setenv('DATABASE_URL', 'unused')
    configure_environment()
    import os
    assert os.environ['DATABASE_URL'] == 'postgresql://workbench:a%40b%3A%2F%3F%23%25@postgres:5432/workbench'


def test_empty_password_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / 'empty'
    path.write_text('')
    monkeypatch.setenv('DATABASE_PASSWORD_FILE', str(path))
    with pytest.raises(ValueError, match='empty'):
        configure_environment()


def test_migration_transaction_boundaries():
    assert migration_body('BEGIN;\nSELECT 1;\nCOMMIT;').strip() == 'SELECT 1;'
    with pytest.raises(ValueError, match='Embedded'):
        migration_body('SELECT 1;\nCOMMIT;\nSELECT 2;')


def test_all_legacy_scripts_can_be_wrapped():
    directory = Path(__file__).resolve().parents[2] / 'database' / 'migrations'
    paths = list(directory.glob('*.sql'))
    assert len(paths) >= 20
    for path in paths:
        migration_body(path.read_text(encoding='utf-8-sig'))


def test_migration_hash_is_checkout_portable_but_detects_sql_changes():
    lf = b'BEGIN;\nSELECT 1;\nCOMMIT;\n'
    crlf = lf.replace(b'\n', b'\r\n')
    first, variants = migration_fingerprints(lf)
    second, _ = migration_fingerprints(crlf)
    assert first == second
    import hashlib
    assert hashlib.sha256(crlf).hexdigest() in variants
    assert hashlib.sha256(lf.replace(b'SELECT 1', b'SELECT 2')).hexdigest() not in variants
