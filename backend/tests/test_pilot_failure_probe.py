from copy import deepcopy
from hashlib import sha256
import pytest
from app.pilot_failure_probe import check_scope,SYNTHETIC_CSV


def current():
    return {'binding_checksum':'a'*64,'specification':{'version':1,'target_schema':'ai_sample',
        'target_table':'pilot_missing_column_20260927','output_columns':['record_key','label'],
        'filters':[],'aggregation':None,'write_mode':'APPEND'},'run':{'write_started':False,
        'parent_run_id':None,'input_snapshot':{'source_config':{'sources':[{'checksum':sha256(SYNTHETIC_CSV).hexdigest()}]}}}}


def test_only_fixed_synthetic_new_target():
    assert check_scope(current(),'a'*64)=='pilot_missing_column_20260927'


def test_acceptance_target_requires_explicit_exact_allowance():
    data=current();data['specification']['target_table']='ui_accept_revision_20261011_v1'
    with pytest.raises(ValueError):check_scope(data,'a'*64)
    with pytest.raises(ValueError):check_scope(data,'a'*64,'ui_accept_revision_20261012_v1')
    assert check_scope(data,'a'*64,'ui_accept_revision_20261011_v1')=='ui_accept_revision_20261011_v1'


def test_acceptance_requirement_revision_requires_proven_unexecuted_parents():
    data=current();target='ui_accept_revision_20261011_v1';data['specification']['target_table']=target
    data['run']['parent_run_id']='previous-input'
    with pytest.raises(ValueError):check_scope(data,'a'*64,target)
    with pytest.raises(ValueError):check_scope(data,'a'*64,target,1)
    assert check_scope(data,'a'*64,target,True)==target
    data['run']['write_started']=True
    with pytest.raises(ValueError):check_scope(data,'a'*64,target,True)


def test_legacy_probe_cannot_use_acceptance_parent_exception():
    data=current();data['run']['parent_run_id']='previous-input'
    with pytest.raises(ValueError):check_scope(data,'a'*64,data['specification']['target_table'],True)


@pytest.mark.parametrize('target',['ui_accept_csv_20261011_v2','ui_accept_revision_20261011_v2',
    'ui_accept_revision_20261011_v1;DROP','business','ui_accept_partial_20261011_v1'])
def test_explicit_acceptance_allowance_cannot_expand_target_namespace(target):
    data=current();data['specification']['target_table']=target
    with pytest.raises(ValueError):check_scope(data,'a'*64,target)


@pytest.mark.parametrize('change',['started','child','source','binding'])
def test_acceptance_allowance_still_rejects_replay_or_changed_input(change):
    data=current();target='ui_accept_revision_20261011_v1';data['specification']['target_table']=target
    if change=='started':data['run']['write_started']=True
    if change=='child':data['run']['parent_run_id']='old'
    if change=='source':data['run']['input_snapshot']['source_config']['sources'][0]['checksum']='b'*64
    with pytest.raises(ValueError):check_scope(data,'b'*64 if change=='binding' else 'a'*64,target)


@pytest.mark.parametrize('key,value',[('target_schema','business'),('target_table','other'),
    ('target_table','pilot_missing_column_20260927;DROP'),('version',2),('write_mode','REPLACE'),
    ('output_columns',['label']),('filters',[{}]),('aggregation',{})])
def test_reject_other_specification(key,value):
    data=current();data['specification'][key]=value
    # Empty aggregation object must also be rejected, not treated as no aggregation.
    with pytest.raises(ValueError):check_scope(data,'a'*64)


@pytest.mark.parametrize('change',['started','child','source','binding'])
def test_reject_replay_and_changed_binding(change):
    data=current()
    if change=='started':data['run']['write_started']=True
    if change=='child':data['run']['parent_run_id']='old'
    if change=='source':data['run']['input_snapshot']['source_config']['sources'][0]['checksum']='b'*64
    with pytest.raises(ValueError):check_scope(data,'b'*64 if change=='binding' else 'a'*64)
