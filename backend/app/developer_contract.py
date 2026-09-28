"""Version-bound Developer proposal. Models propose supported specs, never XML/SQL."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator
from .etl_specification import EtlSpecificationV1,EtlSpecificationV2,EtlSpecificationV3,EtlSpecificationV4,EtlSpecificationV5,validate_specification
from .sa_contract import build_sa_context,digest
from .sa_approval import load_binding
from .specification_store import context as specification_context
from .run_queue import RunConflict


class DeveloperProposalV1(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    version: Literal[1]
    context_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    summary: str=Field(min_length=1,max_length=4000)
    evidence_ids: list[str]=Field(min_length=1,max_length=200)
    specification: EtlSpecificationV1


class DeveloperProposalV2(DeveloperProposalV1):
    version: Literal[2]
    specification: EtlSpecificationV2

    @field_validator('version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 2:
            raise ValueError('DEVELOPER_PROPOSAL_VERSION_INVALID')
        return value


class DeveloperProposalV3(DeveloperProposalV1):
    version: Literal[3]
    specification: EtlSpecificationV3

    @field_validator('version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 3:
            raise ValueError('DEVELOPER_PROPOSAL_VERSION_INVALID')
        return value


class DeveloperProposalV4(DeveloperProposalV1):
    version: Literal[4]
    specification: EtlSpecificationV4

    @field_validator('version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 4:
            raise ValueError('DEVELOPER_PROPOSAL_VERSION_INVALID')
        return value


class DeveloperProposalV5(DeveloperProposalV1):
    version: Literal[5]
    specification: EtlSpecificationV5

    @field_validator('version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 5:
            raise ValueError('DEVELOPER_PROPOSAL_VERSION_INVALID')
        return value


def proposal_model(context):
    version = context.get('version')
    if type(version) is not int or version not in (1, 2, 3, 4, 5):
        raise ValueError('DEVELOPER_CONTEXT_VERSION_UNSUPPORTED')
    return {1: DeveloperProposalV1, 2: DeveloperProposalV2, 3: DeveloperProposalV3, 4: DeveloperProposalV4, 5: DeveloperProposalV5}[version]


def build_context(run,naming,approval,sa_review):
    if not naming or naming.get('status')!='CONFIRMED' or naming.get('task_id')!=run['task_id']:
        raise RunConflict('DEVELOPER_NAMING_CONFIRMATION_REQUIRED')
    evidence=build_sa_context(run)['evidence']
    target=run['input_snapshot']['target_config']
    value={'version':1,'run_id':str(run['run_id']),'input_checksum':run['input_checksum'],
        'settings_checksum':run['settings_snapshot']['checksum'],
        'sa_approval_id':str(approval['approval_id']),'sa_binding_checksum':approval['binding_checksum'],
        'sa_review':sa_review,'evidence':evidence,
        'naming':{'contract_id':str(naming['contract_id']),'version':naming['version'],'checksum':naming['checksum']},
        'columns':[{key:column.get(key) for key in ('source_name','english_name','vertica_type')}
            for column in naming['contract_json']['columns']],
        'target':{key:target.get(key) for key in ('schema','table')},
        'supported_scope':'ONE_CSV_AND_FILTERS_OPTIONAL_GROUPED_AGGREGATION_EXPLICIT_PROJECTION_APPEND'}
    sources = run['input_snapshot'].get('source_config', {}).get('sources') or []
    if any(source.get('type') == 'JSON' for source in sources):
        from .json_contract_binding import validated_json_contract
        validated_json_contract(run['input_snapshot']['source_config'])
        value.update(version=5, supported_scope='ONE_FLAT_JSON_EXPLICIT_READ_CONTRACT_FILTERS_OPTIONAL_GROUPED_AGGREGATION_APPEND')
    if any(source.get('type') == 'EXCEL' for source in sources):
        from .excel_contract_binding import validated_excel_contract
        validated_excel_contract(run['input_snapshot']['source_config'])
        value.update(version=4, supported_scope='ONE_XLSX_EXPLICIT_READ_CONTRACT_FILTERS_OPTIONAL_GROUPED_AGGREGATION_APPEND')
    if len(sources) > 1:
        if len(sources) != 2:
            raise RunConflict('DEVELOPER_SOURCE_COUNT_UNSUPPORTED')
        value.update(version=2,
            supported_scope='TWO_CSV_EXPLICIT_INNER_OR_LEFT_JOIN_FILTERS_OPTIONAL_GROUPED_AGGREGATION_APPEND')
    if 'source_order_v1' in target:
        from .source_order_input import order_issues
        if order_issues(run['input_snapshot']):
            raise RunConflict('DEVELOPER_SOURCE_ORDER_UNSUPPORTED')
        value.update(version=3,supported_scope='ONE_CSV_FULL_ROW_PROJECTION_WITH_GENERATED_SOURCE_ORDINAL_APPEND')
    return {**value,'context_checksum':digest(value)}


def load_context(queue,conn,task_id,run_id):
    binding=load_binding(queue,conn,task_id,run_id)
    approval=conn.execute('SELECT * FROM platform.sa_handoff_approval WHERE run_id=%s',(run_id,)).fetchone()
    if not approval or approval['binding']!=binding or approval['binding_checksum']!=binding['checksum']:
        raise RunConflict('DEVELOPER_SA_APPROVAL_REQUIRED')
    run,naming=specification_context(queue,conn,task_id,run_id)
    record=conn.execute('SELECT output_json FROM platform.agent_invocation WHERE invocation_id=%s',(binding['invocation_id'],)).fetchone()
    return {'context':build_context(run,naming,approval,record['output_json']['review']),
        'run':run,'naming':naming}


def validate_proposal(payload,captured):
    context=captured['context']
    if digest({k:v for k,v in context.items() if k!='context_checksum'})!=context['context_checksum']:
        raise ValueError('DEVELOPER_CONTEXT_CHANGED')
    source_count = len(captured['run']['input_snapshot'].get('source_config', {}).get('sources') or [])
    ordered='source_order_v1' in (captured['run']['input_snapshot'].get('target_config') or {})
    excel=any(source.get('type')=='EXCEL' for source in captured['run']['input_snapshot'].get('source_config', {}).get('sources') or [])
    json_source=any(source.get('type')=='JSON' for source in captured['run']['input_snapshot'].get('source_config', {}).get('sources') or [])
    expected_version=5 if json_source else 4 if excel else 3 if ordered else source_count
    if source_count not in (1, 2) or (ordered and source_count!=1) or context.get('version') != expected_version:
        raise ValueError('DEVELOPER_CONTEXT_VERSION_MISMATCH')
    proposed=proposal_model(context).model_validate(payload)
    if proposed.context_checksum!=context['context_checksum']:
        raise ValueError('DEVELOPER_CONTEXT_CHANGED')
    valid_ids={item['id'] for item in context['evidence']}
    if 'requirement' not in proposed.evidence_ids or any(ref not in valid_ids for ref in proposed.evidence_ids):
        raise ValueError('DEVELOPER_EVIDENCE_INVALID')
    if context['version'] == 2 and not {'join.conditions', 'sources.csv_inputs'}.issubset(proposed.evidence_ids):
        raise ValueError('DEVELOPER_JOIN_EVIDENCE_REQUIRED')
    if 'transformation.conditions' in valid_ids and 'transformation.conditions' not in proposed.evidence_ids:
        raise ValueError('DEVELOPER_TRANSFORMATION_EVIDENCE_REQUIRED')
    if ordered and ('source_order.conditions' not in valid_ids or 'source_order.conditions' not in proposed.evidence_ids):
        raise ValueError('DEVELOPER_SOURCE_ORDER_EVIDENCE_REQUIRED')
    if excel and ('source.0.excel_input' not in valid_ids or 'source.0.excel_input' not in proposed.evidence_ids):
        raise ValueError('DEVELOPER_EXCEL_INPUT_EVIDENCE_REQUIRED')
    if json_source and ('source.0.json_input' not in valid_ids or 'source.0.json_input' not in proposed.evidence_ids):
        raise ValueError('DEVELOPER_JSON_INPUT_EVIDENCE_REQUIRED')
    checked=validate_specification(proposed.specification.model_dump(mode='json'),captured['run'],captured['naming'])
    if checked['status']!='VALIDATED_NOT_APPROVED':
        raise ValueError('DEVELOPER_SPECIFICATION_INVALID')
    return {'proposal':proposed.model_dump(mode='json'),'specification_checksum':checked['specification_checksum'],
        'status':'VALIDATED_NOT_APPROVED','execution_authorized':False,'release_ready':False}
