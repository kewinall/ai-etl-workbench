from copy import deepcopy
from hashlib import sha256
import pytest
from app.pilot_scenario import ancestors,sources_match,semantic_proof,gap_proof
from app.pilot_fixture_catalog import corpus
from app.sa_contract import digest
from app.pilot_scenario import recovery_proof
from unittest.mock import Mock


def frozen(key):return next(c for c in corpus() if c['definition']['case_key']==key)


def test_lineage_excludes_unrelated_branches():
    runs=[{'run_id':'a','parent_run_id':None},{'run_id':'unrelated','parent_run_id':None},
          {'run_id':'b','parent_run_id':'a'}]
    assert [r['run_id'] for r in ancestors(runs)]==['b','a']


@pytest.mark.parametrize('runs',[
    [{'run_id':'a','parent_run_id':'missing'}],
    [{'run_id':'a','parent_run_id':'b'},{'run_id':'b','parent_run_id':'a'}]])
def test_invalid_lineage_denied(runs):
    with pytest.raises(ValueError):ancestors(runs)


def test_sources_need_recorded_byte_verification_not_claimed_hash_only():
    fixed=frozen('success-null-group');s=fixed['fixture']['sources'][0];checksum=sha256(s['content'].encode()).hexdigest()
    run={'input_snapshot':{'source_config':{'sources':[{'checksum':checksum,'fields':[{'name':n,'type':t} for n,t in s['fields']]}]}},
         'gate_result':{'source_evidence':[{'source_ref':'source.0','status':'UPLOAD_BYTES_VERIFIED','content_checksum':checksum}]}}
    assert sources_match(run,fixed)
    run['gate_result']['source_evidence']=[]
    assert not sources_match(run,fixed)


def semantic():
    run={'run_id':'parent','write_started':False,'input_checksum':'i','settings_snapshot':{'checksum':'s'}}
    packet={'version':1,'input_checksum':'i','settings_checksum':'s','specification_saved':False,'execution_authorized':False,
            'issues':[{'field_path':'filters.0.operator','expected':'GE','actual':'GT','node_id':'filter','requirement_path':'intent.filter'}]}
    packet['attempt_checksum']=digest(packet)
    return run,[{'event_id':10,'event_type':'SPECIFICATION_SEMANTIC_REJECTED','event_context':packet}]


def test_semantic_exact_frozen_defect_and_hash_required():
    run,events=semantic()
    assert semantic_proof(run,events,'semantic-filter-aggregate')['event_id']==10
    events[0]['event_context']['issues'][0]['actual']='LE'
    assert semantic_proof(run,events,'semantic-filter-aggregate') is None
    packet=events[0]['event_context'];packet['attempt_checksum']=digest({k:v for k,v in packet.items() if k!='attempt_checksum'})
    assert semantic_proof(run,events,'semantic-filter-aggregate') is None


@pytest.mark.parametrize('change',['write','event','input','settings','node'])
def test_semantic_wrong_binding_or_started_write_denied(change):
    run,events=semantic()
    if change=='write':run['write_started']=True
    elif change=='event':events.append({'event_id':11,'event_type':'WRITE_STARTED','event_context':{}})
    elif change=='input':run['input_checksum']='changed'
    elif change=='settings':run['settings_snapshot']['checksum']='changed'
    else:
        packet=events[0]['event_context'];packet['issues'][0]['node_id']=''
        packet['attempt_checksum']=digest({k:v for k,v in packet.items() if k!='attempt_checksum'})
    assert semantic_proof(run,events,'semantic-filter-aggregate') is None


def test_gap_requires_original_missing_value_specific_issue_and_no_write():
    fixed=frozen('gap-filter-aggregate')
    run={'run_id':'parent','write_started':False,'input_snapshot':{'source_config':{},'target_config':{'requirements_v1':{'write_mode':None}}},
         'gate_result':{'status':'NEEDS_INPUT','issues':[{'field_path':'requirements_v1.write_mode'}]}}
    events=[{'event_id':2,'event_type':'REQUIREMENT_NEEDS_INPUT'}]
    assert gap_proof(run,events,fixed)['event_id']==2
    bad=deepcopy(run);bad['input_snapshot']['target_config']['requirements_v1']['write_mode']='APPEND'
    assert gap_proof(bad,events,fixed) is None
    bad=deepcopy(run);bad['gate_result']['issues'][0]['field_path']='unrelated'
    assert gap_proof(bad,events,fixed) is None


@pytest.mark.parametrize('mutation',[None,'same_target','unknown','log','hash','order','reconciliation','dispatch'])
def test_recovery_requires_bound_failure_reconciliation_and_distinct_target(monkeypatch,mutation):
    fixed=frozen('recovery-null-group')
    run={'run_id':'r','state':'FAILED','outcome_code':'HOP_EXECUTION_FAILED','write_started':True,
         'input_checksum':'input','input_snapshot':{'target_config':{'schema':'ai_sample','table':'old'}}}
    latest={'input_snapshot':{'target_config':{'schema':'ai_sample','table':'new'}}}
    packet={'run_id':'r','outcome':'HOP_EXECUTION_FAILED','engine_stopped':True,
            'observed_row_count':0,'columns':['category_missing_fault','row_count']}
    packet['checksum']=digest(packet)
    events=[{'event_id':1,'event_type':'SYNTHETIC_MISSING_COLUMN_INJECTED','event_context':{
        'case_key':'recovery-null-group','column':'category','renamed_to':'category_missing_fault','original_hpl_unchanged':True,'binding_checksum':'dispatch'}},
        {'event_id':2,'event_type':'HOP_EXECUTION_FAILED','event_context':{'exit_code':1,'errors':1,'log_checksum':'log'}},
        {'event_id':3,'event_type':'SYNTHETIC_FAILURE_TARGET_OBSERVED','event_context':packet},
        {'event_id':4,'event_type':'OPERATOR_RECONCILED_WITHOUT_RETRY','event_context':{'reconciliation_id':'closed'}}]
    closed={'reconciliation_id':'closed','evidence_sha256':packet['checksum'],'observed_row_count':0,'binding':{'input_checksum':'input'}}
    conn=Mock();conn.execute.return_value.fetchone.side_effect=[closed,{'binding_checksum':'dispatch'}]
    monkeypatch.setattr('app.private_log_store.read_private_log',lambda *args:b'private')
    monkeypatch.setattr('app.execution_diagnosis.diagnose',lambda *args:{'findings':[{'code':'COLUMN_NOT_FOUND','line_numbers':[12]}]})
    if mutation=='same_target':latest=deepcopy(run)
    elif mutation=='unknown':run['outcome_code']='HOP_RESULT_UNKNOWN'
    elif mutation=='log':monkeypatch.setattr('app.execution_diagnosis.diagnose',lambda *args:{'findings':[]})
    elif mutation=='hash':packet['checksum']='changed'
    elif mutation=='order':events[0]['event_id']=9
    elif mutation=='reconciliation':closed['evidence_sha256']='changed'
    elif mutation=='dispatch':events[0]['event_context']['binding_checksum']='changed'
    proof=recovery_proof(None,conn,'task',run,events,fixed,latest)
    assert (proof is not None)==(mutation is None)
