"""Evidence validation for an isolated Hop replay. No HTTP proof submission."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .sa_contract import digest
from .source_binding import source_set_checksum
from .etl_specification import SourceOrderV1


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


class PortabilityEvidenceV3(PortabilityEvidenceV1):
    version: Literal[3]
    comparison: Literal['EXACT_SOURCE_SEQUENCE']
    source_order: SourceOrderV1
    result_query_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    position_mismatch_count: int=Field(strict=True,ge=0,le=0)


class PortabilityEvidenceV4(PortabilityEvidenceV1):
    version: Literal[4]
    source_format: Literal['XLSX']


def validate_portability(row,candidate,source_checksum,*,expected_checksum,expected_count,source_checksums=None,
                         source_order=None,result_query_checksum=None,source_format=None):
    if not row or row['status']!='PASS':raise ValueError('RELEASE_PORTABILITY_REQUIRED')
    ordered=source_order is not None
    if source_format is not None and (source_format!='XLSX' or source_checksums is not None or ordered):
        raise ValueError('RELEASE_PORTABILITY_FORMAT_BINDING_REQUIRED')
    if (ordered and (source_checksums is not None or result_query_checksum is None)) or (not ordered and result_query_checksum is not None):
        raise ValueError('RELEASE_PORTABILITY_ORDER_BINDING_REQUIRED')
    evidence=(PortabilityEvidenceV4 if source_format=='XLSX' else PortabilityEvidenceV3 if ordered else PortabilityEvidenceV2 if source_checksums is not None else PortabilityEvidenceV1).model_validate(row['evidence']).model_dump()
    if ordered and (evidence['source_order']!=SourceOrderV1.model_validate(source_order).model_dump()
                    or evidence['result_query_checksum']!=result_query_checksum):
        raise ValueError('RELEASE_PORTABILITY_ORDER_CHANGED')
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
