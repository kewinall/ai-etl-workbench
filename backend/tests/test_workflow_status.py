from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.workflow_status import summarize, create_workflow_router


def case(**changes):
    run = dict(run_id='current', task_id='task', state='QUEUED', matches_current=True,
               write_started=False, approval=None, gate_result=None, outcome_code=None)
    run.update(changes.pop('run', {}))
    params = dict(latest_run_id='current', sa={}, sa_approval={}, developer={},
                  specifications=[], hop={}, qa={}, qa_approval={}, release={})
    params.update(changes)
    return summarize(run, **params)


def test_no_approval_never_implies_execution_or_completion():
    status = case()
    assert status['current_stage'] == 'requirements'
    assert status['completed'] == []
    assert status['execution_authorized'] is False
    assert not status['stages'][3]['can_operate']


def test_missing_requirements_returns_to_original_input():
    status = case(run={'state': 'NEEDS_REVIEW', 'approval': {'decision': 'APPROVE'},
                      'gate_result': {'status': 'NEEDS_INPUT', 'issues': [{'message': '缺目標', 'field_path': 'target.table'}]}})
    assert status['current_stage'] == 'requirements'
    assert status['category'] == '需修正'
    assert status['issues'][0]['field_path'] == 'target.table'


def test_sa_confirmation_and_design_are_distinct():
    status = case(run={'state': 'NEEDS_REVIEW', 'approval': {'decision': 'APPROVE'}},
                  sa_approval={'status': 'AWAITING_CONFIRMATION'})
    assert status['current_stage'] == 'review'
    assert not status['stages'][2]['can_operate']
    status = case(sa_approval={'status': 'APPROVED_CURRENT'})
    assert status['current_stage'] == 'design'


def test_stale_spec_approval_does_not_advance():
    status = case(sa_approval={'status': 'APPROVED_CURRENT'},
                  specifications=[{'approval_id': 'old', 'approval_effective': False}])
    assert status['current_stage'] == 'design'


@pytest.mark.parametrize('code', ['HOP_RESULT_UNKNOWN', 'HOP_EXECUTION_FAILED'])
def test_partial_write_is_reconciliation_never_retry(code):
    status = case(run={'write_started': True, 'outcome_code': code, 'state': 'NEEDS_REVIEW'},
                  hop={'request': {'status': 'COMPLETED'}})
    assert status['current_stage'] == 'results'
    assert status['next_action']['label'] == '核對結果並結案'
    assert not status['waiting']


def test_qa_evidence_reassessment_is_not_hop_execution():
    status = case(run={'write_started': True, 'outcome_code': 'HOP_EXECUTED_QA_REQUIRED'},
                  qa={'eligible': True, 'dispatch_enabled': True, 'reassess_invocation_id': 'qa-1'})
    assert status['current_stage'] == 'quality'
    assert '不重跑 Hop' in status['next_action']['label']


def test_unknown_model_result_does_not_enable_redispatch():
    status = case(developer={'invocation': {'status': 'DEVELOPER_OUTCOME_UNKNOWN'}})
    assert not status['next_action']['enabled']
    assert not status['waiting']


def test_historical_release_remains_read_only_but_downloadable():
    status = case(latest_run_id='other', release={'release_ready': True, 'status': 'RELEASE_READY'},
                  qa_approval={'status': 'APPROVED_CURRENT'})
    assert status['historical']
    assert all(not stage['can_operate'] for stage in status['stages'])
    assert status['next_action']['label'] == '下載正式交付'


def test_disabled_dispatch_and_overdue_portability_are_not_success():
    status = case(specifications=[{'approval_effective': True}], hop={'offer': {'id': 's'}, 'dispatch_enabled': False})
    assert not status['next_action']['enabled']
    status = case(qa_approval={'status': 'APPROVED_CURRENT'}, release={'portability': {'status': 'RUNNING', 'overdue': True}})
    assert not status['waiting']
    assert status['category'] == '需修正'


def test_missing_cross_task_run_returns_404_without_reading_other_stores():
    class Queue:
        def detail(self, *args): raise ValueError('RUN_NOT_FOUND')
    app = FastAPI()
    app.include_router(create_workflow_router(Queue(), None))
    response = TestClient(app).get(f'/api/tasks/task/runs/{uuid4()}/workflow-status')
    assert response.status_code == 404
