from test_run_queue_integration import context
from test_specification_api_integration import prepared,pytestmark


def test_sdm_uses_current_saved_approved_spec(context):
    queue,task_id,run,spec,naming,api=prepared(context)
    base=f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved=api.post(base,json=spec).json();sid=saved['specification_id']
    url=base+'/'+sid+'/sdm-preview'
    assert api.get(url).status_code==409
    assert api.post(base+'/'+sid+'/approve',json={'content_checksum':saved['content_checksum']}).status_code==200
    before=queue.detail(task_id,run['run_id'])
    response=api.get(url);assert response.status_code==200,response.text
    result=response.json()
    assert result==api.get(url).json()
    assert result['specification_id']==sid
    assert result['document']['specification_checksum']==saved['content_checksum']
    assert result['document']['naming']['checksum']==naming['checksum']
    assert [m['target_column'] for m in result['document']['mappings']]==spec['output_columns']
    assert result['qa_passed'] is False and result['release_ready'] is False
    after=queue.detail(task_id,run['run_id'])
    assert before['events']==after['events'] and after['write_started'] is False
    assert api.get(url.replace(task_id,'other-task')).status_code==404
    assert api.post(base,json={**spec,'filters':[]}).status_code==200
    assert api.get(url).status_code==409
