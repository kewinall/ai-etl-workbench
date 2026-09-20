from contextlib import contextmanager
from datetime import datetime, timezone
import pytest
from app.repository import PostgresRepository


def test_secret_read_checks_version_before_decrypt(monkeypatch):
    timestamp=datetime(2026,9,13,tzinfo=timezone.utc)
    row={'cipher_text':b'cipher','nonce':b'nonce','updated_at':timestamp}
    class Cursor:
        def fetchone(self): return row
    class Connection:
        def execute(self, sql, params):
            assert params==('connection:test',)
            assert 'cipher_text,nonce,updated_at' in sql
            return Cursor()
    @contextmanager
    def connection(): yield Connection()
    repo=object.__new__(PostgresRepository)
    monkeypatch.setattr(repo,'conn',connection)
    calls=[]
    monkeypatch.setattr('app.platform_harness.decrypt_secret',lambda cipher,nonce:calls.append((cipher,nonce)) or 'synthetic-secret')
    with pytest.raises(ValueError,match='CREDENTIAL_VERSION_REQUIRED'):repo.read_secret_at_version('connection:test',None)
    with pytest.raises(ValueError,match='CREDENTIAL_VERSION_CHANGED'):repo.read_secret_at_version('connection:test','old')
    assert calls==[]
    assert repo.read_secret_at_version('connection:test',timestamp.isoformat())=='synthetic-secret'
    assert calls==[(b'cipher',b'nonce')]
