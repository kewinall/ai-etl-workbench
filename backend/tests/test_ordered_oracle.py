from copy import deepcopy
from hashlib import sha256
import json

import pytest

from app.hpl_compiler import compile_hpl
from app.oracle_schema import validate_oracle_schema
from app.result_oracle import compare_oracle_document
from test_comparison_contract import evidence, check
from test_source_order_compilation import ordered_design


def document():
    compiled=compile_hpl(*ordered_design())
    return compiled, dict(version=2, comparison='EXACT_SOURCE_SEQUENCE', ordinal_column='source_position',
        specification_checksum=compiled['specification_checksum'],
        naming_checksum=compiled['specification']['naming']['checksum'],
        columns=[{'name':'category','kind':'TEXT','nullable':False},
                 {'name':'amount','kind':'DECIMAL','nullable':False},
                 {'name':'source_position','kind':'INTEGER','nullable':False}],
        rows=[{'category':'Z','amount':'30','source_position':1},
              {'category':'A','amount':'10','source_position':2}])


def compare(doc, actual):
    content=json.dumps(doc).encode()
    return compare_oracle_document(content,actual,document_checksum=sha256(content).hexdigest(),
        specification_checksum=doc['specification_checksum'],naming_checksum=doc['naming_checksum'])


def test_ordered_oracle_and_public_evidence_preserve_sequence_mismatch():
    from decimal import Decimal
    compiled,doc=document()
    validate_oracle_schema(doc,compiled)
    actual=[{**r,'amount':Decimal(r['amount'])} for r in doc['rows']]
    matched=compare(doc,actual)
    assert matched['version']==2 and matched['status']=='MATCH'
    assert check({**evidence(),**matched})['status']=='MATCH'
    wrong=compare(doc,list(reversed(actual)))
    assert wrong['status']=='MISMATCH'
    assert wrong['missing_count']==wrong['unexpected_count']==0
    assert wrong['position_mismatch_count']==2
    assert check({**evidence(),**wrong})['status']=='MISMATCH'
    assert 'category' not in json.dumps(wrong)
    assert wrong['qa_passed'] is wrong['release_ready'] is False


def test_unordered_answer_cannot_be_bound_to_ordered_specification_or_reverse():
    compiled,doc=document()
    old={k:v for k,v in doc.items() if k not in ('comparison','ordinal_column')}
    old['version']=1
    with pytest.raises(ValueError,match='ORACLE_ORDER_CONTRACT_MISMATCH'):
        validate_oracle_schema(old,compiled)
    legacy=deepcopy(compiled)
    legacy['specification']['version']=1
    with pytest.raises(ValueError,match='ORACLE_ORDER_CONTRACT_MISMATCH'):
        validate_oracle_schema(doc,legacy)


@pytest.mark.parametrize('change', [
    {'comparison':'EXACT_MULTISET'}, {'ordinal_column':None}, {'ordinal_column':'amount'},
    {'ordinal_column':'unknown'}, {'ordinal_column':'source_position;DROP TABLE x'},
])
def test_ordered_document_invalid_contract_rejected(change):
    _,doc=document()
    with pytest.raises(ValueError): compare({**doc,**change},[])


def test_nullable_and_nonsequential_oracle_ordinals_are_rejected():
    compiled,doc=document()
    doc['columns'][-1]['nullable']=True
    with pytest.raises(ValueError): compare(doc,[])
    with pytest.raises(ValueError,match='ORACLE_ORDER_COLUMN_NOT_NULL_REQUIRED'):
        validate_oracle_schema(doc,compiled)
    doc['columns'][-1]['nullable']=False
    doc['rows'].reverse()
    with pytest.raises(ValueError,match='RESULT_EXPECTED_SOURCE_ORDER_INVALID'):
        compare(doc,[])


@pytest.mark.parametrize('change', [
    {'version':1}, {'version':True}, {'position_mismatch_count':True},
    {'position_mismatch_count':-1}, {'position_mismatch_count':3},
    {'position_mismatch_count':0}, {'ordinal_column':'x y'},
    {'comparison':'EXACT_MULTISET'}, {'status':'MATCH'},
])
def test_invalid_persisted_sequence_evidence_rejected_with_valid_checksum(change):
    value={**evidence(),'version':2,'comparison':'EXACT_SOURCE_SEQUENCE',
           'ordinal_column':'source_position','position_mismatch_count':2,
           'expected_count':2,'actual_count':2,'status':'MISMATCH','actual_checksum':'0'*64}
    assert check(value)==value
    with pytest.raises(ValueError,match='COMPARISON_EVIDENCE_INVALID'):
        check({**value,**change})
