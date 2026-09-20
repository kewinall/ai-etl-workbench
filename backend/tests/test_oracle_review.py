import json
import pytest
from app import oracle_store


def test_pagination_and_precision(monkeypatch):
    doc={'columns':[{'name':'value','kind':'INTEGER','nullable':True}],
         'rows':[{'value':9223372036854775807},{'value':None},{'value':True}]}
    monkeypatch.setattr(oracle_store,'read_oracle',lambda *args:json.dumps(doc).encode())
    first=oracle_store.review_oracle(None,'t','r','s','o',0,1)
    assert first['rows']==[{'value':'9223372036854775807'}]
    assert first['total_rows']==3 and first['has_more'] is True
    last=oracle_store.review_oracle(None,'t','r','s','o',1,2)
    assert last['rows']==[{'value':None},{'value':'true'}]
    assert last['has_more'] is False and last['qa_passed'] is False


@pytest.mark.parametrize('offset,limit',[(-1,50),(0,101),(0,0),(False,50),(0,True)])
def test_invalid_pagination_rejected_before_decryption(monkeypatch,offset,limit):
    def forbidden(*args):raise AssertionError('must not read')
    monkeypatch.setattr(oracle_store,'read_oracle',forbidden)
    with pytest.raises(ValueError,match='ORACLE_PAGE_INVALID'):
        oracle_store.review_oracle(None,'t','r','s','o',offset,limit)
