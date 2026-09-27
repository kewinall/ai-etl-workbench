from hashlib import sha256
import pytest
from app.migrations import verify_current


class Ledger:
    def __init__(self, rows): self.rows = rows
    def execute(self, sql):
        assert sql == 'SELECT name, checksum FROM platform.schema_migration'
        return self
    def fetchall(self): return self.rows


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_current_ledger_is_readonly_and_accepts_checkout_newlines(tmp_path, newline):
    raw = ('SELECT 1;' + newline).encode()
    (tmp_path/'001.sql').write_bytes(raw)
    verify_current(Ledger([dict(name='001.sql', checksum=sha256(b'SELECT 1;\n').hexdigest())]), tmp_path)


@pytest.mark.parametrize('rows', [[], [dict(name='000.sql', checksum='0'*64)],
                                [dict(name='001.sql', checksum='0'*64)]])
def test_missing_extra_or_changed_migration_blocks_readiness(tmp_path, rows):
    (tmp_path/'001.sql').write_text('SELECT 1;')
    with pytest.raises(ValueError, match='MIGRATION_'):
        verify_current(Ledger(rows), tmp_path)


def test_missing_distribution_blocks_readiness(tmp_path):
    with pytest.raises(ValueError, match='FILES_MISSING'):
        verify_current(Ledger([]), tmp_path)
