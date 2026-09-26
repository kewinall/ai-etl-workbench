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
