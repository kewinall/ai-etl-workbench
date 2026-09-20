"""Versioned, non-secret evidence binding used by formal delivery artifacts."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field


class ReleaseDocumentBindingV1(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: Literal[1]
    run_id: UUID
    specification_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    qa_binding_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    source_sdm_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    portability_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')


def document_binding(value,run_id,specification_checksum):
    binding=ReleaseDocumentBindingV1.model_validate(value).model_dump(mode='json')
    if binding['run_id']!=str(run_id) or binding['specification_checksum']!=specification_checksum:
        raise ValueError('RELEASE_DOCUMENT_BINDING_CHANGED')
    return binding
