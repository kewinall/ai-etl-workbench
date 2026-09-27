import pytest
import json
import tarfile
from app.recovery_export import export, digest
from app.recovery_unpack import unpack
from app.recovery_files import compare


def test_export_unpack_roundtrip_and_refuse_overwrite(tmp_path):
    roots = {name: tmp_path/name for name in ('secrets', 'uploads', 'artifacts', 'outputs')}
    restored = tmp_path/'restored'
    restored.mkdir()
    for name, root in roots.items():
        root.mkdir(); (root/'empty').mkdir()
        (root/'synthetic').write_bytes(b'no-real-data')
        (restored/name).mkdir()
    dump = tmp_path/'input.dump'; dump.write_bytes(b'synthetic')
    package = tmp_path/'package'
    export(package, dump, digest(dump), roots)
    assert unpack(package, restored)['archives_unpacked'] == 4
    for name, root in roots.items():
        assert compare(root, restored/name)['status'] == 'PASS'
    with pytest.raises(ValueError, match='EMPTY_DESTINATION'):
        unpack(package, restored)
    (package/'database.dump').write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='PACKAGE_MISMATCH'):
        unpack(package, restored)


@pytest.mark.parametrize('name,kind', [('../outside','file'), ('/absolute','file'), ('link','symlink')])
def test_invalid_archive_member_rejected_before_writes(tmp_path, name, kind):
    package = tmp_path/'package'; package.mkdir()
    restored = tmp_path/'restored'; restored.mkdir()
    entries = []
    for group in ('secrets','uploads','artifacts','outputs'):
        (restored/group).mkdir()
        path = package/(group+'.tar')
        with tarfile.open(path, 'w') as archive:
            if group == 'outputs':
                item = tarfile.TarInfo(name)
                if kind == 'symlink':
                    item.type = tarfile.SYMTYPE; item.linkname = '../outside'
                archive.addfile(item)
        entries.append(dict(name=path.name, bytes=path.stat().st_size, sha256=digest(path)))
    dump = package/'database.dump'; dump.write_bytes(b'synthetic')
    entries.append(dict(name=dump.name, bytes=dump.stat().st_size, sha256=digest(dump)))
    (package/'manifest.json').write_text(json.dumps(dict(format='workbench-private-recovery-v1', files=entries)))
    with pytest.raises(ValueError, match='MEMBER_REJECTED'):
        unpack(package, restored)
    assert all(not any(root.iterdir()) for root in restored.iterdir())
