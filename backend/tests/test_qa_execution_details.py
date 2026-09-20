from hashlib import sha256
from copy import deepcopy
import pytest
import app.qa_execution_details as module
from app.hpl_compiler import compile_hpl
from app.qa_contract import build_qa_context, validate_qa_review
from test_etl_specification import design
from test_qa_semantics import sample


def fixture(monkeypatch, content=None):
    spec,run,naming=design()
    data=content or '類別,金額\nA,101.25\na,110.00\n'.encode()
    source=run['input_snapshot']['source_config']['sources'][0]
    source.update(upload_id='test-only',checksum=sha256(data).hexdigest(),size=len(data))
    monkeypatch.setattr(module,'read_verified_upload',lambda *args:data)
    compiled=compile_hpl(spec,run,naming)
    auth=dict(source_checksum=source['checksum'],hpl_checksum=compiled['hpl_checksum'])
    return spec,run,compiled,auth


def test_parser_case_sensitivity_types_and_order_are_transferred_without_rows(monkeypatch):
    _,run,compiled,auth=fixture(monkeypatch)
    value=module.execution_details(run,compiled,auth)
    assert value['csv_input_contract']['extra_columns']=='REJECT'
    assert value['csv_structure_validation']['records_checked']==2
    assert value['output_types']['total_amount']=='NUMERIC(18,2)'
    stages=value['compiler_plan']['stages']
    assert next(x for x in stages if x['id']=='sort')['case_sensitive'] is True
    assert [x['id'] for x in stages].index('filter')<[x['id'] for x in stages].index('aggregate')
    assert '101.25' not in str(value) and 'test-only' not in str(value)
    assert value['source_checksum']==auth['source_checksum']


def test_mismatched_executed_source_is_blocked_before_read(monkeypatch):
    _,run,compiled,auth=fixture(monkeypatch);auth['source_checksum']='0'*64
    with pytest.raises(ValueError,match='BINDING_CHANGED'):module.execution_details(run,compiled,auth)


def test_extra_csv_columns_block_semantic_evidence(monkeypatch):
    _,run,compiled,auth=fixture(monkeypatch,'類別,金額\nA,101.25,unexpected\n'.encode())
    with pytest.raises(ValueError,match='NO_LONGER_VERIFIABLE'):module.execution_details(run,compiled,auth)


def test_old_context_is_unchanged_and_new_details_require_semantic_review(monkeypatch):
    old,review=sample(); preserved=deepcopy(old)
    assert build_qa_context(old['run_id'],old['specification_checksum'],old['evidence'],old['semantics'])==preserved
    spec,run,compiled,auth=fixture(monkeypatch)
    from xml.etree import ElementTree as ET
    checks=deepcopy(old['evidence'])
    for item in checks:
        if item['id']=='static_validation':item['checksum']=compiled['hpl_checksum']
    semantics=dict(requirement=run['input_snapshot']['requirement_text'],
        conditions=run['input_snapshot']['target_config']['requirements_v1'],specification=spec,
        nodes=[dict(id=n.findtext('name'),component=n.findtext('type')) for n in ET.fromstring(compiled['hpl']).findall('transform')],
        execution_details=module.execution_details(run,compiled,auth))
    current=build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    assert current['version']==3 and current['context_checksum']!=old['context_checksum']
    with pytest.raises(ValueError,match='VERSION_MISMATCH'):validate_qa_review(review,current)
    semantics['execution_details']['compiler_plan']['naming_checksum']='0'*64
    with pytest.raises(ValueError,match='DETAILS_BINDING_CHANGED'):
        build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
