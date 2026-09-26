"""Read/review/authorize Developer work. HTTP requests never invoke providers."""
import os
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .developer_contract import load_context
from .developer_gateway import developer_material
from .developer_journal import DeveloperJournal, checked_trace
from .sa_contract import digest


class AuthorizeDeveloper(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: StrictBool
    context_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    prompt_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    schema_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    model: str = Field(min_length=1, max_length=200)


def read(queue, task_id, run_id):
    with queue.conn() as conn:
        queue.locked_task(conn, task_id)
        run = conn.execute('SELECT * FROM platform.task_run WHERE task_id=%s AND run_id=%s', (task_id, run_id)).fetchone()
        if not run: raise ValueError('RUN_NOT_FOUND')
        row = conn.execute("SELECT * FROM platform.agent_invocation WHERE task_id=%s AND run_id=%s AND role='pilot_developer'", (task_id, run_id)).fetchone()
        try:
            captured = load_context(queue, conn, task_id, run_id)
            context = captured['context']
        except ValueError:
            context = None
        settings = run['settings_snapshot']
        model = settings.get('model_routes', {}).get('etl_specification')
        native = settings['ai']['provider_type'] == 'LOCAL_COPILOT' and bool(model and model.startswith('copilot/'))
        record = None
        if row:
            stored_context = row['input_json']['context']
            if digest({k:v for k,v in stored_context.items() if k != 'context_checksum'}) != row['context_checksum']:
                raise ValueError('DEVELOPER_HISTORY_INTEGRITY_ERROR')
            output = row.get('output_json') or {}
            trace = None
            if row['status'] in ('VALIDATED_NOT_APPROVED', 'STALE_RESULT_NEEDS_REVIEW'):
                if digest(output['proposal']) != output['proposal_checksum']:
                    raise ValueError('DEVELOPER_HISTORY_INTEGRITY_ERROR')
                trace = checked_trace(output['trace'], row, output['proposal'])
            record = {key:row[key] for key in ('status', 'provider', 'model', 'created_at', 'prompt_version', 'context_checksum')}
            record.update(invocation_id=str(row['invocation_id']), proposal=output.get('proposal'),
                          specification=output.get('specification'), usage=trace['usage'] if trace else None,
                          duration_ms=trace['duration_ms'] if trace else None)
        material = developer_material(context or {'version': 1})
        return {'invocation':record, 'context':context, 'model':model,
                'matches_current': bool(context and (not row or context == row['input_json']['context'])),
                'eligible': bool(context and native and not row),
                'dispatch_enabled': os.getenv('WORKBENCH_DEVELOPER_DISPATCH_ENABLED') == 'true',
                'prompt_checksum':material['prompt_checksum'], 'schema_checksum':material['schema_checksum'],
                'execution_authorized':False, 'release_ready':False}


def create_developer_router(queue):
    router = APIRouter(prefix='/api/tasks', tags=['Developer review'])
    def call(fn):
        try: return fn()
        except ValueError as error:
            code = str(error)
            if code in ('TASK_NOT_FOUND', 'RUN_NOT_FOUND'): raise HTTPException(404, detail=code) from None
            raise HTTPException(409, detail='Developer 版本、核准或派發條件已變更，請重新載入') from None

    @router.get('/{task_id}/runs/{run_id}/developer')
    def get_developer(task_id:str, run_id:UUID):
        return call(lambda:read(queue, task_id, run_id))

    @router.post('/{task_id}/runs/{run_id}/developer/authorize')
    def authorize(task_id:str, run_id:UUID, data:AuthorizeDeveloper):
        def action():
            offer = read(queue, task_id, run_id)
            if not offer['dispatch_enabled'] or not offer['context']:
                raise ValueError('DEVELOPER_DISPATCH_DISABLED_OR_BLOCKED')
            if (data.prompt_checksum != offer['prompt_checksum'] or data.schema_checksum != offer['schema_checksum']
                    or data.model != offer['model'] or not data.model.startswith('copilot/')):
                raise ValueError('DEVELOPER_AUTHORIZATION_CHANGED')
            return DeveloperJournal(queue).reserve(task_id, run_id, data.context_checksum, confirmed=data.confirmed)
        return call(action)
    return router
