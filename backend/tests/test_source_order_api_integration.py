from copy import deepcopy

from test_run_queue_integration import context
from test_specification_api_integration import prepared,pytestmark
from test_source_order_compilation import ordered_design


def test_ordered_public_preview_save_approval_and_no_dispatch(context):
    queue,task,run,spec,naming,api=prepared(context,design_factory=ordered_design)
    base=f'/api/tasks/{task}/runs/{run["run_id"]}'
    before=queue.detail(task,run['run_id'])
    editor=api.get(base+'/specification/editor-context').json()
    assert editor['binding']['source_order']==spec['source_order']
    for action in ('validate','compile-preview'):
        response=api.post(base+'/specification/'+action,json=spec)
        assert response.status_code==200,response.text
        result=response.json()
        assert result['status']=='VALIDATED_NOT_APPROVED',result
        assert not result['execution_authorized']
        assert result['specification']['source_order']==spec['source_order']
        if action=='compile-preview':
            assert '<rownum_field>source_position</rownum_field>' in result['hpl']
            assert '"source_position" BIGINT' in result['ddl']
            assert not result['release_ready'] and not result['qa_passed']
    assert queue.detail(task,run['run_id'])==before
    url=base+'/specifications'
    saved=api.post(url,json=spec).json()
    assert api.post(url,json=spec).json()==saved
    sid=saved['specification_id']
    approval=url+'/'+sid+'/approve'
    assert api.post(approval,json={'content_checksum':'c'*64}).status_code==409
    assert api.post(approval,json={'content_checksum':saved['content_checksum']}).status_code==200
    history=api.get(url).json()['items']
    assert len(history)==1 and history[0]['spec_json']==spec
    assert history[0]['approval_effective'] and not history[0]['execution_authorized']
    for mutation in ('ordinal','omitted_output','downgrade'):
        bad=deepcopy(spec)
        if mutation=='ordinal':bad['source_order']['ordinal_column']='other_position'
        elif mutation=='omitted_output':bad['output_columns'].remove('source_position')
        else:bad['version']=1;bad.pop('source_order')
        result=api.post(url,json=bad).json()
        assert result['status']=='INVALID',result
    assert len(api.get(url).json()['items'])==1
    after=queue.detail(task,run['run_id'])
    assert {**after,'events':before['events']}==before
    with queue.conn() as conn:
        for table in ('hop_artifact','agent_invocation'):
            assert conn.execute(f'SELECT count(*) AS n FROM platform.{table} WHERE task_id=%s',(task,)).fetchone()['n']==0
