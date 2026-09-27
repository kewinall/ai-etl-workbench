"""Validate a private recovery package and unpack into four empty directories.

Does not restore PostgreSQL, start services, overwrite files or remove partial output.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import tarfile

from .recovery_export import digest


def unpack(package, destination):
    package, destination = Path(package), Path(destination)
    names = ('secrets', 'uploads', 'artifacts', 'outputs')
    manifest = json.loads((package / 'manifest.json').read_text())
    expected = {'database.dump', *(name + '.tar' for name in names)}
    entries = manifest['files']
    if (manifest['format'] != 'workbench-private-recovery-v1'
            or len(entries) != 5 or {entry['name'] for entry in entries} != expected):
        raise ValueError('RECOVERY_MANIFEST_INVALID')
    for entry in entries:
        path = package / entry['name']
        if path.is_symlink() or path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('RECOVERY_PACKAGE_MISMATCH')
    for name in names:
        root = destination / name
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise ValueError('RECOVERY_EMPTY_DESTINATION_REQUIRED')
        with tarfile.open(package / (name + '.tar')) as archive:
            seen = set()
            for member in archive:
                path = PurePosixPath(member.name)
                if (not (member.isfile() or member.isdir()) or path.is_absolute()
                        or '..' in path.parts or '\\' in member.name or ':' in member.name
                        or not path.parts or member.name in seen):
                    raise ValueError('RECOVERY_ARCHIVE_MEMBER_REJECTED')
                seen.add(member.name)
    for name in names:
        with tarfile.open(package / (name + '.tar')) as archive:
            archive.extractall(destination / name, filter='data')
    return {'status': 'PASS', 'archives_unpacked': 4, 'database_restored': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    try:
        result = unpack(args.package, args.destination)
    except Exception:
        result = {'status': 'FAILED', 'detail': 'Package validation or empty-destination extraction failed'}
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
