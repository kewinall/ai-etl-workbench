"""Evidence-bound QA advice. Neither model PASS nor this validator grants release."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .sa_contract import digest
from .etl_specification import EtlSpecificationV1
from .requirement_contract import RequirementConditionsV1
from .csv_contract import CsvInputContractV1

REQUIRED_CHECKS=('specification','static_validation','hop_execution','result_comparison','result_source')


class QANodeV1(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: str=Field(min_length=1,max_length=120)
    component: str=Field(min_length=1,max_length=120)


class QAExecutionDetailsV1(BaseModel):
    model_config=ConfigDict(extra='forbid')
    csv_input_contract: CsvInputContractV1
    compiler_plan: dict
    output_types: dict[str,str]
    hpl_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    source_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    csv_structure_validation: dict
    validation_scope: Literal['SAME_EXECUTED_BYTES_RECHECKED_NO_ETL_REPLAY']
    extra_columns_enforcement: Literal['WHOLE_BATCH_VALIDATION_BEFORE_HOP']


class QASemanticsV1(BaseModel):
    model_config=ConfigDict(extra='forbid')
    requirement: str=Field(min_length=1,max_length=20000)
    conditions: RequirementConditionsV1
    specification: EtlSpecificationV1
    nodes: list[QANodeV1]=Field(min_length=1,max_length=200)
    execution_details: QAExecutionDetailsV1 | None=None


class QACheckV1(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    id: Literal['specification','static_validation','hop_execution','result_comparison','result_source']
    status: Literal['PASS','FAIL','MISSING']
    checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    summary: str=Field(min_length=1,max_length=2000)


class QAIssueV1(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    message: str=Field(min_length=1,max_length=2000)
    evidence_ids: list[str]=Field(min_length=1,max_length=20)


class QAReviewV1(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    version: Literal[1]
    run_id: str
    context_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    specification_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    status: Literal['PASS','FAIL','NEEDS_REVIEW']
    summary: str=Field(min_length=1,max_length=4000)
    evidence_ids: list[str]=Field(min_length=1,max_length=20)
    issues: list[QAIssueV1]=Field(max_length=50)


def build_qa_context(run_id,specification_checksum,checks,semantics=None):
    """Trusted controller supplies deterministic checks, not an HTTP client/model."""
    from uuid import UUID
    import re
    identity=str(UUID(str(run_id)))
    if not isinstance(specification_checksum,str) or not re.fullmatch('[a-f0-9]{64}',specification_checksum):
        raise ValueError('QA_SPECIFICATION_CHECKSUM_REQUIRED')
    values=[QACheckV1.model_validate(check).model_dump() for check in checks]
    ids=[value['id'] for value in values]
    if len(ids)!=len(set(ids)) or set(ids)!=set(REQUIRED_CHECKS):
        raise ValueError('QA_REQUIRED_CHECKS_MISSING_OR_DUPLICATED')
    values.sort(key=lambda value:REQUIRED_CHECKS.index(value['id']))
    context={'version':1,'run_id':identity,'specification_checksum':specification_checksum,'evidence':values}
    if semantics is not None:
        value=QASemanticsV1.model_validate(semantics).model_dump(mode='json')
        # Keep historic v2 JSON/checksums byte-for-byte compatible.
        if value['execution_details'] is None:value.pop('execution_details')
        if value['specification']['run_id']!=identity or digest(value['specification'])!=specification_checksum:
            raise ValueError('QA_SEMANTIC_SPECIFICATION_CHANGED')
        if len({node['id'] for node in value['nodes']})!=len(value['nodes']):
            raise ValueError('QA_SEMANTIC_NODES_DUPLICATED')
        details=value.get('execution_details')
        if details:
            plan=details['compiler_plan'];csv=details['csv_structure_validation']
            static=next(check for check in values if check['id']=='static_validation')
            nodes={node['id']:node['component'] for node in value['nodes']}
            if (plan.get('specification_checksum')!=specification_checksum
                    or plan.get('naming_checksum')!=value['specification']['naming']['checksum']
                    or set(details['output_types'])!=set(value['specification']['output_columns'])
                    or details['hpl_checksum']!=static['checksum']
                    or csv.get('content_checksum')!=details['source_checksum']
                    or csv.get('contract_checksum')!=digest(details['csv_input_contract'])
                    or csv.get('status')!='CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE'
                    or csv.get('complete') is not True or csv.get('issues')
                    or not plan.get('stages')
                    or any(nodes.get(stage.get('id'))!=stage.get('component') for stage in plan['stages'])):
                raise ValueError('QA_EXECUTION_DETAILS_BINDING_CHANGED')
        context.update(version=3 if 'execution_details' in value else 2,semantics=value)
    return {**context,'context_checksum':digest(context)}


def validate_qa_review(payload,context):
    if digest({key:value for key,value in context.items() if key!='context_checksum'})!=context.get('context_checksum'):
        raise ValueError('QA_CONTEXT_CHANGED')
    canonical=build_qa_context(context['run_id'],context['specification_checksum'],context['evidence'],context.get('semantics'))
    if canonical!=context:raise ValueError('QA_CONTEXT_CHANGED')
    review=QAReviewV1.model_validate(payload)
    if any(getattr(review,key)!=context[key] for key in ('run_id','specification_checksum','context_checksum')):
        raise ValueError('QA_VERSION_MISMATCH')
    references=review.evidence_ids+[ref for issue in review.issues for ref in issue.evidence_ids]
    required=(*REQUIRED_CHECKS,'semantic_design') if context['version']>=2 else REQUIRED_CHECKS
    valid_refs=set(required)
    if context['version']>=2:valid_refs.update('node.'+node['id'] for node in context['semantics']['nodes'])
    if any(ref not in valid_refs for ref in references):raise ValueError('QA_UNKNOWN_EVIDENCE')
    failed={item['id'] for item in context['evidence'] if item['status']=='FAIL'}
    missing={item['id'] for item in context['evidence'] if item['status']=='MISSING'}
    if failed and review.status!='FAIL':raise ValueError('QA_CANNOT_OVERRIDE_FAILURE')
    if review.status=='PASS' and (missing or review.issues or not set(required).issubset(review.evidence_ids)):
        raise ValueError('QA_PASS_REQUIRES_COMPLETE_EVIDENCE')
    if review.status!='PASS' and not review.issues:raise ValueError('QA_ISSUE_DETAILS_REQUIRED')
    issue_refs={ref for issue in review.issues for ref in issue.evidence_ids}
    if not failed.union(missing).issubset(issue_refs):raise ValueError('QA_BLOCKER_CITATIONS_REQUIRED')
    return {**review.model_dump(),'advisory_only':True,'qa_approved':False,'release_ready':False}
