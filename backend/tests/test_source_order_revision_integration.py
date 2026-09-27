from copy import deepcopy
import pytest
from app.control_worker import run_once
from app.run_api import create_run_router
from test_run_queue_integration import context, pytestmark
from test_specification_api_integration import prepared
from test_source_order_compilation import ordered_design


def test_order_revision_persists_via_api_without_mutating_parent_or_reusing_approval(context):
    queue,task_id,parent,_,_,api=prepared(context)
    api.app.include_router(create_run_router(queue))
    old=queue.detail(task_id,parent['run_id'])
    _,template,_=ordered_design()
    target=template['input_snapshot']['target_config']
    body=dict(request_key='source-order-child-01',input_checksum=parent['input_checksum'],
        requirement_text='保留全部來源列與原始順序，新增來源序號並依序號排序驗證',
        target_schema='ai_sample',target_table='ordered_revision',
        source_order_v1=target['source_order_v1'],transformation_contract_v1=target['transformation_contract_v1'])
    url=f'/api/tasks/{task_id}/runs/{parent["run_id"]}/revisions'
    response=api.post(url,json=body)
    assert response.status_code==201,response.text
    child=response.json()
    assert child['input_summary']['source_order_v1']==body['source_order_v1']
    assert api.post(url,json=body).json()['run_id']==child['run_id']
    changed=deepcopy(body);changed['source_order_v1']['ordinal_column']='different_position'
    assert api.post(url,json=changed).status_code==409
    saved=queue.detail(task_id,child['run_id'])
    assert saved['approval'] is None and saved['write_started'] is False
    assert saved['input_checksum']!=old['input_checksum']
    assert saved['input_snapshot']['target_config']['source_order_v1']==body['source_order_v1']
    assert queue.detail(task_id,parent['run_id'])['input_snapshot']==old['input_snapshot']
    assert run_once(queue)['status']=='IDLE'
    queue.review(task_id,child['run_id'],saved['input_checksum'],saved['settings_snapshot']['checksum'],'APPROVE')
    assert run_once(queue)['status']=='CHECKED'
    assert queue.detail(task_id,child['run_id'])['write_started'] is False
