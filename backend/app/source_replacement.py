"""Explicit CSV replacement metadata; byte validation occurs before revision commit."""
from copy import deepcopy
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from . import task_uploads
from .upload_integrity import read_verified_upload


class ReplacementField(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=256)
    type: str = Field(min_length=1, max_length=100)


class CsvReplacementV1(BaseModel):
    model_config = ConfigDict(extra='forbid')
    upload_id: UUID
    checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    size: StrictInt = Field(gt=0, le=50 * 1024 * 1024)
    original_name: str = Field(min_length=1, max_length=256)
    fields: list[ReplacementField] = Field(min_length=1, max_length=200)


def replace_csv_source(config, replacement):
    if replacement is None:
        return deepcopy(config)
    parsed = CsvReplacementV1.model_validate(replacement)
    sources = config.get('sources') or ([config] if config.get('type') == 'CSV' else [])
    if len(sources) != 1 or sources[0].get('type') != 'CSV':
        raise ValueError('CSV_REPLACEMENT_NOT_SUPPORTED')
    allowed = {'id', 'type', 'alias', 'has_actual_data', 'path', 'file_path',
               'upload_id', 'checksum', 'size', 'original_name', 'fields',
               'encoding', 'delimiter', 'quote', 'header', 'header_row',
               'worksheet', 'worksheets', 'expires_at', 'profiled',
               'file_pattern', 'parser_format', 'sample_rows', 'source_type'}
    if (set(sources[0]) - allowed
            or set(config) - allowed - {'sources', 'requirement_supplement', 'csv_input_contract_v1'}):
        raise ValueError('CSV_REPLACEMENT_UNSUPPORTED_METADATA')
    if len({field.name for field in parsed.fields}) != len(parsed.fields):
        raise ValueError('DUPLICATE_SOURCE_FIELDS')
    # Never accept a client-supplied path, sample rows or credentials.
    new = {'type': 'CSV', 'alias': sources[0].get('alias') or 'source_1',
           'has_actual_data': True, 'upload_id': str(parsed.upload_id),
           'checksum': parsed.checksum, 'size': parsed.size,
           'original_name': parsed.original_name,
           'fields': [field.model_dump() for field in parsed.fields],
           'path': str(task_uploads.UPLOAD_ROOT / str(parsed.upload_id) / 'source.csv')}
    # Remove duplicated legacy source metadata; retain only semantic supplements.
    return {key: deepcopy(value) for key, value in config.items()
            if key in ('requirement_supplement', 'csv_input_contract_v1')} | {'sources': [new]}


def verify_csv_replacement(replacement):
    if replacement is not None:
        parsed = CsvReplacementV1.model_validate(replacement)
        read_verified_upload(str(parsed.upload_id), 'CSV', parsed.checksum, parsed.size)
