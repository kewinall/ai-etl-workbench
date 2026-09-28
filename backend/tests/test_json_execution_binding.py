from copy import deepcopy
from hashlib import sha256
from uuid import uuid4
import pytest
from app import task_uploads
from app.json_source_profile import confirmed_json_profile
from app.json_execution_binding import validate_reader_binding
from app.source_binding import execution_sources, expected_prepared_binding
from app.source_staging import stage_json_source
from app.prepared_integrity import verify_prepared_files
from app.execution_oracle import validate_execution_sources
from app.hop_command import hop_command
from test_json_input_contract import policy


@pytest.fixture(params=[False, True])
def bound(tmp_path, monkeypatch, request):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    data = (b'\xef\xbb\xbf' if request.param else b'') + b' [ { "id" : "001" },{} ] '
    uploaded = task_uploads.save_and_profile('synthetic.json', data)
    profile = confirmed_json_profile(uploaded['upload_id'], uploaded['checksum'], uploaded['size'])
    source = {**uploaded, **profile, 'type': 'JSON', 'has_actual_data': True}
    config = {'sources': [source], 'json_input_contract_v1': policy()}
    return config, execution_sources(config, 5), data


def test_original_reader_identity_and_post_execution_oracle(bound):
    config, binding, data = bound
    reader = validate_reader_binding(binding)
    assert binding['source_checksum'] == sha256(data).hexdigest()
    assert reader['reader_checksum'] == sha256(data.removeprefix(b'\xef\xbb\xbf')).hexdigest()
    auth = dict.fromkeys(('run_id', 'specification_id', 'specification_approval_id',
        'specification_checksum', 'input_checksum', 'settings_checksum', 'hpl_checksum'), 'a' * 64)
    expected = expected_prepared_binding({**auth, **binding})
    assert expected['json_reader'] == reader and expected['json_reader'] is not reader
    assert not any(key in str(binding) for key in ('upload_id', 'path', '001'))
    validate_execution_sources({'policy_version': 'hop-single-attempt-v5', **binding}, config)
    for downgrade in ('hop-single-attempt-v2', 'hop-single-attempt-v3', 'hop-single-attempt-v4'):
        with pytest.raises(ValueError):
            validate_execution_sources({'policy_version': downgrade, **binding}, config)


@pytest.mark.parametrize('change', ['missing', 'reader', 'size', 'bool_size', 'profile', 'policy', 'normalization', 'csv', 'multiple'])
def test_incomplete_or_changed_reader_binding_rejected(bound, change):
    config, binding, _ = bound
    changed = deepcopy(binding)
    if change == 'missing': changed.pop('json_reader')
    elif change == 'csv': changed['source_format'] = 'CSV'
    elif change == 'multiple': changed['source_checksums'] = {'source.0': 'a' * 64, 'source.1': 'b' * 64}
    else:
        key = {'reader': 'reader_checksum', 'size': 'reader_byte_count', 'bool_size': 'reader_byte_count',
               'profile': 'profile_checksum', 'policy': 'contract_checksum', 'normalization': 'normalization'}[change]
        changed['json_reader'][key] = True if change == 'bool_size' else 1 if change == 'size' else 'tampered'
    with pytest.raises(ValueError):
        validate_reader_binding(changed)
    with pytest.raises(ValueError):
        validate_execution_sources({'policy_version': 'hop-single-attempt-v5', **changed}, config)


@pytest.mark.parametrize('change', ['none', 'reader', 'original', 'path', 'lineage', 'downgrade'])
def test_last_use_verifies_both_files_and_bom_only_relationship(bound, change):
    config, binding, data = bound
    with stage_json_source(uuid4(), config['sources'][0], policy()) as staged:
        hpl = staged['directory'] / 'candidate.hpl'; hpl.write_bytes(b'<pipeline/>')
        prepared = {'directory': staged['directory'], 'source_path': staged['path'], 'hpl_path': hpl,
                    'original_source_path': staged['original_path'],
                    'binding': {**binding, 'hpl_checksum': sha256(hpl.read_bytes()).hexdigest()}}
        if change in ('reader', 'original'):
            staged['path' if change == 'reader' else 'original_path'].write_bytes(b'changed')
        elif change == 'path': prepared['original_source_path'] = config['sources'][0]['path']
        elif change == 'lineage':
            # Even self-consistent hashes do not permit changing data during BOM removal.
            altered = staged['path'].read_bytes().replace(b'001', b'002')
            staged['path'].write_bytes(altered)
            prepared['binding']['json_reader']['reader_checksum'] = sha256(altered).hexdigest()
        elif change == 'downgrade': prepared['binding'].pop('source_format')
        if change == 'none':
            result = verify_prepared_files(prepared)
            assert result['source_checksum'] == sha256(data).hexdigest()
            assert result['reader_checksum'] == binding['json_reader']['reader_checksum']
        else:
            with pytest.raises(ValueError, match='PREPARED_FILES_CHANGED_OR_UNAVAILABLE'):
                verify_prepared_files(prepared)
        folder = staged['directory']
    assert not folder.exists()


@pytest.mark.parametrize('private', [False, True])
def test_json_launch_pins_null_rows_and_has_no_csv_fallback(private):
    args = hop_command('/candidate with spaces,comma', credential_launcher=private, source_format='JSON')
    assert args[0] == '/usr/bin/java' and '-DHOP_JSON_INPUT_INCLUDE_NULLS=Y' in args
    assert args[-1] == '--parameters=SOURCE_JSON=/candidate with spaces,comma/source.json'
    assert not any('SOURCE_CSV' in arg or 'PASSWORD' in arg for arg in args)
    with pytest.raises(ValueError, match='INVALID_HOP_SOURCE_FORMAT'):
        hop_command('/candidate', source_format='JSON', source_count=2)
