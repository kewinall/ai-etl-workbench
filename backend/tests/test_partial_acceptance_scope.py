from copy import deepcopy
from hashlib import sha256
import pytest
from app.partial_acceptance_scope import (PROJECT_ID,TARGET,AUTHORIZATION,ROWS,SOURCE,
    SOURCE_SHA256,check_scope,verify_committed_prefix,verified_owner)

TASK='TASK-SYNTHETIC-PARTIAL'
RUN='11111111-1111-4111-8111-111111111111'
BINDING='a'*64
OWNER='b'*64
NONCE='c'*32

def offer():
    return dict(binding_checksum=BINDING,specification=dict(version=1,target_schema='ai_sample',
        target_table=TARGET,write_mode='APPEND',output_columns=['record_key','label'],
        filters=[],aggregation=None),run=dict(project_id=PROJECT_ID,task_id=TASK,run_id=RUN,
        write_started=False,parent_run_id=None,input_snapshot=dict(source_config=dict(sources=[dict(checksum=SOURCE_SHA256)]))))

def owner():
    return dict(Id=OWNER,State=dict(Running=True,Paused=False,Restarting=False,Pid=123),
        HostConfig=dict(RestartPolicy=dict(Name='no')),Config=dict(Labels={
        'workbench.partial.project':PROJECT_ID,'workbench.partial.task':TASK,'workbench.partial.run':RUN,
        'workbench.partial.binding':BINDING,'workbench.partial.target':TARGET,
        'workbench.partial.nonce':NONCE,'workbench.partial.source':SOURCE_SHA256}))

def test_fixed_source_and_full_1001_answer_are_declared_before_execution():
    assert len(ROWS)==1001 and ROWS[0]==(1,'row-0001') and ROWS[-1]==(1001,'row-1001')
    assert SOURCE.count(b'\n')==1002 and sha256(SOURCE).hexdigest()==SOURCE_SHA256
    assert check_scope(offer(),TASK,RUN,BINDING)==TARGET

@pytest.mark.parametrize('key,value',[('project_id','other'),('task_id','old'),('run_id','22222222-2222-4222-8222-222222222222'),('write_started',True),('write_started',0),('parent_run_id','old')])
def test_reject_wrong_context_or_previously_executed_run(key,value):
    data=offer();data['run'][key]=value
    with pytest.raises(ValueError):check_scope(data,TASK,RUN,BINDING)

@pytest.mark.parametrize('key,value',[('version',2),('target_schema','business'),('target_table','ui_accept_revision_20261011_v1'),('write_mode','REPLACE'),('output_columns',['label']),('filters',[{}]),('aggregation',{}),('joins',[{}])])
def test_reject_other_transform_or_target(key,value):
    data=offer();data['specification'][key]=value
    with pytest.raises(ValueError):check_scope(data,TASK,RUN,BINDING)

def test_source_binding_and_boolean_ancestry_are_required():
    data=offer();data['run']['parent_run_id']='input-revision'
    with pytest.raises(ValueError):check_scope(data,TASK,RUN,BINDING,1)
    assert check_scope(data,TASK,RUN,BINDING,True)==TARGET
    data['run']['input_snapshot']['source_config']['sources'][0]['checksum']='d'*64
    with pytest.raises(ValueError):check_scope(data,TASK,RUN,BINDING,True)
    with pytest.raises(ValueError):check_scope(offer(),TASK,RUN,'d'*64)

@pytest.mark.parametrize('rows',[[],ROWS[:999],ROWS,ROWS[:999]+(ROWS[0],),ROWS[:999]+((1000,'wrong'),),ROWS[1:],[(1,)],None])
def test_count_only_or_wrong_partial_rows_do_not_authorize_termination(rows):
    with pytest.raises(ValueError):verify_committed_prefix(rows)

def test_independent_exact_first_batch_can_be_observed_in_any_order():
    assert verify_committed_prefix(list(reversed(ROWS[:1000])))['sum_keys']==500500

def test_exact_live_single_owner_and_explicit_authority_are_required():
    assert verified_owner(owner(),OWNER,TASK,RUN,BINDING,NONCE,AUTHORIZATION)==OWNER
    for authorization in (None,'authorized-v2-revision-20261011','yes'):
        with pytest.raises(ValueError):verified_owner(owner(),OWNER,TASK,RUN,BINDING,NONCE,authorization)
    with pytest.raises(ValueError):verified_owner(owner(),'named-worker',TASK,RUN,BINDING,NONCE,AUTHORIZATION)

@pytest.mark.parametrize('key,value',[('Running',False),('Running',1),('Paused',True),('Restarting',True),('Pid',0),('Pid',True)])
def test_missing_or_dead_owner_is_not_a_live_wait(key,value):
    data=owner();data['State'][key]=value
    with pytest.raises(ValueError):verified_owner(data,OWNER,TASK,RUN,BINDING,NONCE,AUTHORIZATION)

@pytest.mark.parametrize('key',list(owner()['Config']['Labels']))
def test_other_task_or_rebound_container_cannot_be_killed(key):
    data=owner();data['Config']['Labels'][key]='different'
    with pytest.raises(ValueError):verified_owner(data,OWNER,TASK,RUN,BINDING,NONCE,AUTHORIZATION)

def test_restart_policy_or_handle_change_is_rejected():
    data=owner();data['HostConfig']['RestartPolicy']['Name']='always'
    with pytest.raises(ValueError):verified_owner(data,OWNER,TASK,RUN,BINDING,NONCE,AUTHORIZATION)
    data=owner();data['Id']='d'*64
    with pytest.raises(ValueError):verified_owner(data,OWNER,TASK,RUN,BINDING,NONCE,AUTHORIZATION)
