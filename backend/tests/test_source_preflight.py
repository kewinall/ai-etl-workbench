from app import task_uploads
from app.control_worker import run_once
from test_control_worker import Queue


def test_worker_binds_actual_bytes_and_blocks_tamper(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    upload = task_uploads.save_and_profile('test.csv', b'id\n1\n')
    source = {**upload, 'type': 'CSV', 'has_actual_data': True}
    snapshot = dict(requirement_text='Synthetic', source_type='CSV',
                    source_config={'sources': [source], 'csv_input_contract_v1': {
                        'version': 1, 'encoding': 'UTF-8', 'delimiter': ',',
                        'header': True, 'extra_columns': 'REJECT'}},
                    target_config={'schema': 'ai_sample', 'table': 'synthetic',
                                   'requirements_v1': {'version': 1, 'write_mode': 'APPEND', 'date_scope': 'ALL'}})
    queue = Queue(snapshot)
    assert run_once(queue)['status'] == 'CHECKED'
    assert queue.result['source_evidence'][0]['csv']['complete']
    (tmp_path / upload['upload_id'] / 'source.csv').write_bytes(b'id\n2\n')
    queue = Queue(snapshot)
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    assert queue.result['source_evidence'][0]['status'] == 'UPLOAD_CONTENT_CHANGED'
    assert str(tmp_path) not in str(queue.result)


def test_legacy_upload_without_binding_is_blocked():
    queue = Queue({'source_config': {'sources': [{'type': 'CSV', 'path': 'private-path', 'has_actual_data': True}]}})
    assert run_once(queue)['status'] == 'NEEDS_INPUT'
    assert queue.result['source_evidence'][0]['status'] == 'UPLOAD_BINDING_INVALID'
    assert 'private-path' not in str(queue.result)
