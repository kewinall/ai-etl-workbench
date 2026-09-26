from copy import deepcopy
from hashlib import sha256
from unittest.mock import Mock
import pytest
from app.qa_runtime_options import inspect_options
from app.qa_contract import build_qa_context
from app import qa_journal
from test_qa_multisource import fixture,context_fixture


def test_options_are_from_bound_hpl_and_reference_is_not_run_evidence(monkeypatch):
    _,_,compiled,_=fixture(monkeypatch)
    options=inspect_options(compiled)
    assert options['hpl_checksum']==sha256(compiled['hpl'].encode()).hexdigest()
    assert options['sources'][0]['fields'][0]['trim_type']=='none'
    assert options['target']['ignore_errors']=='N'
    assert options['target']['commit']=='1000'
    assert options['behavior_reference']['scope']=='SEPARATE_ENGINE_PROBES_NOT_THIS_RUN_OR_RUNTIME_VERSION_ATTESTATION'
    assert 'NO_ALL_BATCH_ROLLBACK' in options['atomicity']
    assert 'left-private' not in str(options) and 'password' not in str(options)


@pytest.mark.parametrize('old,new',[
    ('<trim_type>none</trim_type>','<trim_type>both</trim_type>'),
    ('<lazy_conversion>N</lazy_conversion>','<lazy_conversion>Y</lazy_conversion>'),
    ('<ignore_errors>N</ignore_errors>','<ignore_errors>Y</ignore_errors>'),
    ('<commit>1000</commit>','<commit>500</commit>'),
    ('</pipeline>','<transform_error_handling><error/></transform_error_handling></pipeline>')])
def test_inspection_rejects_changed_options_even_with_updated_xml_hash(monkeypatch,old,new):
    _,_,compiled,_=fixture(monkeypatch)
    assert old in compiled['hpl'];compiled['hpl']=compiled['hpl'].replace(old,new)
    compiled['hpl_checksum']=sha256(compiled['hpl'].encode()).hexdigest()
    with pytest.raises(ValueError,match='QA_RUNTIME_'):inspect_options(compiled)


def test_v4_history_and_v5_same_execution_enrichment_are_exact_and_bounded(monkeypatch):
    run,compiled,checks,semantics=context_fixture(monkeypatch)
    old_semantics=deepcopy(semantics);old_semantics['execution_details'].pop('runtime_options')
    previous=build_qa_context(run['run_id'],compiled['specification_checksum'],checks,old_semantics)
    current=build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    assert previous['version']==4 and current['version']==5
    assert build_qa_context(previous['run_id'],previous['specification_checksum'],previous['evidence'],previous['semantics'])==previous
    record=dict(status='VALIDATED_NOT_APPROVED',prompt_version=4,
        input_json={'prompt_checksum':'a'*64,'context':previous})
    monkeypatch.setattr(qa_journal,'public_record',Mock(return_value={'review':{'status':'NEEDS_REVIEW'}}))
    assert qa_journal.can_reassess(record,1,current)
    assert qa_journal.same_execution_enrichment(previous,current)
    assert not qa_journal.can_reassess(record,3,current)
    for path in ('requirement','source_checksum','hpl_checksum','reference'):
        changed=deepcopy(current)
        if path=='requirement':changed['semantics']['requirement']='changed'
        elif path=='reference':changed['semantics']['execution_details']['runtime_options']['behavior_reference']['scope']='THIS_RUN_PASSED'
        else:changed['semantics']['execution_details'][path]='f'*64
        assert not qa_journal.same_execution_enrichment(previous,changed)
    changed=deepcopy(current);changed['evidence'][0]['checksum']='f'*64
    assert not qa_journal.same_execution_enrichment(previous,changed)
