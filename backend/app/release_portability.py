"""Evidence validation for an isolated Hop replay. No HTTP proof submission."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .sa_contract import digest
from .source_binding import source_set_checksum


class PortabilityEvidenceV1(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: Literal[1]
    candidate_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    hpl_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    hwf_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    ddl_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    source_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    hop_log_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    result_expected_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    result_actual_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    expected_count: int=Field(strict=True,ge=0,le=10000)
    actual_count: int=Field(strict=True,ge=0,le=10000)
    exit_code: Literal[0]
    isolated_target_created: Literal[True]
    original_artifacts_unmodified: Literal[True]
    workflow_completed: Literal[True]


class PortabilityEvidenceV2(PortabilityEvidenceV1):
    version: Literal[2]
    source_checksums: dict[str,str]


def validate_portability(row,candidate,source_checksum,*,expected_checksum,expected_count,source_checksums=None):
    if not row or row['status']!='PASS':raise ValueError('RELEASE_PORTABILITY_REQUIRED')
    evidence=(PortabilityEvidenceV2 if source_checksums is not None else PortabilityEvidenceV1).model_validate(row['evidence']).model_dump()
    if source_checksums is not None:
        if (evidence['source_checksums'] != source_checksums
                or source_set_checksum(source_checksums) != source_checksum):
            raise ValueError('RELEASE_PORTABILITY_SOURCE_SET_CHANGED')
    if digest(evidence)!=row['checksum'] or evidence['candidate_checksum']!=candidate['checksum']:
        raise ValueError('RELEASE_PORTABILITY_CHANGED')
    artifacts={a['type']:a for a in candidate['manifest']['artifacts']}
    for kind in ('HPL','HWF','DDL'):
        if evidence[kind.lower()+'_checksum']!=artifacts[kind]['checksum']:raise ValueError('RELEASE_PORTABILITY_ARTIFACT_CHANGED')
    if (evidence['source_checksum']!=source_checksum
            or evidence['result_expected_checksum']!=expected_checksum or evidence['expected_count']!=expected_count
            or evidence['result_expected_checksum']!=evidence['result_actual_checksum']
            or evidence['expected_count']!=evidence['actual_count']):raise ValueError('RELEASE_PORTABILITY_RESULT_MISMATCH')
    return evidence
