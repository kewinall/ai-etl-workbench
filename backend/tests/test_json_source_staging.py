from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import pytest
from app import task_uploads
from app.source_staging import stage_json_source
from test_json_input_contract import policy


@pytest.fixture
def uploaded(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    from app.json_source_profile import confirmed_json_profile
    upload = task_uploads.save_and_profile('synthetic.json', b'\xef\xbb\xbf [ { "id" : "001" } ] ')
    profile = confirmed_json_profile(upload['upload_id'], upload['checksum'], upload['size'])
    return {**upload, **profile,
            'type': 'JSON', 'has_actual_data': True}


def test_stage_exact_reader_copy_preserves_original_and_cleans_attempt(uploaded):
    original = Path(uploaded['path']).read_bytes()
    with stage_json_source(uuid4(), uploaded, policy()) as staged:
        assert staged['path'].read_bytes() == original[3:]
        assert staged['evidence']['content_checksum'] == sha256(original).hexdigest()
        assert staged['evidence']['reader_content_checksum'] == sha256(original[3:]).hexdigest()
        assert staged['execution_authorized'] is False
        assert staged['evidence']['column_types_checked'] is True
        assert staged['evidence']['type_conversion_verified'] is False
        directory = staged['directory']
    assert not directory.exists()
    assert Path(uploaded['path']).read_bytes() == original


def test_changed_upload_cannot_be_staged(uploaded):
    Path(uploaded['path']).write_bytes(b'[{"id":"002"}]')
    with pytest.raises(ValueError, match='UPLOAD_CONTENT_CHANGED'):
        with stage_json_source(uuid4(), uploaded, policy()):
            pytest.fail('Changed source yielded')


def test_no_arbitrary_path_fallback(uploaded):
    with pytest.raises(ValueError, match='UPLOAD_BINDING_INVALID'):
        with stage_json_source(uuid4(), {**uploaded, 'upload_id': None}, policy()):
            pytest.fail('Unbound source yielded')


def test_stage_requires_profile_confirmation(uploaded):
    uploaded.pop('json_profile_binding_v1')
    with pytest.raises(ValueError, match='JSON_PROFILE_CONFIRMATION_REQUIRED'):
        with stage_json_source(uuid4(), uploaded, policy()):
            pytest.fail('Unconfirmed source yielded')
