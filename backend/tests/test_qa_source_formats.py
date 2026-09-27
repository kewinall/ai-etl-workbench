from copy import deepcopy
from hashlib import sha256
from unittest.mock import Mock
import pytest
from app.qa_source_formats import expected_formats, inspect_formats, should_enrich
from app.qa_contract import build_qa_context
from app import qa_journal
from test_qa_single_source_contract import contexts
from test_qa_multisource import context_fixture


def mask_fixture():
    plan={'stages':[{'component':'CSVInput','id':'source','fields':[
        {'stream_name':'d','data_type':'DATE'}, {'stream_name':'t','data_type':'TIMESTAMP'}]}]}
    xml='<pipeline><transform><name>source</name><type>CSVInput</type><fields>'
    xml+='<field><name>d</name><format>yyyy-MM-dd</format></field>'
    xml+='<field><name>t</name><format>yyyy-MM-dd HH:mm:ss</format></field>'
    xml+='</fields></transform></pipeline>'
    return dict(plan=plan,hpl=xml,hpl_checksum=sha256(xml.encode()).hexdigest())


def test_actual_mask_inspection_and_explicit_limitations():
    c=mask_fixture();r=inspect_formats(c)
    assert r==expected_formats(c['plan'],c['hpl_checksum'])
    assert r['sources'][0]['fields'][0]['format']=='yyyy-MM-dd'
    assert 'not proof of strict rejection' in r['limitation']


@pytest.mark.parametrize('change',['mask','missing','duplicate','checksum'])
def test_mutated_hpl_rejected_even_with_rehashed_xml(change):
    c=mask_fixture()
    if change=='mask':c['hpl']=c['hpl'].replace('yyyy-MM-dd','dd/MM/yyyy')
    if change=='missing':c['hpl']=c['hpl'].replace('<format>yyyy-MM-dd</format>','')
    if change=='duplicate':c['hpl']=c['hpl'].replace('</pipeline>',c['hpl'][10:-11]+'</pipeline>')
    if change!='checksum':c['hpl_checksum']=sha256(c['hpl'].encode()).hexdigest()
    else:c['hpl_checksum']='0'*64
    with pytest.raises(ValueError,match='QA_FORMAT_'):inspect_formats(c)


@pytest.mark.parametrize('multi',[False,True])
def test_context_enrichment_is_exact_and_history_stays_readable(monkeypatch,multi):
    if multi:
        run,c,checks,sem=context_fixture(monkeypatch)
        old=build_qa_context(run['run_id'],c['specification_checksum'],checks,sem)
    else:
        _,old,c,_,_=contexts(monkeypatch)
    sem=deepcopy(old['semantics'])
    sem['execution_details']['source_formats']=inspect_formats(c)
    new=build_qa_context(old['run_id'],old['specification_checksum'],old['evidence'],sem)
    assert (old['version'],new['version'])==((5,8) if multi else (6,7))
    assert build_qa_context(old['run_id'],old['specification_checksum'],old['evidence'],old['semantics'])==old
    assert qa_journal.same_execution_enrichment(old,new)
    record=dict(status='VALIDATED_NOT_APPROVED',prompt_version=6,
        input_json={'context':old,'prompt_checksum':'a'*64})
    monkeypatch.setattr(qa_journal,'public_record',Mock(return_value={'review':{'status':'NEEDS_REVIEW'}}))
    assert qa_journal.can_reassess(record,1,new)
    assert not qa_journal.can_reassess(record,3,new)
    for key in ('requirement','format','evidence'):
        changed=deepcopy(new)
        if key=='requirement':changed['semantics']['requirement']='changed'
        elif key=='format':changed['semantics']['execution_details']['source_formats']['sources'][0]['fields'][0]['format']='wrong'
        else:changed['evidence'][0]['checksum']='0'*64
        assert not qa_journal.same_execution_enrichment(old,changed)


@pytest.mark.parametrize('status,review,expected',[
    ('VALIDATED_NOT_APPROVED','PASS',False),('VALIDATED_NOT_APPROVED','NEEDS_REVIEW',True),
    ('QA_RESERVED',None,False),('QA_OUTCOME_UNKNOWN',None,False)])
def test_no_retroactive_migration_or_inflight_invalidation(status,review,expected):
    row=dict(status=status,input_json={'context':{'version':6}},output_json={'review':{'status':review}})
    assert should_enrich(row) is expected
    assert should_enrich(None)
