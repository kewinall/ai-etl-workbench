from pathlib import Path
import pytest
from app.sdm_store import save_candidate, download_candidate
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark


def test_candidate_saved_idempotent_download_and_tamper(context, tmp_path, monkeypatch):
    monkeypatch.setenv('WORKBENCH_ARTIFACT_ROOT', str(tmp_path))
    queue, task, run, spec, naming, api = prepared(context)
    run_id = run['run_id']
    base = f'/api/tasks/{task}/runs/{run_id}/specifications'
    saved = api.post(base, json=spec).json()
    sid, checksum = saved['specification_id'], saved['content_checksum']
    assert api.post(base+'/'+sid+'/approve', json={'content_checksum': checksum}).status_code == 200
    try:
        history_url = f'/api/tasks/{task}/runs/{run_id}/sdm-candidates'
        assert api.get(history_url).json()['items'] == []
        with pytest.raises(ValueError, match='SDM_SPECIFICATION_CHANGED'):
            save_candidate(queue, task, run_id, sid, '0'*64, root=tmp_path)
        row = save_candidate(queue, task, run_id, sid, checksum, root=tmp_path)
        assert row['status'] == 'CANDIDATE_NOT_RELEASED'
        assert not row['release_ready'] and not row['qa_passed']
        assert 'file_path' not in row
        endpoint = base+'/'+sid+'/sdm-candidate'
        assert api.post(endpoint, json={'content_checksum': '0'*64}).status_code == 409
        response = api.post(endpoint, json={'content_checksum': checksum})
        assert response.status_code == 200
        assert response.json()['sdm_id'] == str(row['sdm_id'])
        assert 'file_path' not in response.json()
        download = f'/api/tasks/{task}/runs/{run_id}/sdm-candidates/{row["sdm_id"]}/download'
        response = api.get(download)
        assert response.status_code == 200 and response.content.startswith(b'PK')
        assert response.headers['x-sdm-status'] == 'CANDIDATE_NOT_RELEASED'
        assert response.headers['cache-control'] == 'no-store'
        history = api.get(history_url)
        assert history.status_code == 200
        assert len(history.json()['items']) == 1
        assert history.json()['items'][0]['sdm_id'] == str(row['sdm_id'])
        assert 'file_path' not in history.json()['items'][0]
        assert api.get(f'/api/tasks/other-task/runs/{run_id}/sdm-candidates').status_code == 404
        assert save_candidate(queue, task, run_id, sid, checksum, root=tmp_path)['sdm_id'] == row['sdm_id']
        metadata, content = download_candidate(queue, task, run_id, row['sdm_id'], root=tmp_path)
        assert content.startswith(b'PK') and len(content) == metadata['file_size']
        with pytest.raises(ValueError, match='SDM_NOT_FOUND'):
            download_candidate(queue, 'other-task', run_id, row['sdm_id'], root=tmp_path)
        file = next(Path(tmp_path).rglob('*.xlsx'))
        file.write_bytes(b'changed')
        assert api.get(download).status_code == 409
        with pytest.raises(ValueError, match='SDM_FILE_CHANGED_OR_UNAVAILABLE'):
            download_candidate(queue, task, run_id, row['sdm_id'], root=tmp_path)
        with pytest.raises(ValueError, match='SDM_FILE_CHANGED_OR_UNAVAILABLE'):
            save_candidate(queue, task, run_id, sid, checksum, root=tmp_path)
        # Metadata remains available even if the physical file is damaged.
        assert api.get(history_url).json()['items'][0]['sdm_id'] == str(row['sdm_id'])
        # Restore only this test's temporary bytes, then supersede the specification.
        file.write_bytes(content)
        from copy import deepcopy
        revised = deepcopy(spec)
        revised['filters'] = []
        replacement = api.post(base, json=revised)
        assert replacement.status_code == 200
        assert replacement.json()['specification_id'] != sid
        assert api.post(endpoint, json={'content_checksum': checksum}).status_code == 409
        assert api.get(download).content == content
        assert api.get(history_url).json()['items'][0]['sdm_id'] == str(row['sdm_id'])
    finally:
        with queue.conn() as conn:
            conn.execute('DELETE FROM platform.sdm_artifact WHERE task_id=%s', (task,))
