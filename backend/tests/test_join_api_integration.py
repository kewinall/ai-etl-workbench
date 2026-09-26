"""Real isolated PostgreSQL/API; no models, Hop or Vertica writes."""
from copy import deepcopy
from uuid import UUID
import pytest
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark
from test_join_semantics import join_design


def test_v2_editor_preview_save_and_approval_preserve_join_semantics(context):
    queue,task,run,spec,naming,api = prepared(context,design_factory=join_design)
    base=f'/api/tasks/{task}/runs/{run["run_id"]}'
    editor=api.get(base+'/specification/editor-context')
    assert editor.status_code == 200,editor.text
    value=editor.json()
    assert value['status']=='EDITOR_CONTEXT_READY',value
    assert value['binding']['version']==2 and value['binding']['joins']==spec['joins']
    assert [c['source_name'] for c in value['source_columns']] == [c['source_name'] for c in naming['contract_json']['columns']]
    for action in ('validate','compile-preview'):
        response=api.post(base+'/specification/'+action,json=spec)
        assert response.status_code==200,response.text
        result=response.json()
        assert result['status']=='VALIDATED_NOT_APPROVED' and not result['execution_authorized']
        if action=='compile-preview':
            assert 'SOURCE_CSV_0' in result['hwf'] and 'SOURCE_CSV_1' in result['hwf']
        wrong=deepcopy(spec);wrong['joins'][0]['join_type']='INNER'
        rejected=api.post(base+'/specification/'+action,json=wrong).json()
        issue=next(i for i in rejected['issues'] if i['code']=='SPEC_JOIN_SEMANTICS_MISMATCH')
        assert issue['node_id']=='join_customers' and issue['field_path']=='joins.0.join_type'
        assert 'hpl' not in rejected
    wrong=deepcopy(spec);wrong['joins'][0]['join_type']='INNER'
    assert api.post(base+'/specifications',json=wrong).json()['status']=='INVALID'
    assert api.get(base+'/specifications').json()['items']==[]
    saved=api.post(base+'/specifications',json=spec)
    assert saved.status_code==200,saved.text
    record=saved.json()
    approved=api.post(base+'/specifications/'+record['specification_id']+'/approve',
                      json={'content_checksum':record['content_checksum']})
    assert approved.status_code==200,approved.text
    history=api.get(base+'/specifications').json()['items']
    assert len(history)==1 and history[0]['spec_json']==spec and history[0]['approval_effective']
    assert not queue.detail(task,run['run_id'])['write_started']
    for change in ({'version':1},{'version':2.0},{'source_refs':['source.0']},{'sql':'SELECT 1'}):
        assert api.post(base+'/specifications',json={**spec,**change}).status_code==422


def test_two_source_authorization_reservation_and_write_guard(context,tmp_path,monkeypatch):
    from app import task_uploads
    from app.execution_authorization import offer,authorize
    from app.execution_preparation import prepare_approved_source
    from app.execution_reservation import reserve
    from app.run_queue import RunConflict
    from oracle_fixture import approved_answer
    monkeypatch.setattr(task_uploads,'ROOT',tmp_path)
    monkeypatch.setattr(task_uploads,'UPLOAD_ROOT',tmp_path/'uploads')
    spec,template,naming=join_design()
    for i,text in enumerate(('客戶編號,名稱\nA,left\n','客戶編號|名稱\nA|right\n')):
        fields=template['input_snapshot']['source_config']['sources'][i]['fields']
        template['input_snapshot']['source_config']['sources'][i]={
            **task_uploads.save_and_profile(f'join{i}.csv',text.encode()),'fields':fields,
            'type':'CSV','has_actual_data':True}
    queue,task,run,spec,naming,api=prepared(context,design_factory=lambda:(spec,template,naming))
    base=f'/api/tasks/{task}/runs/{run["run_id"]}/specifications'
    saved=api.post(base,json=spec).json();sid=UUID(saved['specification_id'])
    assert api.post(base+'/'+str(sid)+'/approve',json={'content_checksum':saved['content_checksum']}).status_code==200
    with pytest.raises(ValueError,match='EXPECTED_RESULT_ORACLE_REQUIRED'):
        with queue.conn() as conn:offer(queue,conn,task,run['run_id'],sid)
    approved_answer(queue,task,run['run_id'],sid,[dict(left_key='A',left_value='left',right_key='A',right_value='right')])
    with queue.conn() as conn:current=offer(queue,conn,task,run['run_id'],sid)
    assert current['binding']['policy_version']=='hop-single-attempt-v3'
    assert set(current['binding']['source_checksums'])=={'source.0','source.1'}
    assert not current['execution_authorized']
    consent=authorize(queue,task,run['run_id'],sid,current['binding_checksum'],True)
    aid=UUID(consent['authorization_id'])
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED','true')
    with prepare_approved_source(queue,task,run['run_id'],sid) as staged:
        binding=staged['binding']
        changes=[]
        for ref in ('source.0','source.1'):
            bad=deepcopy(binding);bad['source_checksums'][ref]='0'*64;changes.append(bad)
        bad=deepcopy(binding);bad.pop('source_checksums');changes.append(bad)
        bad=deepcopy(binding);bad['source_checksum']='0'*64;changes.append(bad)
        for bad in changes:
            with pytest.raises(RunConflict,match='PREPARED_BINDING_CHANGED'):
                reserve(queue,task,run['run_id'],sid,aid,bad)
        reservation=reserve(queue,task,run['run_id'],sid,aid,binding)
        assert reservation['status']=='RESERVED_NOT_STARTED'
        for bad in changes:
            with pytest.raises(RunConflict,match='EXECUTION_BINDING_CHANGED'):
                queue.begin_external_write(run['run_id'],reservation['lease_token'],bad)
        assert not queue.detail(task,run['run_id'])['write_started']
        queue.begin_external_write(run['run_id'],reservation['lease_token'],binding)
        assert queue.detail(task,run['run_id'])['write_started']
        with pytest.raises(RunConflict,match='EXECUTION_AUTHORIZATION_CONSUMED'):
            reserve(queue,task,run['run_id'],sid,aid,binding)
        with pytest.raises(RunConflict):
            queue.begin_external_write(run['run_id'],reservation['lease_token'],binding)
        from app.private_log_store import save_private_log
        from app.execution_oracle import load_execution_oracle
        log=save_private_log(queue,run['run_id'],reservation['lease_token'],b'synthetic control-test log')
        queue.complete_hop(run['run_id'],reservation['lease_token'],dict(status='COMPLETED',exit_code=0,
                           errors=0,log_checksum=log['checksum']))
        pinned=load_execution_oracle(queue,task,run['run_id'])
        assert pinned['status']=='EXECUTION_ORACLE_PINNED_NOT_COMPARED' and not pinned['qa_passed']
        assert pinned['binding_checksum']==current['binding_checksum']
    # This is a control-DB write-start marker, not a real Hop/Vertica run.
