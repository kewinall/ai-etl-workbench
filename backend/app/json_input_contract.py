"""Explicit flat JSON semantics; never authorizes ETL or rewrites source records."""
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator
from .json_profile import inspect_json


class JsonInputContractV1(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[1]
    encoding: Literal['UTF-8-SIG']
    bom_handling: Literal['REMOVE_UTF8_BOM']
    root_shape: Literal['ARRAY', 'OBJECT']
    missing_keys: Literal['NULL']
    extra_keys: Literal['REJECT']
    nested_values: Literal['REJECT']
    duplicate_keys: Literal['REJECT']
    trim_strings: Literal['NONE']
    null_records: Literal['PRESERVE']
    on_error: Literal['FAIL']

    @field_validator('version', mode='before')
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('JSON_CONTRACT_VERSION_INVALID')
        return value


def contract_checksum(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':')).encode()).hexdigest()


def validate_json_content(content, contract, field_names):
    policy = JsonInputContractV1.model_validate(contract)
    if not isinstance(content, bytes) or not 0 < len(content) <= 50 * 1024 * 1024:
        raise ValueError('JSON_BYTES_OR_SIZE_INVALID')
    if (not isinstance(field_names, list) or not 0 < len(field_names) <= 200
            or any(not isinstance(name, str) or not name.strip() for name in field_names)
            or len(set(field_names)) != len(field_names)):
        raise ValueError('JSON_FIELDS_INVALID')
    profile, _ = inspect_json(content)
    if profile['root_shape'] != policy.root_shape:
        raise ValueError('JSON_ROOT_SHAPE_MISMATCH')
    if [field['name'] for field in profile['fields']] != field_names:
        raise ValueError('JSON_COLUMN_BINDING_MISMATCH')
    return {'status': 'JSON_STRUCTURE_VALIDATED_NOT_EXECUTABLE', 'complete': True,
            'records_expected': profile['row_count'], 'root_shape': policy.root_shape,
            'content_checksum': sha256(content).hexdigest(), 'byte_count': len(content),
            'contract_checksum': contract_checksum(policy.model_dump()),
            'field_names_checksum': contract_checksum(field_names),
            'column_statistics': profile['column_statistics'],
            'type_conversion_verified': False, 'execution_authorized': False}


def prepare_json_reader_content(content, contract, field_names):
    """Only remove a leading UTF-8 BOM for Hop 2.12; retain both byte identities.

    No JSON reserialization, field mapping, value conversion, filtering or sorting.
    The original upload is unchanged; the caller must bind this reader checksum
    alongside the original checksum before any execution or portable replay.
    """
    evidence = validate_json_content(content, contract, field_names)
    has_bom = content.startswith(b'\xef\xbb\xbf')
    reader = content[3:] if has_bom else content
    return reader, {**evidence, 'reader_content_checksum': sha256(reader).hexdigest(),
                    'reader_byte_count': len(reader),
                    'normalization': 'UTF8_BOM_REMOVED' if has_bom else 'NONE'}
