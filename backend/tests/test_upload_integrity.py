import hashlib
import uuid

import pytest

from app import task_uploads
from app.upload_integrity import read_verified_upload


@pytest.fixture
def upload(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    uid = str(uuid.uuid4())
    folder = tmp_path / uid
    folder.mkdir()
    data = b'name,value\na,1\n'
    path = folder / 'source.csv'
    path.write_bytes(data)
    return path, [uid, 'CSV', hashlib.sha256(data).hexdigest(), len(data)], data


def test_exact_snapshot(upload):
    path, binding, data = upload
    snapshot = read_verified_upload(*binding)
    path.write_bytes(b'changed')
    assert snapshot == data
    with pytest.raises(ValueError, match='UPLOAD_CONTENT_CHANGED'):
        read_verified_upload(*binding)


@pytest.mark.parametrize('change', [b'x', b'', b'name,value\nb,1\n', b'name,value\na,1\nextra'])
def test_changed_bytes(upload, change):
    path, binding, _ = upload
    path.write_bytes(change)
    with pytest.raises(ValueError, match='UPLOAD_CONTENT_CHANGED'):
        read_verified_upload(*binding)


@pytest.mark.parametrize('index,value', [(0, '../outside'), (0, None), (1, '../../x'),
                                         (2, 'invalid'), (3, True), (3, 0),
                                         (3, 50 * 1024 * 1024 + 1)])
def test_invalid_binding(upload, index, value):
    _, binding, _ = upload
    binding[index] = value
    with pytest.raises(ValueError, match='UPLOAD_BINDING_INVALID'):
        read_verified_upload(*binding)


def test_missing(upload):
    path, binding, _ = upload
    path.unlink()
    with pytest.raises(ValueError, match='^UPLOAD_UNAVAILABLE$'):
        read_verified_upload(*binding)


def test_directory_is_not_file(upload):
    path, binding, _ = upload
    path.unlink()
    path.mkdir()
    with pytest.raises(ValueError, match='UPLOAD_PATH_INVALID'):
        read_verified_upload(*binding)
