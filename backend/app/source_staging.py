"""Private per-attempt source copy; does not authorize or execute a pipeline."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import os
import tempfile
from uuid import UUID

from . import task_uploads
from .upload_integrity import read_verified_upload
from .csv_content_validation import validate_csv_content


@contextmanager
def stage_csv_source(run_id, source, contract):
    """Read once, validate those bytes, then yield a separate attempt-local path.

    Caller must hold current Run/specification authorization and mount the
    directory read-only in Hop. This copy is not immutable against the local
    owner/admin. Never reopen the original upload after staging.
    No data/path from this private object may enter a Release or public API.
    """
    canonical_id = str(UUID(str(run_id)))
    if source.get('type') != 'CSV':
        raise ValueError('STAGING_REQUIRES_CSV')
    content = read_verified_upload(source.get('upload_id'), 'CSV',
                                   source.get('checksum'), source.get('size'))
    evidence = validate_csv_content(content, contract, [field.get('name') for field in source.get('fields', [])])
    if evidence['status'] != 'CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE' or not evidence['complete']:
        raise ValueError('STAGING_CSV_INVALID')
    root = task_uploads.ROOT / 'runtime-temp' / 'run-sources'
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=canonical_id + '-', dir=root) as directory:
        path = Path(directory) / 'source.csv'
        # Exclusive creation; unique attempt directory means retries never replace
        # another attempt's bytes. Private until caller mounts it read-only.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if sha256(path.read_bytes()).hexdigest() != evidence['content_checksum']:
            raise ValueError('STAGING_COPY_MISMATCH')
        yield {'path': path, 'directory': Path(directory), 'evidence': evidence,
               'run_id': canonical_id, 'execution_authorized': False}
