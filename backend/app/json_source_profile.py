"""Managed JSON profile identity; explicit confirmation, no execution authority."""
from hashlib import sha256
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .json_profile import inspect_json
from .json_input_contract import contract_checksum


def confirmed_json_profile(upload_id, checksum, size, *, content=None):
    from .upload_integrity import read_verified_upload
    if content is None:
        content = read_verified_upload(upload_id, 'JSON', checksum, size)
    elif not isinstance(content, bytes) or type(size) is not int or len(content) != size or sha256(content).hexdigest() != checksum:
        raise ValueError('UPLOAD_CONTENT_CHANGED')
    profile, _ = inspect_json(content)
    binding = {'version': 1, 'upload_id': upload_id, 'content_checksum': checksum,
               'byte_count': size, 'fields': profile['fields'], 'root_shape': profile['root_shape'],
               'row_count': profile['row_count'], 'profile_version': profile['json_profile_version']}
    profile['json_profile_binding_v1'] = {**binding, 'profile_checksum': contract_checksum(binding),
                                       'scope': 'INPUT_PROFILE_ONLY'}
    return profile


def verify_json_source(source, *, content=None):
    binding = source.get('json_profile_binding_v1')
    if not isinstance(binding, dict):
        raise ValueError('JSON_PROFILE_CONFIRMATION_REQUIRED')
    profile = confirmed_json_profile(source.get('upload_id'), source.get('checksum'), source.get('size'), content=content)
    if (contract_checksum(binding) != contract_checksum(profile['json_profile_binding_v1'])
            or source.get('fields') != profile['fields'] or source.get('root_shape') != profile['root_shape']):
        raise ValueError('JSON_PROFILE_BINDING_CHANGED')
    return profile


class JsonProfileInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    checksum: str = Field(pattern=r'^[0-9a-f]{64}$')
    size: int = Field(gt=0, le=50 * 1024 * 1024)


def create_json_profile_router():
    router = APIRouter()

    @router.post('/api/task-sources/{upload_id}/json-profile')
    def confirm(upload_id: str, data: JsonProfileInput):
        try:
            return confirmed_json_profile(upload_id, **data.model_dump())
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    return router
