from hashlib import sha256
from threading import Event
import pytest
from app.json_runtime_evidence import MARKER, require_json_runtime_receipt
from app import hop_cli
from test_hop_cli import setup


@pytest.mark.parametrize('data', [b'', MARKER + b'\n' + MARKER, MARKER.replace(b'=Y', b'=N'),
    b'WORKBENCH_JSON_READER_V2 INCLUDE_NULLS=Y', MARKER + b' extra', 'not bytes'])
def test_missing_changed_duplicate_runtime_receipts_fail(data):
    with pytest.raises(ValueError, match='JSON_RUNTIME_RECEIPT_REQUIRED'):
        require_json_runtime_receipt(data)


def json_prepared(setup):
    prepared, process, options = setup
    source = prepared['source_path'].with_name('source.json')
    prepared['source_path'].rename(source); prepared['source_path'] = source
    original = source.with_name('source-original.json'); original.write_bytes(source.read_bytes())
    prepared['original_source_path'] = original
    prepared['binding'].update(source_format='JSON', json_reader={
        'version': 1, 'reader_checksum': sha256(b'synthetic').hexdigest(),
        'original_byte_count': 9, 'reader_byte_count': 9, 'normalization': 'NONE',
        'profile_checksum': 'a' * 64, 'contract_checksum': 'b' * 64})
    return prepared, process, options


@pytest.mark.parametrize('receipt', [b'', MARKER + b'\n', MARKER + b'\n' + MARKER + b'\n'])
def test_json_success_requires_exact_saved_private_runtime_receipt(setup, receipt):
    prepared, process, options = json_prepared(setup)
    options['environment'] = {'WORKBENCH_VERTICA_PASSWORD': 'synthetic-unused'}
    process.return_value['output'] = receipt + process.return_value['output']
    result = hop_cli.run_hop_cli(prepared, Event(), **options)
    assert result['result']['status'] == ('COMPLETED' if receipt == MARKER + b'\n' else 'UNKNOWN')
    assert result['result']['log_checksum'] == sha256(process.return_value['output']).hexdigest()
    assert result['qa_passed'] is False
    hop_cli.hop_command.assert_called_once_with(prepared['directory'].as_posix(),
        credential_launcher=True, source_count=1, source_format='JSON')


def test_json_cannot_fallback_to_unattested_launcher(setup):
    prepared, process, options = json_prepared(setup)
    with pytest.raises(ValueError, match='JSON_PRIVATE_LAUNCHER_REQUIRED'):
        hop_cli.run_hop_cli(prepared, Event(), **options)
    process.assert_not_called()
