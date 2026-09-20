import os
import time
from app import task_uploads


def test_expired_upload_is_not_deleted_without_reference_check(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    uploaded = task_uploads.save_and_profile('old.csv', b'id\n1\n')
    folder = tmp_path / uploaded['upload_id']
    old = time.time() - 90 * 86400
    os.utime(folder, (old, old))
    assert task_uploads.cleanup_expired(1) == 0
    assert (folder / 'source.csv').read_bytes() == b'id\n1\n'
    task_uploads.save_and_profile('new.csv', b'id\n2\n')
    assert task_uploads.cleanup_expired(1) == 0
    assert (folder / 'source.csv').is_file()


def test_cleanup_does_not_create_missing_root(tmp_path, monkeypatch):
    root = tmp_path / 'missing'
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', root)
    assert task_uploads.cleanup_expired() == 0
    assert not root.exists()
