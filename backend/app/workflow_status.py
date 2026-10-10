"""Read-only stage guidance. Existing offers remain the authority for mutations."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response
from uuid import UUID
from .run_queue import RunConflict

LABELS = ['需求與資料規格', '需求審查', '流程設計審查', '執行確認', '執行與結果', '品質審查', '成果交付']
KEYS = ['requirements', 'review', 'design', 'confirm', 'results', 'quality', 'delivery']
WAITING = {'QUEUED', 'RUNNING', 'DISPATCH_RESERVED', 'CLAIMED', 'SA_QUEUED', 'QA_RESERVED'}


def summarize(run, *, latest_run_id, sa, sa_approval, developer, specifications,
              hop, qa, qa_approval, release, services=None):
    """A projection of authoritative readers, never a new mutable state machine."""
    historical = str(run['run_id']) != str(latest_run_id)
    current = run.get('matches_current') is True and not historical
    approved_input = (run.get('approval') or {}).get('decision') == 'APPROVE'
    gate = run.get('gate_result') or {}
    sa_record = sa.get('invocation') or {}
    dev_record = developer.get('invocation') or {}
    job = hop.get('request') or {}
    qa_record = qa.get('invocation') or {}
    portable = release.get('portability') or {}
    spec_ok = any(s.get('approval_effective') for s in specifications)
    sa_ok = sa_approval.get('status') == 'APPROVED_CURRENT'
    qa_ok = qa_approval.get('status') == 'APPROVED_CURRENT'
    completed = [approved_input, sa_ok, spec_ok, bool(job),
                 run.get('outcome_code') == 'HOP_EXECUTED_QA_REQUIRED', qa_ok,
                 release.get('release_ready') is True]
    if release.get('release_ready') is True:
        completed = [True] * 7  # The existing release reader already verifies the full lineage.
    issues = list(gate.get('issues') or [])
    review = sa_record.get('review') or {}
    issues += list(review.get('issues') or [])
    for event in reversed(run.get('events') or []):
        if event.get('event_type') in ('SPECIFICATION_SAVED', 'SPECIFICATION_APPROVED'):
            break
        if event.get('event_type') == 'SPECIFICATION_SEMANTIC_REJECTED':
            issues += [{**issue, 'stage': 'design'} for issue in (event.get('event_context') or {}).get('issues', [])]
            break
    issues += [{**issue, 'stage': 'quality'} for issue in (qa_record.get('review') or {}).get('issues', [])] if not qa_ok else []
    index, owner, action, enabled, waiting = 0, '你', '確認需求版本', current, False
    code = run.get('outcome_code') or ''
    if approved_input:
        index, action = 1, '授權需求審查'
        enabled = current and gate.get('status') == 'CHECKED'
        if run['state'] in ('QUEUED', 'RUNNING') or sa_record.get('status') in WAITING:
            owner, action, enabled, waiting = 'AI／控制服務', '等待需求審查', False, True
        elif gate.get('status') == 'NEEDS_INPUT' or review.get('status') == 'NEEDS_INPUT':
            index, action, enabled = 0, '前往修正需求', current
        elif sa_approval.get('status') == 'AWAITING_CONFIRMATION':
            action, enabled = '確認需求審查結果', current
        elif sa_record and not sa_ok:
            action, enabled = '檢查需求審查問題', current
    if sa_ok:
        index, action, enabled = 2, '確認命名並檢閱流程設計', current
        if dev_record.get('status') in WAITING:
            owner, action, enabled, waiting = 'AI', '等待流程設計', False, True
        elif specifications:
            action = '檢視並核准流程設計'
    if spec_ok:
        index, action, enabled = 3, '核對標準答案與執行前置條件', current
        if hop.get('offer'):
            action, enabled = '確認並執行一次', current and hop.get('dispatch_enabled') is True
    if job or run.get('write_started'):
        index, action, enabled = 4, '查看執行結果', current
        if job.get('status') in WAITING and not job.get('overdue'):
            owner, action, enabled, waiting = '執行服務', '等待執行結果', False, True
        elif job.get('overdue') or code in ('HOP_RESULT_UNKNOWN', 'HOP_EXECUTION_FAILED') or job.get('status') == 'NEEDS_REVIEW':
            owner, action, enabled, waiting = '你', '核對結果並結案', current, False
    if completed[4]:
        index, owner, action, enabled, waiting = 5, '你', '授權品質審查', current and qa.get('eligible') is True and qa.get('dispatch_enabled') is True, False
        if qa_record.get('status') in WAITING:
            owner, action, enabled, waiting = 'AI', '等待品質審查', False, True
        elif qa_approval.get('status') == 'AWAITING_CONFIRMATION':
            action, enabled = '核准品質審查結果', current
        elif qa.get('reassess_invocation_id'):
            action = '補充證據並重新審查（不重跑 Hop）'
        elif qa_record:
            action, enabled = '處理 QA 意見與證據缺口', current
    if qa_ok:
        index, owner, action, enabled, waiting = 6, '你', '準備 SDM 與候選包', current, False
        if portable.get('status') == 'RUNNING' and not portable.get('overdue'):
            owner, action, enabled, waiting = '隔離驗證服務', '等待可攜驗證', False, True
        elif release.get('status') == 'AWAITING_RELEASE_APPROVAL':
            action = '檢閱並核准交付'
        elif release.get('release_ready'):
            action, enabled = '下載正式交付', True
        elif portable.get('overdue') or portable.get('status') in ('FAIL', 'FAILED', 'UNKNOWN'):
            action, enabled = '檢查可攜驗證問題', current
    if any('UNKNOWN' in str(r.get('status', '')) for r in (sa_record, dev_record, qa_record)):
        owner, action, enabled, waiting = '你', '核對模型呼叫結果，勿重送', False, False
    if run['state'] == 'CANCELLED':
        action, enabled, waiting = '已取消；查看原始輸入及歷史', False, False
    if run.get('failed_revision_available'):
        index, owner, action, enabled, waiting = 0, '你', '建立修正版並重新確認需求', current, False
    if not current:
        enabled, waiting = release.get('release_ready') is True, False
        action = '下載正式交付' if enabled else '檢視歷史與失效核准原因'
    service_blocker = None
    if services is not None and current and index == 1 and approved_input and run['state'] in ('QUEUED', 'RUNNING'):
        control = next((w for w in services.get('workers', []) if w['kind'] == 'CONTROL'), {})
        if not control.get('can_dispatch'):
            service_blocker = '控制服務未就緒；請由環境管理者啟動此環境的控制 Worker，再重新核對狀態。'
            owner, action, enabled, waiting = '環境管理者', '查看服務就緒條件', False, False
    stages = [{'key': key, 'number': i + 1, 'label': LABELS[i],
               'status': 'complete' if completed[i] else 'current' if i == index else 'blocked',
               'can_operate': current and i <= index,
               'blocked_reason': None if completed[i] or (current and i <= index) else
               ('歷史或上游內容已變更；只讀檢視，不沿用核准。' if not current else '先完成前一階段的必要核准與證據。')}
              for i, key in enumerate(KEYS)]
    category = ('執行服務未就緒' if service_blocker else '可交付' if release.get('release_ready') else '系統處理中' if waiting else
                '待核對' if '核對結果' in action or 'UNKNOWN' in code else
                '需修正' if issues or '問題' in action or '缺口' in action else '待你確認')
    return {'task_id': run['task_id'], 'run_id': str(run['run_id']),
            'updated_at': run.get('updated_at'), 'read_at': datetime.now(timezone.utc),
            'historical': historical, 'matches_current': run.get('matches_current') is True,
            'stages': stages, 'current_stage': KEYS[index], 'owner': owner,
            'completed': [LABELS[i] for i, done in enumerate(completed) if done],
            'next_action': {'label': action, 'stage': KEYS[index], 'enabled': enabled,
                            'type': 'NAVIGATE', 'operation_enabled': enabled,
                            'blocked_reason': service_blocker},
            'services': services, 'service_blocked_reason': service_blocker,
            'waiting': waiting, 'category': category, 'issues': issues,
            'execution_blocked_reason': hop.get('blocked_reason'),
            'source_scope_note': 'JSON／資料表來源的完整執行驗收尚未完成；可檢視規格與候選證據，勿視為全鏈通過。',
            'release_status': release.get('status'), 'release': release.get('release'),
            'execution_authorized': False}


def read(queue, repo, task_id, run_id):
    from .sa_journal import SAJournal
    from .sa_approval import read as sa_read
    from .developer_api import read as developer_read
    from .specification_store import history
    from .hop_dispatch_api import read as hop_read
    from .qa_authorization_api import offer as qa_offer
    from .qa_journal import QAJournal
    from .qa_approval import read_approval
    from .release_store import status as release_status
    from .run_api import public_run
    from .worker_presence import WorkerRegistry
    # Every reader validates Task/Run identity. Do not mask unavailable stores as empty.
    before = queue.detail(task_id, run_id)
    runs = queue.list_runs(task_id)
    with queue.conn() as conn:
        specifications = history(queue, conn, task_id, run_id)['items']
    qa = qa_offer(queue, task_id, run_id)
    qa['invocation'] = QAJournal(queue).read(task_id, run_id)['invocation']
    result = summarize(before, latest_run_id=runs[0]['run_id'],
        sa=SAJournal(queue).read(task_id, run_id), sa_approval=sa_read(queue, task_id, run_id),
        developer=developer_read(queue, task_id, run_id), specifications=specifications,
        hop=hop_read(queue, task_id, run_id), qa=qa,
        qa_approval=read_approval(queue, task_id, run_id), release=release_status(queue, repo, task_id, run_id),
        services=WorkerRegistry(queue).snapshot())
    after = queue.detail(task_id, run_id)
    if public_run(before) != public_run(after) or str(queue.list_runs(task_id)[0]['run_id']) != str(runs[0]['run_id']):
        raise RunConflict('WORKFLOW_READ_CHANGED')
    return result


def create_workflow_router(queue, repo):
    router = APIRouter(prefix='/api/tasks', tags=['Read-only workflow guidance'])

    @router.get('/{task_id}/runs/{run_id}/workflow-status')
    def status(task_id: str, run_id: UUID, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        try:
            return read(queue, repo, task_id, run_id)
        except RunConflict:
            raise HTTPException(409, detail='階段資料在讀取期間已變更，請重新讀取；未核准或派發任何工作。') from None
        except ValueError as exc:
            if str(exc) in ('TASK_NOT_FOUND', 'RUN_NOT_FOUND'):
                raise HTTPException(404, detail='找不到指定 Task 或版本；未改用最新版本。') from None
            raise HTTPException(503, detail='階段證據無法完整核對，操作已暫停。') from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, detail='階段證據服務不可用，操作已暫停。') from None
    return router
