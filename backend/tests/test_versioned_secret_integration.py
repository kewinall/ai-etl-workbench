import os
from uuid import uuid4
import pytest
from app.repository import PostgresRepository
from app.platform_harness import encrypt_secret
from test_run_queue_integration import context, pytestmark


def test_real_vault_version_rotation_rejects_old_snapshot(context):
    queue, _ = context
    repo = PostgresRepository(os.environ['DATABASE_URL'])
    reference = 'connection:test-version-' + uuid4().hex
    try:
        cipher, nonce = encrypt_secret('synthetic-first')
        repo.save_secret(reference, cipher, nonce)
        first = repo.secret_version(reference)
        assert repo.read_secret_at_version(reference, first) == 'synthetic-first'
        cipher, nonce = encrypt_secret('synthetic-second')
        repo.save_secret(reference, cipher, nonce)
        second = repo.secret_version(reference)
        assert first != second
        with pytest.raises(ValueError, match='CREDENTIAL_VERSION_CHANGED'):
            repo.read_secret_at_version(reference, first)
        assert repo.read_secret_at_version(reference, second) == 'synthetic-second'
        with pytest.raises(ValueError, match='CREDENTIAL_VERSION_CHANGED'):
            repo.read_secret_at_version(reference+'-missing', second)
    finally:
        with queue.conn() as conn:
            conn.execute('DELETE FROM platform.secret_vault_entry WHERE secret_ref=%s', (reference,))
