"""Real isolated PostgreSQL/API guards, not model/Hop acceptance."""
from copy import deepcopy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.run_api import create_run_router
from app.control_worker import run_once
from test_run_queue_integration import context, pytestmark
from test_specification_api_integration import prepared
from test_transformation_contract import confirmed, intent


@pytest.mark.parametrize('mutation', ['operator', 'constant', 'count'])
def test_api_refuses_semantic_mutation_before_save_compile_or_write(context, mutation):
    queue, task, run, spec, naming, api = prepared(context, design_factory=confirmed)
    wrong = deepcopy(spec)
    if mutation == 'operator': wrong['filters'][0]['operator'] = 'GE'
    elif mutation == 'constant': wrong['filters'][0]['constant']['value'] = '20.00'
    else: wrong['aggregation']['metrics'][1].update(function='COUNT_NON_NULL', column='category')
    base = f'/api/tasks/{task}/runs/{run["run_id"]}'
    for path in ('/specification/validate', '/specification/compile-preview', '/specifications'):
        response = api.post(base + path, json=wrong)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['status'] == 'INVALID' and not result['execution_authorized']
        assert any(i['code'] == 'SPEC_TRANSFORMATION_INTENT_MISMATCH' for i in result['issues'])
        assert 'hpl' not in result and 'specification_id' not in result
    assert not queue.detail(task, run['run_id'])['write_started']
    with queue.conn() as conn:
        assert conn.execute('SELECT count(*) AS n FROM platform.specification WHERE task_id=%s', (task,)).fetchone()['n'] == 0


def test_revision_api_preserves_old_intent_and_requires_new_approval(context):
    queue, task, parent, spec, naming, _ = prepared(context, design_factory=confirmed)
    app = FastAPI(); app.include_router(create_run_router(queue)); api = TestClient(app)
    new = intent(); new['filters'][0]['constant']['value'] = '200.00'
    base = f'/api/tasks/{task}/runs'
    body = dict(request_key='intent-revision-child', input_checksum=parent['input_checksum'],
                requirement_text='confirmed threshold greater than 200', target_schema='ai_sample', target_table='totals',
                transformation_contract_v1=new)
    response = api.post(f'{base}/{parent["run_id"]}/revisions', json=body)
    assert response.status_code == 201, response.text
    child = response.json()
    assert child['input_summary']['transformation_contract_v1'] == new
    assert api.post(f'{base}/{parent["run_id"]}/revisions', json=body).json()['run_id'] == child['run_id']
    assert child['input_checksum'] != parent['input_checksum']
    detail = queue.detail(task, child['run_id'])
    assert detail['approval'] is None and not detail['write_started']
    assert run_once(queue)['status'] == 'IDLE'
    previous = queue.detail(task, parent['run_id'])
    assert previous['input_snapshot']['target_config']['transformation_contract_v1'] == intent()
    assert previous['state'] == 'CANCELLED'
    body['transformation_contract_v1']['filters'][0]['operator'] = 'GE'
    assert api.post(f'{base}/{parent["run_id"]}/revisions', json=body).status_code == 409
