from copy import deepcopy
import pytest
from app.qa_target_contract import expected_target, inspect_target, should_enrich
from app.qa_contract import build_qa_context
from app.qa_journal import same_execution_enrichment
from test_qa_multisource import context_fixture


def fixture(monkeypatch):
    run, compiled, checks, sem = context_fixture(monkeypatch)
    details = sem['execution_details']; spec = compiled['specification']
    packet = expected_target(spec,details)
    claim = dict(run_id=spec['run_id'], specification_checksum=compiled['specification_checksum'],
        hpl_checksum=compiled['hpl_checksum'], ddl_checksum=packet['checksum'],
        schema_name=spec['target_schema'],table_name=spec['target_table'],settings_checksum=spec['settings_checksum'])
    return run,compiled,checks,sem,claim


def test_new_evidence_and_old_canonical_context(monkeypatch):
    run,c,checks,sem,claim=fixture(monkeypatch)
    old=build_qa_context(run['run_id'],c['specification_checksum'],checks,sem)
    sem['execution_details']['target_contract']=inspect_target(c,sem['execution_details'],claim)
    new=build_qa_context(run['run_id'],c['specification_checksum'],checks,sem)
    assert new['version']==11 and same_execution_enrichment(old,new)
    assert build_qa_context(old['run_id'],old['specification_checksum'],old['evidence'],old['semantics'])==old
    changed=deepcopy(new);changed['semantics']['requirement']='changed'
    assert not same_execution_enrichment(old,changed)
    changed=deepcopy(new);changed['semantics']['execution_details']['target_contract']['columns'][0]['nullable']=False
    assert not same_execution_enrichment(old,changed)


def test_checksum_matches_delivery_compiler_and_missing_claim_fails(monkeypatch):
    from app.delivery_compiler import compile_delivery_components
    from test_join_semantics import join_design
    run,c,_,sem,claim=fixture(monkeypatch)
    spec,source_run,naming=join_design()
    delivery=compile_delivery_components(spec,source_run,naming)
    assert expected_target(spec,{'output_types':delivery['output_types']})['checksum']==delivery['ddl_checksum']
    with pytest.raises(ValueError,match='DDL_BINDING_CHANGED'):
        inspect_target(c,sem['execution_details'],None)


@pytest.mark.parametrize('field',['run_id','specification_checksum','hpl_checksum','ddl_checksum','schema_name','table_name','settings_checksum'])
def test_claim_tampering_rejected(monkeypatch,field):
    _,c,_,sem,claim=fixture(monkeypatch);claim[field]='wrong'
    with pytest.raises(ValueError,match='DDL_BINDING_CHANGED'):
        inspect_target(c,sem['execution_details'],claim)


@pytest.mark.parametrize('status,review,expected',[
    ('VALIDATED_NOT_APPROVED','PASS',False),('VALIDATED_NOT_APPROVED','NEEDS_REVIEW',True),
    ('QA_RESERVED',None,False),('QA_OUTCOME_UNKNOWN',None,False)])
def test_preserve_prior_pass_and_inflight(status,review,expected):
    record=dict(status=status,input_json={'context':{'semantics':{'execution_details':{}}}},
                output_json={'review':{'status':review}})
    assert should_enrich(record) is expected
    record['input_json']['context']['semantics']['execution_details']['target_contract']={'version':1}
    assert should_enrich(record)
