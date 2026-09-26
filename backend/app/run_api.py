"""Pilot preparation/review API. No worker dispatch or ETL execution here."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
import os
from .run_queue import RunConflict, RunBlocked
from .requirement_contract import RequirementConditionsV1
from .join_contract import JoinContractV1, join_evidence
from .source_revision import SourceFieldsV1, editable_source
from .source_replacement import CsvReplacementV1
from .csv_contract import (CsvInputContractV1, CsvInputContractsV1, editable_csv_source,
                          csv_evidence, editable_csv_sources, csv_sources_evidence)


class SAAuthorizationIdentity(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent: StrictBool
    input_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    settings_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    context_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    prompt_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    schema_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')


class AuthorizeSA(SAAuthorizationIdentity):
    policy_version: Literal['sa-bounded-v1']
    max_provider_attempts: Literal[4]
    max_output_tokens_per_attempt: Literal[2048]


class AuthorizeCopilot(SAAuthorizationIdentity):
    policy_version: Literal['copilot-cli-once-v1']
    max_cli_sessions: Literal[1]
    automatic_retries: Literal[0]
    token_cap_supported: Literal[False]


class PrepareRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['PREPARE']
    request_key: str = Field(pattern=r'^[A-Za-z0-9_-]{8,120}$')
    ai_profile_id: str | None = Field(default=None, min_length=1, max_length=120)
    connection_id: str | None = Field(default=None, min_length=1, max_length=120)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: UUID
    kind: Literal['INPUT_REVIEW']
    decision: Literal['APPROVE', 'REJECT']
    input_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    settings_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')


class ReviewQA(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: StrictBool
    binding_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')


class PrepareSDMDelivery(BaseModel):
    model_config=ConfigDict(extra='forbid')
    qa_binding_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')


class ReconcileExecution(BaseModel):
    model_config=ConfigDict(extra='forbid')
    binding_checksum: str=Field(pattern=r'^[a-f0-9]{64}$')
    evidence_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    observed_row_count: int=Field(strict=True,ge=0,le=9223372036854775807)
    engine_stopped: StrictBool
    target_checked: StrictBool
    confirmed: StrictBool


class ReviseRun(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_key: str = Field(pattern=r'^[A-Za-z0-9_-]{8,120}$')
    input_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    requirement_text: str = Field(min_length=1, max_length=20000)
    target_schema: str = Field(pattern=r'^[a-z_][a-z0-9_]{0,62}$')
    target_table: str = Field(pattern=r'^[a-z_][a-z0-9_]{0,62}$')
    requirements_v1: RequirementConditionsV1 | None = None
    source_fields_v1: SourceFieldsV1 | None = None
    csv_input_contract_v1: CsvInputContractV1 | None = None
    csv_replacement_v1: CsvReplacementV1 | None = None
    join_contract_v1: JoinContractV1 | None = None
    csv_input_contracts_v1: CsvInputContractsV1 | None = None


def public_run(row):
    keys = ('run_id','task_id','project_id','state','phase','input_checksum','write_started',
            'outcome_code','created_at','updated_at','matches_current','approval','events','gate_result','parent_run_id')
    result = {key: row[key] for key in keys if key in row}
    settings = row['settings_snapshot']
    result['settings_checksum'] = settings['checksum']
    result['settings_summary'] = {key: settings.get(key) for key in ('ai_profile_id','connection_id','origins','model_routes')}
    result['input_summary'] = {key: row['input_snapshot'].get(key) for key in ('requirement_text','source_type','target_type')}
    result['worker_connected'] = None  # Deprecated: authoritative liveness is /api/runtime/workers.
    target = row['input_snapshot'].get('target_config') or {}
    result['input_summary']['target_schema'] = target.get('schema', '')
    result['input_summary']['target_table'] = target.get('table', '')
    result['input_summary']['requirements_v1'] = target.get('requirements_v1')
    join_input = join_evidence(row['input_snapshot'])
    if join_input is not None:
        result['input_summary']['join_contract_v1'] = join_input
    source = row['input_snapshot'].get('source_config') or {}
    result['input_summary']['source_fields_editable'] = editable_source(source)
    result['input_summary']['csv_contract_editable'] = editable_csv_source(source)
    result['input_summary']['csv_input_contract_v1'] = csv_evidence(source)
    multi_csv = csv_sources_evidence(source)
    if multi_csv is not None:
        result['input_summary']['csv_contracts_editable'] = editable_csv_sources(source)
        result['input_summary']['csv_input_contracts_v1'] = multi_csv
    result['input_summary']['source_fields'] = [{key: field.get(key) for key in ('name', 'type')} for item in source.get('sources', []) for field in item.get('fields', [])]
    result['approval_scope'] = 'INPUT_ONLY_NOT_EXECUTION_OR_RELEASE'
    return result


def create_run_router(queue):
    router = APIRouter(prefix='/api/tasks', tags=['Pilot run preparation'])

    def call(action, *args):
        try:
            return action(*args)
        except RunBlocked as exc:
            raise HTTPException(422, detail={'code': 'RUN_SETTINGS_BLOCKED', 'message': '設定尚未完整，請先修正 Pilot 執行準備提示', 'issues': exc.issues}) from None
        except RunConflict as exc:
            raise HTTPException(409, detail={'code': str(exc), 'message': '版本或執行狀態已變更，請重新載入；已开始寫入的工作不可直接取消'}) from None
        except ValueError as exc:
            code = str(exc)
            if code in ('QA_APPROVAL_VERSION_CONFLICT','QA_APPROVAL_CONTEXT_CHANGED','QA_RUN_NOT_APPROVABLE','SDM_QA_VERSION_CONFLICT'):
                raise HTTPException(409,detail={'code':code,'message':'QA 版本或狀態已變更，請重新載入審查結果'}) from None
            if code in ('TASK_NOT_FOUND', 'RUN_NOT_FOUND', 'COMPARISON_RUN_NOT_FOUND'):
                raise HTTPException(404, detail={'code': code, 'message': '找不到指定的 Task 或執行版本'}) from None
            raise HTTPException(422, detail={'code': 'INVALID_RUN_REQUEST', 'message': '執行版本請求不合法'}) from None
        except Exception:
            raise HTTPException(503, detail={'code': 'RUN_STORE_UNAVAILABLE', 'message': '執行紀錄服務不可用，請確認資料庫與 migration'}) from None

    @router.get('/{task_id}/runs')
    def list_runs(task_id: str):
        return {'runs': [public_run(row) for row in call(queue.list_runs, task_id)], 'worker_connected': None}

    @router.post('/{task_id}/runs', status_code=201)
    def prepare(task_id: str, data: PrepareRun):
        overrides = data.model_dump(exclude={'mode','request_key'}, exclude_none=True)
        return public_run(call(queue.enqueue, task_id, data.request_key, overrides))

    @router.get('/{task_id}/runs/{run_id}')
    def get_run(task_id: str, run_id: UUID):
        return public_run(call(queue.detail, task_id, run_id))

    @router.post('/{task_id}/approvals')
    def approve(task_id: str, data: ReviewInput):
        return call(queue.review, task_id, data.run_id, data.input_checksum, data.settings_checksum, data.decision)

    @router.get('/{task_id}/runs/{run_id}/comparisons')
    def comparisons(task_id:str,run_id:UUID):
        from .comparison_store import list_comparisons
        return call(list_comparisons,queue,task_id,run_id)

    @router.get('/{task_id}/runs/{run_id}/reconciliation')
    def read_reconciliation(task_id:str,run_id:UUID):
        from .execution_reconciliation import read
        return call(read,queue,task_id,run_id)

    @router.post('/{task_id}/runs/{run_id}/reconciliation')
    def close_reconciliation(task_id:str,run_id:UUID,data:ReconcileExecution):
        from .execution_reconciliation import close
        return call(lambda:close(queue,task_id,run_id,data.binding_checksum,data.evidence_sha256,data.observed_row_count,
            engine_stopped=data.engine_stopped,target_checked=data.target_checked,confirmed=data.confirmed))

    @router.get('/{task_id}/runs/{run_id}/qa-review')
    def qa_review(task_id:str,run_id:UUID):
        from .qa_journal import QAJournal
        return call(QAJournal(queue).read,task_id,run_id)

    @router.get('/{task_id}/runs/{run_id}/sa-approval')
    def sa_approval(task_id:str,run_id:UUID):
        from .sa_approval import read
        return call(read,queue,task_id,run_id)

    @router.post('/{task_id}/runs/{run_id}/sa-approval')
    def approve_sa_handoff(task_id:str,run_id:UUID,data:ReviewQA):
        from .sa_approval import approve
        return call(lambda:approve(queue,task_id,run_id,data.binding_checksum,confirmed=data.confirmed))

    @router.get('/{task_id}/runs/{run_id}/qa-approval')
    def qa_approval_offer(task_id:str,run_id:UUID):
        from .qa_approval import read_approval
        return call(read_approval,queue,task_id,run_id)

    @router.post('/{task_id}/runs/{run_id}/qa-approval')
    def qa_approve(task_id:str,run_id:UUID,data:ReviewQA):
        from .qa_approval import approve_review
        return call(lambda:approve_review(queue,task_id,run_id,data.binding_checksum,confirmed=data.confirmed))

    @router.post('/{task_id}/runs/{run_id}/sdm-delivery')
    def sdm_delivery(task_id:str,run_id:UUID,data:PrepareSDMDelivery):
        from .sdm_delivery import prepare_sdm_delivery
        return call(prepare_sdm_delivery,queue,task_id,run_id,data.qa_binding_checksum)

    @router.get('/{task_id}/runs/{run_id}/sa-context')
    def sa_context(task_id: str, run_id: UUID):
        from .sa_journal import SAJournal
        run = call(queue.detail, task_id, run_id)
        captured = call(SAJournal(queue).context, task_id, run_id)
        return {'status': 'CONTEXT_ONLY_MODEL_NOT_CALLED', 'matches_current': run['matches_current'],
                **captured, 'execution_authorized': False}

    @router.post('/{task_id}/runs/{run_id}/revisions', status_code=201)
    def revise(task_id: str, run_id: UUID, data: ReviseRun):
        return public_run(call(queue.revise, task_id, run_id, data.request_key, data.input_checksum,
                               data.requirement_text, data.target_schema, data.target_table,
                               data.requirements_v1.model_dump() if data.requirements_v1 else None,
                               data.source_fields_v1.model_dump() if data.source_fields_v1 else None,
                               data.csv_input_contract_v1.model_dump() if data.csv_input_contract_v1 else None,
                               data.csv_replacement_v1.model_dump(mode='json') if data.csv_replacement_v1 else None,
                               data.join_contract_v1.model_dump() if data.join_contract_v1 else None,
                               data.csv_input_contracts_v1.model_dump() if data.csv_input_contracts_v1 else None))

    @router.get('/{task_id}/runs/{run_id}/sa-invocation')
    def sa_invocation(task_id: str, run_id: UUID):
        from .sa_journal import SAJournal
        return call(SAJournal(queue).read, task_id, run_id)

    @router.get('/{task_id}/runs/{run_id}/sa-authorization')
    def sa_authorization(task_id: str, run_id: UUID):
        from .sa_work_queue import authorization_offer
        from .control_worker import check_requirements
        run = call(queue.detail, task_id, run_id)
        eligible = (run['state'] == 'NEEDS_REVIEW' and not run['write_started'] and run['matches_current']
                    and (run.get('approval') or {}).get('decision') == 'APPROVE'
                    and (run.get('gate_result') or {}).get('status') == 'CHECKED'
                    and check_requirements(run['input_snapshot'])['status'] == 'CHECKED')
        return {'dispatch_enabled': os.getenv('WORKBENCH_SA_DISPATCH_ENABLED') == 'true',
                'eligible': eligible, 'authorization': authorization_offer(run),
                'model': run['settings_snapshot']['model_routes']['requirement_gate'],
                'execution_authorized': False}

    @router.post('/{task_id}/runs/{run_id}/sa-authorization', status_code=202)
    def authorize_sa(task_id: str, run_id: UUID, data: AuthorizeSA | AuthorizeCopilot):
        if os.getenv('WORKBENCH_SA_DISPATCH_ENABLED') != 'true':
            raise HTTPException(503, detail={'code': 'SA_DISPATCH_DISABLED', 'message': 'SA 派發尚未啟用；不會呼叫模型'})
        from .sa_work_queue import SAWorkQueue
        return call(SAWorkQueue(queue).enqueue, task_id, run_id, data.model_dump())

    @router.post('/{task_id}/runs/{run_id}/sa-invocation/cancel')
    def cancel_sa(task_id: str, run_id: UUID):
        from .sa_work_queue import SAWorkQueue
        return call(SAWorkQueue(queue).cancel_queued, task_id, run_id)

    # Keep the existing revision route above and cancellation behavior unchanged.

    @router.post('/{task_id}/runs/{run_id}/cancel')
    def cancel(task_id: str, run_id: UUID):
        return public_run(call(queue.cancel_unstarted, task_id, run_id))

    return router
