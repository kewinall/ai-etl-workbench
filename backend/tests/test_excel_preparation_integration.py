"""Real PostgreSQL consent/preparation; no model or external database writes."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import UUID
import pytest
from app import task_uploads, execution_preparation
from app.excel_profile import selected_profile
from app.excel_contract_binding import validated_excel_contract
from app.execution_authorization import offer, authorize
from app.execution_reservation import reserve
from app.source_binding import expected_prepared_binding
from app.run_queue import RunConflict
from test_run_queue_integration import context, pytestmark
from test_specification_api_integration import prepared
from test_excel_specification import excel_design
from oracle_fixture import approved_answer


def prepared_excel(context, tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    captured = []
    spec, template, naming = excel_design(capture=captured)
    upload = task_uploads.save_and_profile('synthetic.xlsx', captured[0])
    selected = selected_profile(upload['upload_id'], upload['checksum'], upload['size'], '明細', 2)
    config = template['input_snapshot']['source_config']
    config['sources'] = [{**upload, **selected, 'type': 'EXCEL', 'has_actual_data': True}]
    spec['excel_source'] = validated_excel_contract(config)['reference']
    queue, task_id = context
    with queue.conn() as conn:
        conn.execute("UPDATE platform.task SET source_type='EXCEL' WHERE task_id=%s", (task_id,))
    result = prepared(context, design_factory=lambda: deepcopy((spec, template, naming)))
    queue, task_id, run, spec, naming, api = result
    base = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    prefix = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specification/'
    editor = api.get(prefix + 'editor-context').json()
    assert editor['status'] == 'EDITOR_CONTEXT_READY', editor
    assert editor['binding']['version'] == 4
    assert editor['binding']['excel_source'] == spec['excel_source']
    assert editor['execution_authorized'] is False
    for route in ('validate', 'compile-preview'):
        preview = api.post(prefix + route, json=spec)
        assert preview.status_code == 200 and preview.json()['status'] == 'VALIDATED_NOT_APPROVED', preview.text
        assert preview.json()['execution_authorized'] is False
    response = api.post(base, json=spec)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert 'specification_id' in saved, saved
    response = api.post(base + '/' + saved['specification_id'] + '/approve',
                        json={'content_checksum': saved['content_checksum']})
    assert response.status_code == 200, response.text
    return queue, task_id, run, UUID(saved['specification_id']), upload, captured[0]


@pytest.mark.parametrize('invalidate', [False, True])
def test_excel_stage_rechecks_approval_and_cleans_only_private_copy(context, tmp_path, monkeypatch, invalidate):
    queue, task_id, run, sid, upload, content = prepared_excel(context, tmp_path, monkeypatch)
    original = execution_preparation.stage_excel_source
    folders = []
    @contextmanager
    def interleaved(*args):
        with original(*args) as staged:
            folders.append(staged['directory'])
            if invalidate:
                queue.cancel_unstarted(task_id, run['run_id'])
            yield staged
    monkeypatch.setattr(execution_preparation, 'stage_excel_source', interleaved)
    if invalidate:
        with pytest.raises(ValueError, match='APPROVED_INPUTS_STALE_OR_INVALID'):
            with execution_preparation.prepare_approved_source(queue, task_id, run['run_id'], sid):
                pytest.fail('Cancelled approval cannot prepare Excel')
    else:
        with execution_preparation.prepare_approved_source(queue, task_id, run['run_id'], sid) as staged:
            assert staged['source_path'].name == 'source.xlsx'
            assert staged['source_path'].read_bytes() == content
            assert staged['binding']['source_format'] == 'XLSX'
            assert staged['binding']['source_checksum'] == upload['checksum']
            assert 'SOURCE_XLSX' in staged['hpl_path'].read_text()
            assert staged['execution_authorized'] is False
    assert folders and all(not folder.exists() for folder in folders)
    assert Path(upload['path']).read_bytes() == content
    assert not queue.detail(task_id, run['run_id'])['write_started']


def test_excel_format_is_bound_at_consent_reservation_and_final_write_gate(context, tmp_path, monkeypatch):
    queue, task_id, run, sid, upload, content = prepared_excel(context, tmp_path, monkeypatch)
    approved_answer(queue, task_id, run['run_id'], sid,
                    rows=[{'category': 'A', 'total_amount': '150.25', 'row_count': 1}])
    with queue.conn() as conn:
        current = offer(queue, conn, task_id, run['run_id'], sid)
    assert current['binding']['policy_version'] == 'hop-single-attempt-v4'
    assert current['binding']['source_format'] == 'XLSX'
    assert current['binding']['max_attempts'] == 1 and current['binding']['automatic_retry'] is False
    consent = authorize(queue, task_id, run['run_id'], sid, current['binding_checksum'], True)
    aid = UUID(consent['authorization_id'])
    assert authorize(queue, task_id, run['run_id'], sid, current['binding_checksum'], True) == consent
    with execution_preparation.prepare_approved_source(queue, task_id, run['run_id'], sid) as staged:
        binding = staged['binding']
        assert binding == expected_prepared_binding(current['binding'])
        monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
        for changed in ({key: value for key, value in binding.items() if key != 'source_format'},
                        {**binding, 'source_format': 'CSV'}):
            with pytest.raises(RunConflict, match='PREPARED_BINDING_CHANGED'):
                reserve(queue, task_id, run['run_id'], sid, aid, changed)
        claim = reserve(queue, task_id, run['run_id'], sid, aid, binding)
        with pytest.raises(RunConflict, match='EXECUTION_AUTHORIZATION_CONSUMED'):
            reserve(queue, task_id, run['run_id'], sid, aid, binding)
        with pytest.raises(RunConflict, match='EXECUTION_BINDING_CHANGED'):
            queue.begin_external_write(run['run_id'], claim['lease_token'], {**binding, 'source_format': 'CSV'})
        assert queue.detail(task_id, run['run_id'])['write_started'] is False
        # This test records only the DB write-start gate; no executor is called.
        queue.begin_external_write(run['run_id'], claim['lease_token'], binding)
        assert queue.detail(task_id, run['run_id'])['write_started'] is True
    assert Path(upload['path']).read_bytes() == content
