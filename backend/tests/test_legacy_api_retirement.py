"""Retired write routes must return before any repository or execution access."""
import pytest
from fastapi.testclient import TestClient
from app import main


@pytest.mark.parametrize('action', ['run', 'rerun', 'supplement'])
@pytest.mark.parametrize('execution_enabled', ['true', 'false'])
def test_retired_route_has_no_side_effects(monkeypatch, action, execution_enabled):
    class ForbiddenRepository:
        def __getattr__(self, name):
            raise AssertionError(f'Retired route touched repository: {name}')
    monkeypatch.setattr(main, 'repo', ForbiddenRepository())
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', execution_enabled)
    response = TestClient(main.app).post(f'/api/tasks/retired-test/{action}', json={'values': {'amount': 123}})
    assert response.status_code == 410
    assert response.json()['detail']['code'] == 'LEGACY_EXECUTION_RETIRED'
    assert response.json()['detail']['runs_url'] == '/api/tasks/retired-test/runs'


def test_versioned_task_update_preserves_task_and_events(context):
    from app.repository import PostgresRepository, TaskVersionConflict
    queue, task_id = context
    repository = PostgresRepository(queue.url)
    queue.enqueue(task_id, 'legacy-edit-guard')
    before = repository.get_task(task_id)
    with pytest.raises(TaskVersionConflict):
        repository.update_task(task_id, {'name': 'changed name', 'requirement': 'changed requirement', 'operation': 'NEW', 'target_schema': 'ai_sample', 'target_table': 'changed_target', 'model': 'synthetic'})
    assert repository.get_task(task_id) == before


from test_run_queue_integration import context
