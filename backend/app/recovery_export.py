"""Export pre-existing quiesced recovery copies. Never snapshots a live system."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tarfile
from uuid import uuid4

from .recovery_files import inventory


def digest(path):
    result = sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def export(destination, dump, expected_dump_checksum, roots):
    if set(roots) != {'secrets', 'uploads', 'artifacts', 'outputs'}:
        raise ValueError('RECOVERY_ROOTS_REQUIRED')
    if digest(dump) != expected_dump_checksum:
        raise ValueError('RECOVERY_DUMP_MISMATCH')
    before = {name: inventory(root) for name, root in roots.items()}
    destination = Path(destination)
    destination.mkdir(mode=0o700, exist_ok=False)
    # An interrupted directory intentionally remains without manifest.json; never overwrite it.
    entries = []
    shutil.copyfile(dump, destination / 'database.dump')
    if digest(destination / 'database.dump') != expected_dump_checksum:
        raise ValueError('RECOVERY_DUMP_COPY_FAILED')
    entries.append({'name': 'database.dump', 'sha256': expected_dump_checksum,
                    'bytes': (destination / 'database.dump').stat().st_size})
    for name, root in roots.items():
        archive = destination / f'{name}.tar'
        with tarfile.open(archive, 'x') as bundle:
            for relative in sorted(before[name]):
                bundle.add(Path(root) / relative, arcname=relative, recursive=False)
        if inventory(root) != before[name]:
            raise ValueError('RECOVERY_SOURCE_CHANGED')
        with tarfile.open(archive) as bundle:
            observed = {}
            for member in bundle:
                if member.isdir():
                    observed[member.name] = ('directory', 0, None)
                elif member.isfile():
                    checksum = sha256()
                    with bundle.extractfile(member) as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            checksum.update(block)
                    observed[member.name] = ('file', member.size, checksum.hexdigest())
                else:
                    raise ValueError('RECOVERY_ARCHIVE_TYPE_REJECTED')
            if observed != before[name]:
                raise ValueError('RECOVERY_ARCHIVE_MISMATCH')
        entries.append({'name': archive.name, 'sha256': digest(archive), 'bytes': archive.stat().st_size})
    # A root already archived can still change while a later root is copied.
    # Check the entire source set again before publishing the completion marker.
    if digest(dump) != expected_dump_checksum or any(
        inventory(root) != before[name] for name, root in roots.items()
    ):
        raise ValueError('RECOVERY_SOURCE_CHANGED')
    manifest = {'format': 'workbench-private-recovery-v1', 'contains_secrets': True,
                'live_snapshot_created': False, 'files': entries}
    with (destination / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    return {'status': 'PASS', 'archives': 4, 'database_dump': True,
            'contains_secrets': True, 'live_snapshot_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump-checksum', required=True)
    args = parser.parse_args()
    try:
        if os.environ.get('WORKBENCH_RECOVERY_EXPORT') != 'private-copies-v1':
            raise ValueError('RECOVERY_EXPORT_OPT_IN_REQUIRED')
        roots = {name: Path('/copies') / name for name in ('secrets', 'uploads', 'artifacts', 'outputs')}
        for path in [*roots.values(), Path('/snapshot.dump')]:
            if not os.statvfs(path).f_flag & os.ST_RDONLY:
                raise ValueError('RECOVERY_READONLY_REQUIRED')
        name = 'recovery-' + str(uuid4())
        result = export(Path('/backup') / name, '/snapshot.dump', args.dump_checksum, roots)
        result['directory'] = name
    except Exception:
        result = {'status': 'FAILED', 'detail': 'Private export failed; retain incomplete output for inspection'}
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
