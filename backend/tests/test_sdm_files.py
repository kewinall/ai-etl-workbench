from uuid import uuid4
from pathlib import Path
import pytest
from app.sdm_files import save_sdm_bytes, read_sdm_bytes


def test_exclusive_write_exact_read_and_changed_file_rejected(tmp_path):
    ids = [uuid4() for _ in range(3)]
    content = b'synthetic opaque storage test, not an Excel workbook'
    saved = save_sdm_bytes(tmp_path, *ids, content)
    metadata = {key:saved[key] for key in ('checksum','file_size')}
    assert read_sdm_bytes(tmp_path, *ids, **metadata) == content
    with pytest.raises(FileExistsError): save_sdm_bytes(tmp_path, *ids, b'overwrite')
    assert Path(saved['file_path']).read_bytes() == content
    Path(saved['file_path']).write_bytes(b'x'*len(content))
    with pytest.raises(ValueError, match='SDM_FILE_CHANGED_OR_UNAVAILABLE'):
        read_sdm_bytes(tmp_path, *ids, **metadata)


@pytest.mark.parametrize('bad', ['../escape', '/tmp/escape', '', 'not-a-uuid'])
def test_identity_cannot_supply_path(tmp_path,bad):
    with pytest.raises(ValueError): save_sdm_bytes(tmp_path,bad,uuid4(),uuid4(),b'test')
    assert not list(tmp_path.iterdir())


def test_other_project_cannot_read_and_missing_root_is_not_created(tmp_path):
    ids=[uuid4() for _ in range(3)]
    saved=save_sdm_bytes(tmp_path,*ids,b'test')
    metadata={key:saved[key] for key in ('checksum','file_size')}
    with pytest.raises(ValueError,match='SDM_FILE_CHANGED_OR_UNAVAILABLE'):
        read_sdm_bytes(tmp_path,uuid4(),*ids[1:],**metadata)
    missing=tmp_path/'not-configured'
    with pytest.raises(FileNotFoundError):save_sdm_bytes(missing,*ids,b'test')
    assert not missing.exists()


def test_symlink_directory_is_rejected(tmp_path):
    real=tmp_path/'real';real.mkdir()
    link=tmp_path/'link'
    try:link.symlink_to(real,target_is_directory=True)
    except OSError:pytest.skip('Creating symlinks requires platform permission')
    with pytest.raises(ValueError,match='SDM_STORAGE_UNSAFE_PATH'):
        save_sdm_bytes(link,uuid4(),uuid4(),uuid4(),b'test')
    assert not list(real.iterdir())
