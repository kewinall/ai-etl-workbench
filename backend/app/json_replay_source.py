"""Verify both private JSON files around isolated replay; no write authority."""
from hashlib import sha256
from .json_execution_binding import validate_reader_binding, reader_binding


def verify_staged_json(staged, binding, reference):
    reader=validate_reader_binding(binding)
    if reader_binding(staged['evidence'],reference)!=binding:
        raise ValueError('PORTABILITY_JSON_STAGING_CHANGED')
    for path,checksum,size in (
        (staged['original_path'],binding['source_checksum'],reader['original_byte_count']),
        (staged['path'],reader['reader_checksum'],reader['reader_byte_count'])):
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=size:
            raise ValueError('PORTABILITY_JSON_SOURCE_CHANGED')
        if sha256(path.read_bytes()).hexdigest()!=checksum:
            raise ValueError('PORTABILITY_JSON_SOURCE_CHANGED')
