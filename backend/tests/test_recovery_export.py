import json
import pytest
from app.recovery_export import export, digest


def test_private_export_and_no_overwrite(tmp_path):
    roots = {name: tmp_path/name for name in ('secrets','uploads','artifacts','outputs')}
    for root in roots.values():
        root.mkdir()
        (root/'empty').mkdir()
        (root/'synthetic').write_bytes(b'not-real-data')
    dump = tmp_path/'input.dump'
    dump.write_bytes(b'synthetic-not-postgres')
    destination = tmp_path/'export'
    assert export(destination, dump, digest(dump), roots)['status'] == 'PASS'
    manifest = json.loads((destination/'manifest.json').read_text())
    assert manifest['contains_secrets'] and not manifest['live_snapshot_created']
    assert len(manifest['files']) == 5
    for entry in manifest['files']:
        assert digest(destination/entry['name']) == entry['sha256']
    with pytest.raises(FileExistsError):
        export(destination, dump, digest(dump), roots)
    with pytest.raises(ValueError, match='DUMP_MISMATCH'):
        export(tmp_path/'wrong', dump, '0'*64, roots)
    assert not (tmp_path/'wrong').exists()


@pytest.mark.parametrize('changed', ['secrets', 'dump'])
def test_change_after_earlier_archive_prevents_completion(tmp_path, monkeypatch, changed):
    import app.recovery_export as module
    roots = {name: tmp_path/name for name in ('secrets','uploads','artifacts','outputs')}
    for root in roots.values():
        root.mkdir()
        (root/'synthetic').write_bytes(b'before')
    dump = tmp_path/'input.dump'
    dump.write_bytes(b'original')
    expected = digest(dump)
    original_digest = module.digest
    def racing_digest(path):
        value = original_digest(path)
        if path.name == 'outputs.tar':
            target = dump if changed == 'dump' else roots['secrets']/'synthetic'
            target.write_bytes(b'changed-during-later-archive')
        return value
    monkeypatch.setattr(module, 'digest', racing_digest)
    destination = tmp_path/'incomplete'
    with pytest.raises(ValueError, match='SOURCE_CHANGED'):
        export(destination, dump, expected, roots)
    assert destination.exists()
    assert not (destination/'manifest.json').exists()
