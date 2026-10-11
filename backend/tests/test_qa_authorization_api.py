from unittest.mock import Mock
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import app.qa_authorization_api as module


def fixture(monkeypatch):
    run=str(uuid4()); comparison=str(uuid4())
    offer=dict(eligible=True,dispatch_enabled=True,comparison_id=comparison,context_checksum='a'*64,
        prompt_checksum='b'*64,schema_checksum='c'*64,model='copilot/test',invocation=None)
    monkeypatch.setattr(module,'offer',Mock(return_value=offer))
    journal=Mock(); journal.reserve.return_value={'status':'QA_RESERVED','invocation_id':str(uuid4())}
    monkeypatch.setattr(module,'QAJournal',Mock(return_value=journal))
    app=FastAPI();app.include_router(module.create_qa_authorization_router(Mock()))
    return TestClient(app),f'/api/tasks/t/runs/{run}/qa-authorization',offer,journal


@pytest.mark.parametrize('change',['confirmed','model','context_checksum','comparison_id','disabled'])
def test_changed_offer_or_no_consent_does_not_reserve(monkeypatch,change):
    api,url,offer,journal=fixture(monkeypatch)
    body={key:offer[key] for key in ('model','context_checksum','prompt_checksum','schema_checksum','comparison_id')}
    body['confirmed']=True
    if change=='confirmed':body[change]=False
    elif change=='model':body[change]='copilot/other'
    elif change=='comparison_id':body[change]=str(uuid4())
    elif change=='disabled':offer['dispatch_enabled']=False
    else:body[change]='0'*64
    assert api.post(url,json=body).status_code==409
    journal.reserve.assert_not_called()


def test_authorization_only_reserves_and_get_is_read_only(monkeypatch):
    api,url,offer,journal=fixture(monkeypatch)
    assert api.get(url).status_code==200
    journal.reserve.assert_not_called()
    body={key:offer[key] for key in ('model','context_checksum','prompt_checksum','schema_checksum','comparison_id')}
    response=api.post(url,json={**body,'confirmed':True})
    assert response.status_code==200 and response.json()['status']=='QA_RESERVED'
    journal.reserve.assert_called_once()


@pytest.mark.parametrize('record,comparison,native,expected',[
    ({'status':'QA_RESERVED'},True,True,'QA 審查已排程'),
    ({'status':'QA_OUTCOME_UNKNOWN'},True,True,'QA 呼叫結果待核對'),
    ({'status':'STALE_RESULT_NEEDS_REVIEW'},True,True,'版本或證據已失效'),
    ({'status':'VALIDATED_NOT_APPROVED','output_json':{'review':{'status':'NEEDS_REVIEW'}}},True,True,'目前不符合同次執行複核條件'),
    ({'status':'VALIDATED_NOT_APPROVED','output_json':{'review':{'status':'PASS'}}},True,True,'人工核准狀態'),
    (None,False,True,'有效結果比對'),
    (None,True,False,'本機 Copilot QA 路由'),
])
def test_read_offer_explains_actual_blocker_without_reservation(monkeypatch,record,comparison,native,expected):
    from contextlib import nullcontext
    run_id=str(uuid4())
    run={'settings_snapshot':{'model_routes':{'qa_review':'copilot/test'},
                             'ai':{'provider_type':'LOCAL_COPILOT' if native else 'SYNTHETIC'}}}
    if record:record={**record,'invocation_id':str(uuid4())}
    conn=Mock()
    def execute(sql,*args):
        cursor=Mock()
        if 'FROM platform.task_run WHERE' in sql:cursor.fetchone.return_value=run
        elif 'FROM platform.agent_invocation' in sql:cursor.fetchall.return_value=[record] if record else []
        elif 'FROM platform.task_run_result_comparison' in sql:cursor.fetchone.return_value={'comparison_id':str(uuid4())} if comparison else None
        else:raise AssertionError('Unexpected database access')
        return cursor
    conn.execute.side_effect=execute
    queue=Mock();queue.conn.side_effect=lambda:nullcontext(conn)
    monkeypatch.setattr(module,'load_qa_context',Mock(return_value={'context':{'context_checksum':'a'*64}}))
    monkeypatch.setattr(module,'can_reassess',Mock(return_value=False))
    monkeypatch.setattr(module,'qa_material',Mock(return_value={'prompt_checksum':'b'*64}))
    journal=Mock();monkeypatch.setattr(module,'QAJournal',Mock(return_value=journal))
    app=FastAPI();app.include_router(module.create_qa_authorization_router(queue))
    response=TestClient(app).get(f'/api/tasks/t/runs/{run_id}/qa-authorization')
    assert response.status_code==200
    assert response.json()['eligible'] is False
    assert expected in response.json()['blocked_reason']
    journal.reserve.assert_not_called()
