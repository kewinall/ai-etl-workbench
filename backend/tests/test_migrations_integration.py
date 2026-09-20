"""Opt-in tests against the isolated Compose DB. Never use the legacy .env."""
import os
from pathlib import Path
import shutil

import psycopg
import pytest
from app.migrations import migrate

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated Compose DB required')


@pytest.fixture
def migration_context():
    assert os.getenv('DATABASE_HOST') == 'postgres'
    assert os.getenv('DATABASE_NAME') == 'workbench'
    url = os.environ['DATABASE_URL']
    with psycopg.connect(url) as conn:
        assert conn.execute('SELECT current_database()').fetchone()[0] == 'workbench'
        assert conn.execute('SELECT count(*) FROM platform.schema_migration').fetchone()[0] >= 20
    return url, Path(__file__).resolve().parents[2] / 'database' / 'migrations'


def test_repeated_migration_preserves_settings(migration_context):
    url, directory = migration_context
    def snapshot():
        with psycopg.connect(url) as conn:
            return conn.execute('SELECT setting_key, setting_value, updated_at FROM platform.system_setting ORDER BY setting_key').fetchall()
    before = snapshot()
    assert migrate(url, directory) == []
    assert snapshot() == before


def test_changed_sql_is_blocked(migration_context, tmp_path):
    url, directory = migration_context
    copied = tmp_path / 'migrations'
    shutil.copytree(directory, copied)
    first = sorted(copied.glob('*.sql'))[0]
    first.write_text(first.read_text()+'\n-- unauthorized modification\n')
    with pytest.raises(ValueError, match='checksum mismatch'):
        migrate(url, copied)


def test_missing_applied_file_is_blocked(migration_context, tmp_path):
    url, directory = migration_context
    copied = tmp_path / 'migrations'
    shutil.copytree(directory, copied)
    sorted(copied.glob('*.sql'))[-1].unlink()
    with pytest.raises(ValueError, match='missing'):
        migrate(url, copied)
