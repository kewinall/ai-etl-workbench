from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
import pytest
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from app import task_uploads, execution_preparation


@pytest.mark.parametrize('invalidate', [False, True])
def test_saved_specification_and_upload_prepare_atomically(context, tmp_path, monkeypatch, invalidate):
    monkeypatch.setattr(task_uploads,'ROOT',tmp_path)
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path/'uploads')
    data = '類別,金額\nA,101.25\n'.encode()
    upload = task_uploads.save_and_profile('source.csv',data)
    source = {**upload,'type':'CSV','has_actual_data':True,'fields':[{'name':'類別','type':'VARCHAR(32)'},{'name':'金額','type':'NUMERIC(12,2)'}]}
    queue, task_id, run, spec, naming, api = prepared(context,source)
    base = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved = api.post(base,json=spec).json()
    assert api.post(base+'/'+saved['specification_id']+'/approve',json={'content_checksum':saved['content_checksum']}).status_code == 200
    actual = execution_preparation.stage_csv_source
    folders=[]
    @contextmanager
    def interleaved(*args):
        with actual(*args) as staged:
            folders.append(staged['directory'])
            if invalidate:
                queue.cancel_unstarted(task_id,run['run_id'])
            yield staged
    monkeypatch.setattr(execution_preparation,'stage_csv_source',interleaved)
    if invalidate:
        with pytest.raises(ValueError,match='APPROVED_INPUTS_STALE_OR_INVALID'):
            with execution_preparation.prepare_approved_source(queue,task_id,run['run_id'],UUID(saved['specification_id'])):
                pytest.fail('Cancelled Run cannot yield prepared files')
    else:
        with execution_preparation.prepare_approved_source(queue,task_id,run['run_id'],UUID(saved['specification_id'])) as result:
            assert result['source_path'].read_bytes() == data
            assert result['hpl_path'].exists()
            assert result['binding']['source_checksum'] == upload['checksum']
            assert not result['execution_authorized']
        assert not queue.detail(task_id,run['run_id'])['write_started']
    assert folders and not any(folder.exists() for folder in folders)
    assert Path(upload['path']).read_bytes() == data
