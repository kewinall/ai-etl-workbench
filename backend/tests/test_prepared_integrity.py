from hashlib import sha256
import pytest
from app.prepared_integrity import verify_prepared_files


@pytest.fixture
def prepared(tmp_path):
    source = tmp_path / 'source.csv'
    hpl = tmp_path / 'candidate.hpl'
    source.write_bytes(b'id\n1\n')
    hpl.write_bytes(b'<pipeline/>')
    return {'directory':tmp_path, 'source_path':source, 'hpl_path':hpl,
            'binding':{'source_checksum':sha256(source.read_bytes()).hexdigest(),
                       'hpl_checksum':sha256(hpl.read_bytes()).hexdigest()}}


def test_verified_result_contains_no_paths(prepared):
    assert verify_prepared_files(prepared) == prepared['binding']


@pytest.mark.parametrize('key', ['source_path', 'hpl_path'])
@pytest.mark.parametrize('change', ['modify', 'delete', 'redirect', 'directory'])
def test_changed_files_are_rejected(prepared, key, change):
    path = prepared[key]
    if change == 'modify':
        path.write_bytes(b'changed')
    elif change == 'delete':
        path.unlink()
    elif change == 'redirect':
        replacement = path.with_name('other-file')
        replacement.write_bytes(path.read_bytes())
        prepared[key] = replacement
    else:
        path.unlink()
        path.mkdir()
    with pytest.raises(ValueError, match='^PREPARED_FILES_CHANGED_OR_UNAVAILABLE$'):
        verify_prepared_files(prepared)


def test_invalid_binding_is_rejected(prepared):
    prepared['binding']['source_checksum'] = 'invalid'
    with pytest.raises(ValueError, match='PREPARED_FILES_CHANGED_OR_UNAVAILABLE'):
        verify_prepared_files(prepared)
