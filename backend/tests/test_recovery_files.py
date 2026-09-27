import pytest
from app.recovery_files import compare


def test_all_files_empty_directories_and_differences(tmp_path):
    source, restored = tmp_path/'source', tmp_path/'restored'
    for root in (source, restored):
        root.mkdir()
        (root/'empty').mkdir()
        (root/'private-name').write_bytes(b'synthetic')
    result = compare(source, restored)
    assert result == dict(status='PASS', files=1, directories=1, bytes=9, missing=0, extra=0, changed=0)
    (restored/'private-name').write_bytes(b'different')
    (restored/'extra').write_bytes(b'')
    (restored/'empty').rmdir()
    result = compare(source, restored)
    assert result['status'] == 'FAILED'
    assert (result['missing'], result['extra'], result['changed']) == (1, 1, 1)
    assert 'private-name' not in str(result)


def test_same_tree_rejected(tmp_path):
    with pytest.raises(ValueError, match='DISTINCT'):
        compare(tmp_path, tmp_path)


def test_symlink_rejected(tmp_path):
    source, restored = tmp_path/'source', tmp_path/'restored'
    source.mkdir(); restored.mkdir()
    try:
        (source/'link').symlink_to(restored, target_is_directory=True)
    except OSError:
        pytest.skip('Host does not allow creating symlinks')
    with pytest.raises(ValueError, match='SPECIAL'):
        compare(source, restored)


def test_unreadable_directory_is_not_silently_omitted(tmp_path, monkeypatch):
    from app import recovery_files
    def walk(root, *, followlinks, onerror):
        onerror(PermissionError('private path'))
        return iter(())
    monkeypatch.setattr(recovery_files.os, 'walk', walk)
    with pytest.raises(ValueError, match='DIRECTORY_UNREADABLE'):
        recovery_files.inventory(tmp_path)
