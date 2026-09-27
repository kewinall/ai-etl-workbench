from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from xml.etree import ElementTree as ET

import pytest

from app import qa_execution_details
from app.hpl_compiler import compile_hpl
from app.qa_contract import build_qa_context, validate_qa_review, REQUIRED_CHECKS
from app.qa_source_order import inspect_order
from app.result_query_plan import compiled_result_query_plan
from app.result_oracle import compare_oracle_document
from test_comparison_contract import evidence
from test_source_order_compilation import ordered_design


def fixture(monkeypatch, reverse=False):
    spec,run,naming=ordered_design()
    compiled=compile_hpl(spec,run,naming)
    data='類別,金額\nZ,30\nA,10\n'.encode()
    source=run['input_snapshot']['source_config']['sources'][0]
    source.update(upload_id='synthetic',checksum=sha256(data).hexdigest(),size=len(data))
    monkeypatch.setattr(qa_execution_details,'read_verified_upload',lambda *args:data)
    details=qa_execution_details.execution_details(run,compiled,
        dict(source_checksum=source['checksum'],hpl_checksum=compiled['hpl_checksum']))
    doc=dict(version=2,comparison='EXACT_SOURCE_SEQUENCE',ordinal_column='source_position',
        specification_checksum=compiled['specification_checksum'],naming_checksum=naming['checksum'],
        columns=[dict(name='category',kind='TEXT',nullable=False),dict(name='amount',kind='DECIMAL',nullable=False),
                 dict(name='source_position',kind='INTEGER',nullable=False)],
        rows=[dict(category='Z',amount='30',source_position=1),dict(category='A',amount='10',source_position=2)])
    content=json.dumps(doc).encode()
    actual=[{**r,'amount':Decimal(r['amount'])} for r in doc['rows']]
    compared=compare_oracle_document(content,list(reversed(actual)) if reverse else actual,
        document_checksum=sha256(content).hexdigest(),specification_checksum=compiled['specification_checksum'],naming_checksum=naming['checksum'])
    packet={**evidence(),**compared,'run_id':str(run['run_id'])}
    digest=sha256(json.dumps(packet,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    query=compiled_result_query_plan(compiled)
    details['source_order_evidence']=inspect_order(compiled,packet,digest,query['checksum'])
    checks=[dict(id=k,status='PASS',checksum='a'*64,summary='Synthetic test evidence') for k in REQUIRED_CHECKS]
    by_id={c['id']:c for c in checks}
    by_id['static_validation']['checksum']=compiled['hpl_checksum']
    by_id['hop_execution']['checksum']=packet['hop_log_checksum']
    by_id['result_comparison'].update(checksum=digest,status='FAIL' if reverse else 'PASS')
    by_id['result_source']['checksum']=query['checksum']
    semantics=dict(requirement='依來源順序輸出全部列，保留來源序號',
        conditions=run['input_snapshot']['target_config']['requirements_v1'],specification=spec,
        transformation_intent=run['input_snapshot']['target_config']['transformation_contract_v1'],
        nodes=[dict(id=n.findtext('name'),component=n.findtext('type')) for n in ET.fromstring(compiled['hpl']).findall('transform')],
        execution_details=details)
    return compiled,checks,semantics


def build(compiled,checks,semantics):
    return build_qa_context(compiled['specification']['run_id'],compiled['specification_checksum'],checks,semantics)


@pytest.mark.parametrize('reverse',[False,True])
def test_ordered_context_binds_evidence_and_model_cannot_override_failure(monkeypatch,reverse):
    args=fixture(monkeypatch,reverse)
    context=build(*args)
    assert context['version']==13
    assert build_qa_context(context['run_id'],context['specification_checksum'],context['evidence'],context['semantics'])==context
    review={k:context[k] for k in ('run_id','specification_checksum','context_checksum')}
    review.update(version=1,status='PASS',summary='Reviewed synthetic evidence',issues=[],evidence_ids=[*REQUIRED_CHECKS,'semantic_design'])
    if reverse:
        with pytest.raises(ValueError,match='QA_CANNOT_OVERRIDE_FAILURE'):
            validate_qa_review(review,context)
        review.update(status='FAIL',issues=[dict(message='Sequence mismatch',evidence_ids=['result_comparison'])])
    result=validate_qa_review(review,context)
    assert result['qa_approved'] is result['release_ready'] is False


@pytest.mark.parametrize('change',['query','comparison','row_count','source_mapping','sort','missing','status','log'])
def test_order_bindings_cannot_be_substituted(monkeypatch,change):
    compiled,checks,semantics=fixture(monkeypatch)
    details=semantics['execution_details']
    order=details['source_order_evidence']
    if change=='query': order['query_checksum']='0'*64
    elif change=='comparison': order['comparison_checksum']='0'*64
    elif change=='row_count': details['csv_structure_validation']['records_checked']=3
    elif change=='source_mapping': details['compiler_plan']['stages'][0]['ordinal_column']='amount'
    elif change=='sort': details['compiler_plan']['stages'][1]['columns']=['category']
    elif change=='missing': del details['source_order_evidence']
    elif change=='status': next(c for c in checks if c['id']=='result_comparison')['status']='FAIL'
    elif change=='log': next(c for c in checks if c['id']=='hop_execution')['checksum']='0'*64
    with pytest.raises(ValueError): build(compiled,checks,semantics)


@pytest.mark.parametrize('xpath,text',[
    ("./transform[name='source']/rownum_field",'wrong'),
    ("./transform[name='source']/parallel",'Y'),
    ("./transform[name='source']/copies",'2'),
    ("./transform[name='source_order_sort']/fields/field/ascending",'N'),
    ("./transform[name='source_order_sort']/unique_rows",'Y'),
])
def test_native_options_rechecked_even_with_new_hpl_checksum(monkeypatch,xpath,text):
    compiled,_,semantics=fixture(monkeypatch)
    changed=deepcopy(compiled)
    root=ET.fromstring(changed['hpl']); root.find(xpath).text=text
    changed['hpl']=ET.tostring(root,encoding='unicode')
    changed['hpl_checksum']=sha256(changed['hpl'].encode()).hexdigest()
    packet=semantics['execution_details']['source_order_evidence']
    with pytest.raises(ValueError,match='QA_SOURCE_ORDER_OPTIONS_CHANGED'):
        inspect_order(changed,packet['comparison'],packet['comparison_checksum'],packet['query_checksum'])
