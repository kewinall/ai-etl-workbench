from copy import deepcopy
from unittest.mock import Mock
from xml.etree import ElementTree as ET
import pytest
from app.qa_single_source_contract import expected_contract, inspect_contract, preserve_reviewed_context
from app.qa_execution_details import execution_details
from app.qa_contract import build_qa_context
from app import qa_journal
from test_qa_execution_details import fixture
from test_qa_semantics import sample


def contexts(monkeypatch):
    spec,run,compiled,auth=fixture(monkeypatch)
    details=execution_details(run,compiled,auth)
    packet=expected_contract(spec,details)
    claim=dict(run_id=spec['run_id'],specification_checksum=compiled['specification_checksum'],
               hpl_checksum=compiled['hpl_checksum'],ddl_checksum=packet['target_ddl']['checksum'],
               schema_name=spec['target_schema'],table_name=spec['target_table'],
               settings_checksum=spec['settings_checksum'])
    old,_=sample();checks=deepcopy(old['evidence'])
    next(c for c in checks if c['id']=='static_validation')['checksum']=compiled['hpl_checksum']
    semantics=dict(requirement=run['input_snapshot']['requirement_text'],
        conditions=run['input_snapshot']['target_config']['requirements_v1'],specification=spec,
        nodes=[dict(id=n.findtext('name'),component=n.findtext('type')) for n in ET.fromstring(compiled['hpl']).findall('transform')],
        execution_details=details)
    old=build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    details['single_source_contract']=inspect_contract(compiled,details,claim)
    new=build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    return old,new,compiled,details,claim


def test_bound_single_source_options_header_ddl_and_history(monkeypatch):
    old,new,compiled,details,claim=contexts(monkeypatch)
    assert old['version']==3 and new['version']==6
    assert build_qa_context(old['run_id'],old['specification_checksum'],old['evidence'],old['semantics'])==old
    packet=details['single_source_contract']
    assert packet['runtime_options']['sources'][0]['fields'][0]['trim_type']=='none'
    assert 'CASE_SENSITIVE' in packet['header']['matching']
    assert all(c['nullable'] for c in packet['target_ddl']['columns'])
    assert packet['target_ddl']['primary_key']==[]
    assert 'NOT_CURRENT_CATALOG' in packet['target_ddl']['scope']
    assert qa_journal.same_execution_enrichment(old,new)
    record=dict(status='VALIDATED_NOT_APPROVED',prompt_version=5,
                input_json={'context':old,'prompt_checksum':'a'*64})
    monkeypatch.setattr(qa_journal,'public_record',Mock(return_value={'review':{'status':'NEEDS_REVIEW'}}))
    assert qa_journal.can_reassess(record,1,new)
    assert not qa_journal.can_reassess(record,3,new)


@pytest.mark.parametrize('key',['run_id','specification_checksum','hpl_checksum','ddl_checksum',
                                'schema_name','table_name','settings_checksum'])
def test_changed_claim_is_rejected(monkeypatch,key):
    _,_,compiled,details,claim=contexts(monkeypatch)
    claim[key]='changed'
    with pytest.raises(ValueError,match='DDL_BINDING_CHANGED'):inspect_contract(compiled,details,claim)


@pytest.mark.parametrize('part',['requirement','header','ddl','options','source','evidence'])
def test_enrichment_cannot_rewrite_old_evidence_or_options(monkeypatch,part):
    old,new,_,_,_=contexts(monkeypatch)
    value=deepcopy(new);details=value['semantics']['execution_details'];packet=details['single_source_contract']
    if part=='requirement':value['semantics']['requirement']='changed'
    elif part=='header':packet['header']['matching']='CASE_INSENSITIVE'
    elif part=='ddl':packet['target_ddl']['columns'][0]['nullable']=False
    elif part=='options':packet['runtime_options']['target']['ignore_errors']='Y'
    elif part=='source':details['source_checksum']='f'*64
    else:value['evidence'][0]['checksum']='f'*64
    assert not qa_journal.same_execution_enrichment(old,value)


def test_successful_historical_context_is_not_migrated():
    row=dict(status='VALIDATED_NOT_APPROVED',output_json={'review':{'status':'PASS'}},
             input_json={'context':{'version':3}})
    assert preserve_reviewed_context(row)
    row['output_json']['review']['status']='NEEDS_REVIEW'
    assert not preserve_reviewed_context(row)
    assert not preserve_reviewed_context(None)


def test_ddl_evidence_matches_actual_delivery_compiler(monkeypatch):
    from app.delivery_compiler import compile_delivery_components
    from test_etl_specification import design
    _,_,compiled,details,_=contexts(monkeypatch)
    spec,run,naming=design()
    delivery=compile_delivery_components(spec,run,naming)
    assert details['single_source_contract']['target_ddl']['checksum']==delivery['ddl_checksum']


def test_missing_claim_and_changed_header_binding_are_rejected(monkeypatch):
    _,_,compiled,details,claim=contexts(monkeypatch)
    with pytest.raises(ValueError,match='DDL_BINDING_CHANGED'):inspect_contract(compiled,details,None)
    details['csv_structure_validation']['source_columns_checksum']='0'*64
    with pytest.raises(ValueError,match='SOURCE_COLUMN_BINDING_CHANGED'):inspect_contract(compiled,details,claim)
