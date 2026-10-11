"""Offline replay of GET-only reader values read back from 5197 on 2026-10-11 (TASK-20261010-0017/18/19).

Values are copied from the live readers (sa-invocation, sa-approval, developer, specifications, hop-dispatch,
qa-authorization/qa-review, qa-approval, release, workers); no writes, models or ETL were involved.
This proves the new projection on real reader shapes. It is not a deployment test of 5197."""
import pytest
from app.workflow_status import summarize

WORKERS = [{'kind': k, 'can_dispatch': True} for k in
           ('CONTROL', 'SA_COPILOT', 'DEVELOPER_COPILOT', 'QA_COPILOT', 'HOP', 'PORTABILITY')] + \
          [{'kind': 'SA_LITELLM', 'can_dispatch': False}]
CASES = {
    'TASK-20261010-0017': ('5443ccf1-3386-48ba-b669-8c2dbaecd155', ['CSV'], 'CSV'),
    'TASK-20261010-0018': ('029d55b5-d677-427d-a6c2-7a14511b4de4', ['EXCEL'], 'Excel'),
    'TASK-20261010-0019': ('e0b16950-27db-4847-add5-1ddbeaf78e08', ['CSV', 'CSV'], 'CSV'),
}


@pytest.mark.parametrize('task_id', sorted(CASES))
def test_delivered_native_cases_project_consistently(task_id):
    run_id, sources, label = CASES[task_id]
    run = {'run_id': run_id, 'task_id': task_id, 'state': 'NEEDS_REVIEW', 'approval': {'decision': 'APPROVE'},
           'gate_result': {'status': 'CHECKED', 'issues': []}, 'outcome_code': 'HOP_EXECUTED_QA_REQUIRED',
           'write_started': True, 'matches_current': True, 'failed_revision_available': False, 'qa_revision': None,
           'events': [], 'settings_snapshot': {'ai': {'provider_type': 'LOCAL_COPILOT'}},
           'input_snapshot': {'source_config': {'sources': [{'type': t} for t in sources]}}}
    status = summarize(
        run, latest_run_id=run_id,
        sa={'invocation': {'status': 'VALIDATED_NOT_APPROVED', 'review': {'status': 'READY_FOR_REVIEW', 'issues': []}}},
        sa_approval={'status': 'APPROVED_CURRENT'},
        developer={'invocation': {'status': 'VALIDATED_NOT_APPROVED'}, 'eligible': False, 'dispatch_enabled': True,
                   'blocked_reason': '本版需求或 SA 證據尚未通過，請返回需求審查核對。'},
        specifications=[{'approval_effective': False, 'approval_id': 'recorded'}],
        hop={'request': {'status': 'COMPLETED', 'overdue': False}, 'offer': None, 'dispatch_enabled': True,
             'blocked_reason': '先完成 SA 人工交接、Developer 設計、規格與標準答案核准。'},
        qa={'eligible': False, 'dispatch_enabled': True, 'reassess_invocation_id': None,
            'invocation': {'status': 'VALIDATED_NOT_APPROVED', 'review': {'status': 'PASS', 'issues': []}}},
        qa_approval={'status': 'APPROVED_CURRENT'},
        release={'status': 'RELEASE_READY', 'release_ready': True, 'portability': {'status': 'PASS', 'overdue': False},
                 'release': {'release_id': 'r'}},
        services={'workers': WORKERS}, comparison_recovery={'status': 'NOT_ELIGIBLE'}, active_run=True)
    assert status['category'] == '可交付' and status['effective_status'] == '已正式交付'
    assert status['current_stage'] == 'delivery' and status['issues'] == []
    assert [s['status'] for s in status['stages']] == ['complete'] * 7
    assert not any(s['can_operate'] for s in status['stages'])
    enabled = {k for k, v in status['operation_qualifications'].items() if v.get('enabled')}
    assert enabled == {'release_download'}
    assert 'JSON' not in status['source_scope_note'] and label in status['source_scope_note']
