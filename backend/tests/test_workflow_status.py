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


def test_queued_without_control_worker_is_not_processing():
    status = case(run={'approval': {'decision': 'APPROVE'}}, services={'workers': []})
    assert status['category'] == '執行服務未就緒'
    assert not status['waiting']
    assert not status['next_action']['operation_enabled']
    assert status['next_action']['type'] == 'NAVIGATE'
    assert '控制 Worker' in status['service_blocked_reason']
    online = case(run={'approval': {'decision': 'APPROVE'}},
                  services={'workers': [{'kind': 'CONTROL', 'can_dispatch': True}]})
    assert online['waiting']
    assert online['category'] == '系統處理中'


def test_missing_design_service_and_pending_design_are_not_fake_processing():
    status=case(sa_approval={'status':'APPROVED_CURRENT'},
                developer={'invocation':{'status':'DEVELOPER_RESERVED'}},services={'workers':[]})
    assert status['category']=='執行服務未就緒'
    assert not status['waiting']
    assert status['operation_qualifications']['developer']['type']=='AUTHORIZE_MODEL'
    assert not status['operation_qualifications']['hop']['service_ready']


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


@pytest.mark.parametrize('recovery_status', ['QUEUED', 'CLAIMED', 'FAILED'])
def test_finished_hop_without_comparison_stays_at_results(recovery_status):
    status=case(run={'write_started':True,'outcome_code':'HOP_EXECUTED_QA_REQUIRED'},
                comparison_recovery={'status':recovery_status})
    assert status['current_stage']=='results'
    assert not status['stages'][5]['can_operate']
    assert status['waiting']==(recovery_status!='FAILED')
    assert '不可重跑' in status['execution_blocked_reason']


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


def test_reconciled_failed_run_offers_revision_after_closure():
    status = case(run={'failed_revision_available': True, 'write_started': True,
                      'state': 'FAILED', 'outcome_code': 'HOP_EXECUTION_FAILED'})
    assert status['current_stage'] == 'results'
    assert status['next_action']['stage'] == 'requirements'
    assert status['next_action']['label'] == '此版已結案；可建立修正版'


def test_qa_issues_point_to_evidence_stage_not_requirement_revision():
    status = case(run={'outcome_code': 'HOP_EXECUTED_QA_REQUIRED'},
                  qa={'invocation': {'status': 'VALIDATED_NOT_APPROVED',
                                     'review': {'issues': [{'message': '補同次執行證據'}]}}})
    assert status['issues'][0]['stage'] == 'quality'
    assert status['category'] == '需修正'


def test_spec_rejection_is_cleared_by_later_saved_spec():
    rejected = {'event_type': 'SPECIFICATION_SEMANTIC_REJECTED',
                'event_context': {'issues': [{'message': '規格語意不符'}]}}
    assert case(run={'events': [rejected]})['issues'][0]['stage'] == 'design'
    assert not case(run={'events': [rejected, {'event_type': 'SPECIFICATION_SAVED'}]})['issues']


WRITE_OPERATIONS = ['prepare_run', 'input_confirm', 'input_cancel', 'requirement_revision', 'sa_authorize',
                    'sa_approve', 'naming_confirm', 'developer_authorize', 'specification_create',
                    'specification_approve', 'oracle_save', 'oracle_approve', 'hop_execute', 'execution_close',
                    'comparison_recovery', 'qa_authorize', 'qa_approve', 'sdm_prepare', 'release_candidate',
                    'release_approve']


def delivered_case(**changes):
    params = dict(run={'state': 'NEEDS_REVIEW', 'write_started': True, 'outcome_code': 'HOP_EXECUTED_QA_REQUIRED',
                       'approval': {'decision': 'APPROVE'}, 'gate_result': {'status': 'CHECKED'},
                       'input_snapshot': {'source_config': {'sources': [{'type': 'CSV'}]}}},
                  sa={'invocation': {'status': 'VALIDATED_NOT_APPROVED'}},
                  sa_approval={'status': 'APPROVED_CURRENT'},
                  developer={'invocation': {'status': 'VALIDATED_NOT_APPROVED'}, 'eligible': False, 'dispatch_enabled': True},
                  specifications=[{'approval_effective': True}],
                  hop={'request': {'status': 'COMPLETED'}, 'offer': None, 'dispatch_enabled': True},
                  qa={'eligible': False, 'dispatch_enabled': True, 'invocation': {'status': 'VALIDATED_NOT_APPROVED'}},
                  qa_approval={'status': 'APPROVED_CURRENT'},
                  release={'release_ready': True, 'status': 'RELEASE_READY', 'release': {'release_id': 'r'}},
                  services={'workers': [{'kind': k, 'can_dispatch': True} for k in
                                        ('CONTROL', 'SA_COPILOT', 'DEVELOPER_COPILOT', 'QA_COPILOT', 'HOP', 'PORTABILITY')]},
                  active_run=True)
    params.update(changes)
    return case(**params)


def test_delivered_run_is_view_and_download_only():
    status = delivered_case()
    assert status['delivered'] and status['category'] == '可交付'
    assert status['effective_status'] == '已正式交付'
    assert status['milestones']['executed'] and status['milestones']['qa_approved'] and status['milestones']['delivered']
    assert all(not stage['can_operate'] for stage in status['stages'])
    assert all(stage['status'] == 'complete' for stage in status['stages'])
    q = status['operation_qualifications']
    for name in WRITE_OPERATIONS:
        assert q[name]['enabled'] is False, name
        assert '已正式交付' in q[name]['blocked_reason'], name
        assert set(q[name]) >= {'type', 'enabled', 'blocked_reason'}
    assert q['release_download'] == {'type': 'DOWNLOAD', 'enabled': True, 'blocked_reason': None}
    assert q['hop_execute']['service_ready'] is True  # Service state stays visible but never grants writes.
    assert status['next_action']['type'] == 'DOWNLOAD'
    assert status['issues'] == []


def test_completed_qa_is_not_reported_as_pending_approval():
    status = delivered_case(release={'release_ready': False, 'status': 'SDM_AND_CANDIDATE_REQUIRED'})
    assert status['effective_status'] == 'QA 已核准，待完成交付'
    assert status['current_stage'] == 'delivery'
    q = status['operation_qualifications']
    assert not q['qa_approve']['enabled'] and not q['qa_authorize']['enabled']
    assert q['sdm_prepare']['enabled'] and q['release_candidate']['enabled']
    assert not q['hop_execute']['enabled'] and not q['specification_create']['enabled']


def test_design_stage_qualifications_follow_prerequisite_order():
    status = case(run={'state': 'NEEDS_REVIEW', 'approval': {'decision': 'APPROVE'}},
                  sa_approval={'status': 'APPROVED_CURRENT'},
                  developer={'eligible': False, 'blocked_reason': '請先核對並確認本版命名對照，才能授權 Developer 設計。'})
    q = status['operation_qualifications']
    assert q['naming_confirm']['enabled']
    assert not q['developer_authorize']['enabled'] and '命名' in q['developer_authorize']['blocked_reason']
    assert q['specification_create']['enabled'] and not q['specification_approve']['enabled']
    assert not q['hop_execute']['enabled']


def test_historical_and_service_blockers_disable_writes_with_reason():
    historical = case(latest_run_id='other', run={'state': 'QUEUED'})
    assert not historical['operation_qualifications']['input_confirm']['enabled']
    assert '歷史' in historical['operation_qualifications']['input_confirm']['blocked_reason']
    offline = case(run={'approval': {'decision': 'APPROVE'}, 'gate_result': {'status': 'CHECKED'}, 'state': 'NEEDS_REVIEW'},
                   services={'workers': [{'kind': 'CONTROL', 'can_dispatch': True}]})
    sa = offline['operation_qualifications']['sa_authorize']
    assert not sa['enabled'] and sa['service_ready'] is False and '未就緒' in sa['blocked_reason']


def test_source_note_follows_actual_sources():
    csv = case(run={'input_snapshot': {'source_config': {'sources': [{'type': 'CSV'}, {'type': 'CSV'}]}}})
    assert 'JSON' not in csv['source_scope_note'] and csv['source_types'] == ['CSV']
    json = case(run={'input_snapshot': {'source_config': {'sources': [{'type': 'JSON'}]}}})
    assert 'JSON' in json['source_scope_note'] and '尚未完成' in json['source_scope_note']
