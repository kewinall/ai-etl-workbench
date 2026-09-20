"""Last-use checks for private prepared files; never grants execution authority."""
from hashlib import sha256
from pathlib import Path
import re
import stat


def verify_prepared_files(prepared):
    """Caller must still reserve authorization and mount files read-only.

    This detects changed bytes, missing files and redirected paths. It is not
    protection against an administrator modifying files after verification.
    Returns only checksums, never private paths or source content.
    """
    try:
        directory = Path(prepared['directory'])
        binding = prepared['binding']
        if not directory.is_absolute():
            raise ValueError()
        for ancestor in (directory, *directory.parents):
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError()
        result = {}
        for path_key, name, checksum_key in (
            ('source_path', 'source.csv', 'source_checksum'),
            ('hpl_path', 'candidate.hpl', 'hpl_checksum'),
        ):
            path = Path(prepared[path_key])
            expected = binding[checksum_key]
            if path != directory / name or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
                raise ValueError()
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError()
            digest = sha256()
            total = 0
            with path.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > 50 * 1024 * 1024:
                        raise ValueError()
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError()
            result[checksum_key] = expected
        return result
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError('PREPARED_FILES_CHANGED_OR_UNAVAILABLE') from None
