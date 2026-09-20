from decimal import Decimal
from hashlib import sha256
import json
import pytest
from app.result_oracle import compare_oracle_document


def document():
    return {'version':1,'specification_checksum':'a'*64,'naming_checksum':'b'*64,
            'columns':[{'name':'amount','kind':'DECIMAL','nullable':False}],
            'rows':[{'amount':'123456789.123456789'}]}


def compare(doc,**overrides):
    content=json.dumps(doc).encode()
    pins={'document_checksum':sha256(content).hexdigest(),'specification_checksum':'a'*64,'naming_checksum':'b'*64,**overrides}
    return compare_oracle_document(content,[{'amount':Decimal('123456789.123456789')}],**pins)


def test_exact_roundtrip_and_safe_evidence():
    result=compare(document())
    assert result['status']=='MATCH'
    assert result['qa_passed'] is result['release_ready'] is False
    assert '123456789' not in json.dumps(result)


@pytest.mark.parametrize('pin',['document_checksum','specification_checksum','naming_checksum'])
def test_changed_document_or_upstream_version_rejected(pin):
    with pytest.raises(ValueError,match='ORACLE_'):compare(document(),**{pin:'c'*64})


@pytest.mark.parametrize('value',[1.2,True,'NaN','Infinity','1e5',' 1.0'])
def test_decimal_encoding_is_explicit(value):
    doc=document();doc['rows'][0]['amount']=value
    with pytest.raises(ValueError,match='ORACLE_INVALID_DECIMAL'):compare(doc)


def test_unknown_fields_version_and_duplicate_json_rejected():
    doc=document();doc['approved']=True
    with pytest.raises(ValueError,match='ORACLE_INVALID_DOCUMENT'):compare(doc)
    doc=document();doc['version']=True
    with pytest.raises(ValueError,match='ORACLE_UNSUPPORTED_VERSION'):compare(doc)
    content=b'{"version":1,"version":1}'
    with pytest.raises(ValueError,match='ORACLE_DUPLICATE_KEY'):
        compare_oracle_document(content,[],document_checksum=sha256(content).hexdigest(),specification_checksum='a'*64,naming_checksum='b'*64)
