"""Private SDM byte storage. Caller must validate workbook and persist metadata.

No caller-supplied filename, traversal, overwrite or automatic cleanup. This is
not protection against a privileged administrator racing filesystem operations.
"""
from hashlib import sha256
from pathlib import Path
from uuid import UUID
import os
import re
import stat

MAX_BYTES = 16 * 1024 * 1024


def _directory(path):
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('SDM_STORAGE_UNSAFE_PATH')


def _path(root, project_id, run_id, sdm_id, *, create=False):
    root = Path(root)
    if not root.is_absolute():
        raise ValueError('SDM_STORAGE_ABSOLUTE_ROOT_REQUIRED')
    identities = [str(UUID(str(value))) for value in (project_id, run_id, sdm_id)]
    _directory(root)
    folder = root
    for segment in ('sdm', *identities[:2]):
        folder = folder / segment
        if create:
            folder.mkdir(mode=0o700, exist_ok=True)
        _directory(folder)
    return folder / (identities[2] + '.xlsx')


def save_sdm_bytes(root, project_id, run_id, sdm_id, content):
    if type(content) is not bytes or not 0 < len(content) <= MAX_BYTES:
        raise ValueError('SDM_STORAGE_SIZE_INVALID')
    path = _path(root, project_id, run_id, sdm_id, create=True)
    # Exclusive create intentionally rejects even an identical prior file.
    # DB idempotency must resolve existing metadata before generating a new ID.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return {'file_path': str(path), 'file_size': len(content), 'checksum': sha256(content).hexdigest()}


def read_sdm_bytes(root, project_id, run_id, sdm_id, *, checksum, file_size):
    if (type(file_size) is not int or not 0 < file_size <= MAX_BYTES
        or not isinstance(checksum, str) or not re.fullmatch('[a-f0-9]{64}', checksum)):
        raise ValueError('SDM_STORAGE_METADATA_INVALID')
    try:
        path = _path(root, project_id, run_id, sdm_id)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or getattr(before, 'st_file_attributes', 0) & 0x400:
            raise ValueError()
        with path.open('rb') as stream:
            info = os.fstat(stream.fileno())
            if (info.st_dev, info.st_ino, info.st_size) != (before.st_dev, before.st_ino, file_size):
                raise ValueError()
            content = stream.read(file_size + 1)
        if len(content) != file_size or sha256(content).hexdigest() != checksum:
            raise ValueError()
        return content
    except (OSError, ValueError):
        raise ValueError('SDM_FILE_CHANGED_OR_UNAVAILABLE') from None
