from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.specification_api import create_specification_router
from test_etl_specification import design
import pytest


class UnavailableQueue:
    def conn(self):
        raise RuntimeError('private-host private-password')


@pytest.mark.parametrize('action', ['validate', 'compile-preview'])
def test_storage_failure_is_not_a_valid_design_and_does_not_expose_connection(action):
    app = FastAPI(); app.include_router(create_specification_router(UnavailableQueue()))
    spec, run, _ = design()
    response = TestClient(app).post(f'/api/tasks/{run["task_id"]}/runs/{run["run_id"]}/specification/{action}', json=spec)
    assert response.status_code == 503
    assert 'private' not in response.text
    assert '未保存規格或派發工作' in response.text
