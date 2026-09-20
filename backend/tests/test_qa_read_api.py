from uuid import uuid4
import pytest
from test_run_api import client
from app.qa_journal import QAJournal,public_record
from test_qa_contract import sample


def test_qa_read_route_has_no_model_write_entry(monkeypatch):
    value={'invocation':None,'dispatch_available':False,'qa_approved':False,'release_ready':False}
    monkeypatch.setattr(QAJournal,'read',lambda *args:value)
    api=client();url=f'/api/tasks/test/runs/{uuid4()}/qa-review'
    assert api.get(url).json()==value
    assert api.post(url,json={'status':'PASS'}).status_code==405


@pytest.mark.parametrize('error,status',[(ValueError('RUN_NOT_FOUND'),404),(ValueError('private context'),422),(RuntimeError('private host'),503)])
def test_qa_read_errors_do_not_expose_details(monkeypatch,error,status):
    def fail(*args):raise error
    monkeypatch.setattr(QAJournal,'read',fail)
    response=client().get(f'/api/tasks/test/runs/{uuid4()}/qa-review')
    assert response.status_code==status and 'private' not in response.text


def test_changed_history_context_is_rejected():
    _,context,_=sample()
    row={'input_json':{'context':context},'context_checksum':'0'*64,'run_id':context['run_id']}
    with pytest.raises(ValueError,match='QA_HISTORY_INTEGRITY_ERROR'):public_record(row)
