"""Read a managed upload once; callers must use returned bytes, not reopen paths."""
import hashlib
import re
import stat
import uuid

from . import task_uploads

MAX_BYTES = 50 * 1024 * 1024
SUFFIXES = {'CSV': '.csv', 'EXCEL': '.xlsx', 'JSON': '.json'}


def read_verified_upload(upload_id, source_type, checksum, size):
    """No arbitrary paths, data rewriting, execution authority or secret output.

    Metadata must come from the approved revision, not an untrusted new request.
    The returned byte snapshot is checksum-bound even if the disk later changes.
    This is not protection against a privileged local filesystem attacker.
    """
    try:
        valid_id = isinstance(upload_id, str) and str(uuid.UUID(upload_id)) == upload_id
    except (ValueError, AttributeError):
        valid_id = False
    if (not valid_id or not isinstance(source_type, str) or source_type not in SUFFIXES
            or not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum)
            or type(size) is not int or not 0 < size <= MAX_BYTES):
        raise ValueError('UPLOAD_BINDING_INVALID')
    root = task_uploads.UPLOAD_ROOT.resolve()
    folder = root / upload_id
    path = folder / ('source' + SUFFIXES[source_type])
    try:
        # Reject symlinks and Windows junctions/reparse points at managed levels.
        for entry in (folder, path):
            info = entry.lstat()
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, 'st_file_attributes', 0) & 0x400):
                raise ValueError('UPLOAD_PATH_INVALID')
        if path.resolve().parent != folder or folder.resolve().parent != root:
            raise ValueError('UPLOAD_PATH_INVALID')
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError('UPLOAD_PATH_INVALID')
        with path.open('rb') as stream:
            content = stream.read(size + 1)
    except OSError:
        raise ValueError('UPLOAD_UNAVAILABLE') from None
    if len(content) != size or hashlib.sha256(content).hexdigest() != checksum:
        raise ValueError('UPLOAD_CONTENT_CHANGED')
    return content
