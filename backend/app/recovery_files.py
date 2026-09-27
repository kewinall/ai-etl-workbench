"""Compare readonly recovery trees without revealing filenames or contents."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat


def inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('RECOVERY_DIRECTORY_REQUIRED')
    entries = {}
    def fail_walk(error):
        raise ValueError('RECOVERY_DIRECTORY_UNREADABLE') from None
    for current, directories, files in os.walk(root, followlinks=False, onerror=fail_walk):
        for name in sorted(directories + files):
            path = Path(current) / name
            before = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(before.st_mode):
                entries[relative] = ('directory', 0, None)
            elif stat.S_ISREG(before.st_mode):
                digest = sha256()
                # Refuse symlink substitution between enumeration and open on Linux.
                fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                with os.fdopen(fd, 'rb') as stream:
                    opened = os.fstat(stream.fileno())
                    if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                        raise ValueError('RECOVERY_FILE_CHANGED')
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                    after = os.fstat(stream.fileno())
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('RECOVERY_FILE_CHANGED')
                entries[relative] = ('file', before.st_size, digest.hexdigest())
            else:
                raise ValueError('RECOVERY_SPECIAL_FILE_REJECTED')
    return entries


def compare(source, restored):
    if Path(source).resolve() == Path(restored).resolve() or os.path.samefile(source, restored):
        raise ValueError('RECOVERY_DISTINCT_COPIES_REQUIRED')
    original, copy = inventory(source), inventory(restored)
    missing = len(original.keys() - copy.keys())
    extra = len(copy.keys() - original.keys())
    changed = sum(original[key] != copy[key] for key in original.keys() & copy.keys())
    return {'status': 'PASS' if not (missing or extra or changed) else 'FAILED',
            'files': sum(value[0] == 'file' for value in original.values()),
            'directories': sum(value[0] == 'directory' for value in original.values()),
            'bytes': sum(value[1] for value in original.values()),
            'missing': missing, 'extra': extra, 'changed': changed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--restored', required=True)
    args = parser.parse_args()
    try:
        for root in (args.source, args.restored):
            if not os.statvfs(root).f_flag & os.ST_RDONLY:
                raise ValueError('RECOVERY_READONLY_REQUIRED')
        result = compare(args.source, args.restored)
    except Exception:
        result = {'status': 'FAILED', 'detail': 'Readonly tree verification failed'}
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
