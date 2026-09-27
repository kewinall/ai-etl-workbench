"""Version-bound SA input and output validation. No model or execution calls."""
import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .control_worker import check_requirements
from .csv_contract import csv_evidence, csv_sources_evidence


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class SAIssueV1(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    issue_type: Literal['MISSING', 'AMBIGUOUS', 'CONFLICT', 'UNSAFE', 'UNSUPPORTED']
    message: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)


class SAReviewV1(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: Literal[1]
    run_id: str
    input_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    context_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    status: Literal['NEEDS_INPUT', 'READY_FOR_REVIEW']
    summary: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(min_length=1, max_length=200)
    issues: list[SAIssueV1] = Field(max_length=100)


def sa_output_schema(context):
    """Expose only this captured context's citation IDs; validation remains authoritative."""
    schema = SAReviewV1.model_json_schema()
    ids = [item['id'] for item in context['evidence']]
    for node in (schema['properties']['evidence_ids'], schema['$defs']['SAIssueV1']['properties']['evidence_ids']):
        node['items']['enum'] = list(ids)
    return schema


def build_sa_context(run):
    snapshot = run['input_snapshot']
    target = snapshot.get('target_config') or {}
    evidence = [{'id': 'requirement', 'kind': 'REQUIREMENT', 'value': snapshot.get('requirement_text', '')},
                {'id': 'target', 'kind': 'TARGET', 'value': {key: target.get(key) for key in ('schema', 'table')}}]
    # Only known contract fields; no connection metadata, sample data or file paths.
    from .requirement_contract import RequirementConditionsV1
    try:
        conditions = RequirementConditionsV1.model_validate(target.get('requirements_v1') or {}).model_dump()
    except ValueError:
        conditions = {'invalid': True}
    evidence.append({'id': 'conditions', 'kind': 'CONDITIONS', 'value': conditions})
    from .transformation_contract import intent_evidence
    intent = intent_evidence(snapshot)
    if intent is not None:
        evidence.append({'id': 'transformation.conditions', 'kind': 'TRANSFORMATION_CONDITIONS', 'value': intent})
    from .source_order_input import order_evidence
    order = order_evidence(snapshot)
    if order is not None:
        evidence.append({'id':'source_order.conditions','kind':'SOURCE_ORDER_CONDITIONS','value':order})
    from .join_contract import join_evidence
    join_input = join_evidence(snapshot)
    if join_input is not None:
        evidence.append({'id': 'join.conditions', 'kind': 'JOIN_CONDITIONS', 'value': join_input})
    csv_input = csv_evidence(snapshot.get('source_config') or {})
    if csv_input:
        evidence.append({'id': 'source.0.csv_input', 'kind': 'CSV_INPUT', 'value': csv_input})
    multi_csv = csv_sources_evidence(snapshot.get('source_config') or {})
    if multi_csv is not None:
        evidence.append({'id': 'sources.csv_inputs', 'kind': 'CSV_INPUTS', 'value': multi_csv})
    for source_index, source in enumerate((snapshot.get('source_config') or {}).get('sources') or []):
        for field_index, field in enumerate(source.get('fields') or []):
            evidence.append({'id': f'source.{source_index}.field.{field_index}', 'kind': 'SOURCE_FIELD',
                             'value': {key: field.get(key) for key in ('name', 'type')}})
    context = {'version': 4 if order is not None else 3 if intent is not None else 2, 'run_id': str(run['run_id']), 'input_checksum': run['input_checksum'],
               'settings_checksum': run['settings_snapshot']['checksum'], 'evidence': evidence,
               'deterministic_gate': check_requirements(snapshot)}
    return {**context, 'context_checksum': digest(context)}


def validate_sa_review(payload, context):
    review = SAReviewV1.model_validate(payload)
    if (review.run_id != context['run_id'] or review.input_checksum != context['input_checksum']
            or review.context_checksum != context['context_checksum']):
        raise ValueError('SA_VERSION_MISMATCH')
    valid_ids = {item['id'] for item in context['evidence']}
    references = review.evidence_ids + [ref for issue in review.issues for ref in issue.evidence_ids]
    if any(ref not in valid_ids for ref in references):
        raise ValueError('SA_UNKNOWN_EVIDENCE')
    if 'requirement' not in review.evidence_ids:
        raise ValueError('SA_REQUIREMENT_EVIDENCE_REQUIRED')
    if review.status == 'READY_FOR_REVIEW' and (review.issues or context['deterministic_gate']['status'] != 'CHECKED'):
        raise ValueError('SA_CANNOT_OVERRIDE_GATE')
    if review.status == 'READY_FOR_REVIEW' and 'source_order.conditions' in valid_ids and 'source_order.conditions' not in review.evidence_ids:
        raise ValueError('SA_SOURCE_ORDER_EVIDENCE_REQUIRED')
    if review.status == 'NEEDS_INPUT' and not review.issues:
        raise ValueError('SA_MISSING_ISSUE_DETAILS')
    # Citation existence does not establish semantic correctness or authorize execution.
    return review.model_dump()
