"""Read-only stage guidance. Existing offers remain the authority for mutations."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response
from uuid import UUID
from .run_queue import RunConflict

LABELS = ['需求與資料規格', '需求審查', '流程設計審查', '執行確認', '執行與結果', '品質審查', '成果交付']
KEYS = ['requirements', 'review', 'design', 'confirm', 'results', 'quality', 'delivery']
WAITING = {'QUEUED', 'RUNNING', 'DISPATCH_RESERVED', 'CLAIMED', 'SA_QUEUED', 'QA_RESERVED', 'DEVELOPER_RESERVED'}


def summarize(run, *, latest_run_id, sa, sa_approval, developer, specifications,
              hop, qa, qa_approval, release, services=None, comparison_recovery=None,
              active_run=False):
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
    if completed[4] and (qa.get('eligible') or qa_record or qa_ok):
        index, owner, action, enabled, waiting = 5, '你', '授權品質審查', current and qa.get('eligible') is True and qa.get('dispatch_enabled') is True, False
        if qa_record.get('status') in WAITING:
            owner, action, enabled, waiting = 'AI', '等待品質審查', False, True
        elif qa_approval.get('status') == 'AWAITING_CONFIRMATION':
            action, enabled = '核准品質審查結果', current
        elif qa.get('reassess_invocation_id'):
            action = '補充證據並重新審查（不重跑 Hop）'
        elif qa_record:
            action, enabled = '處理 QA 意見與證據缺口', current
    recovery = comparison_recovery or {}
    if completed[4] and not (qa.get('eligible') or qa_record or qa_ok):
        completed[4] = False
        index, owner, action, enabled, waiting = 4, '你', '檢查結果比對與標準答案', current, False
        if recovery.get('status') in ('QUEUED', 'CLAIMED'):
            owner, action, enabled, waiting = '執行服務', '等待只讀結果比對（不重跑 ETL）', False, True
        elif recovery.get('status') == 'FAILED':
            action = '處理結果比對失敗（保留原執行）'
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
        index, owner, action, enabled, waiting = 4, '你', '此版已結案；可建立修正版', current, False
    if not current:
        enabled, waiting = release.get('release_ready') is True, False
        action = '下載正式交付' if enabled else '檢視歷史與失效核准原因'
    service_blocker = None
    online = None
    service_ops = {}
    if services is not None:
        online = {w['kind']: w.get('can_dispatch') is True for w in services.get('workers', [])}
        native = ((run.get('settings_snapshot') or {}).get('ai') or {}).get('provider_type') == 'LOCAL_COPILOT'
        for operation, kind, action_type in [('sa', 'SA_COPILOT' if native else 'SA_LITELLM', 'AUTHORIZE_MODEL'),
                                            ('developer', 'DEVELOPER_COPILOT', 'AUTHORIZE_MODEL'),
                                            ('qa', 'QA_COPILOT', 'AUTHORIZE_MODEL'),
                                            ('hop', 'HOP', 'EXECUTE_WRITE'),
                                            ('portability', 'PORTABILITY', 'VERIFY_ISOLATED')]:
            ready = online.get(kind, False)
            service_ops[operation] = {'type': action_type, 'service_ready': ready,
                'blocked_reason': None if ready else f'{kind} 執行服務未就緒；請由環境管理者啟動此專案的服務，再重新核對。'}
        pending_role = ('sa' if index == 1 and sa_record.get('status') in WAITING else
                        'developer' if index == 2 and dev_record.get('status') in WAITING else
                        'hop' if index == 4 and (job.get('status') in WAITING or recovery.get('status') in ('QUEUED', 'CLAIMED')) else
                        'qa' if index == 5 and qa_record.get('status') in WAITING else
                        'portability' if index == 6 and portable.get('status') == 'RUNNING' else None)
        if pending_role and not service_ops[pending_role]['service_ready']:
            service_blocker = service_ops[pending_role]['blocked_reason']
            owner, action, enabled, waiting = '環境管理者', '查看服務就緒條件', False, False
    if services is not None and current and index == 1 and approved_input and run['state'] in ('QUEUED', 'RUNNING'):
        control = next((w for w in services.get('workers', []) if w['kind'] == 'CONTROL'), {})
        if not control.get('can_dispatch'):
            service_blocker = '控制服務未就緒；請由環境管理者啟動此環境的控制 Worker，再重新核對狀態。'
            owner, action, enabled, waiting = '環境管理者', '查看服務就緒條件', False, False
    delivered = release.get('release_ready') is True
    milestones = {'input_confirmed': approved_input, 'sa_approved': sa_ok, 'specification_approved': spec_ok,
                  'executed': bool(run.get('write_started')) and code == 'HOP_EXECUTED_QA_REQUIRED',
                  'execution_started': bool(run.get('write_started')),
                  'qa_approved': qa_ok, 'delivered': delivered}
    qualifications = operation_qualifications(
        run, current=current, historical=historical, delivered=delivered, approved_input=approved_input, gate=gate,
        sa_record=sa_record, sa_ok=sa_ok, sa_approval=sa_approval, developer=developer, dev_record=dev_record,
        specifications=specifications, spec_ok=spec_ok, hop=hop, job=job, code=code, qa=qa, qa_record=qa_record,
        qa_ok=qa_ok, qa_approval=qa_approval, release=release, recovery=recovery, comparison_done=completed[4],
        service_ops=service_ops, active_run=active_run)
    qualifications.update(service_ops)
    stages = [{'key': key, 'number': i + 1, 'label': LABELS[i],
               'status': 'complete' if completed[i] else 'current' if i == index else 'blocked',
               # Stage hint only. Delivered Runs are view/download only; per-operation flags decide writes.
               'can_operate': current and i <= index and not delivered,
               'blocked_reason': None if completed[i] or (current and i <= index) else
               ('歷史或上游內容已變更；只讀檢視，不沿用核准。' if not current else '先完成前一階段的必要核准與證據。')}
              for i, key in enumerate(KEYS)]
    category = ('執行服務未就緒' if service_blocker else '可交付' if delivered else '系統處理中' if waiting else
                '待核對' if '核對結果' in action or 'UNKNOWN' in code else
                '需修正' if issues or '問題' in action or '缺口' in action or recovery.get('status')=='FAILED' else '待你確認')
    effective = ('已正式交付' if delivered else 'QA 已核准，待完成交付' if qa_ok else
                 '已執行，待結果比對與 QA' if milestones['executed'] else '執行中或待核對' if milestones['execution_started'] else
                 '規格已核准，待執行確認' if spec_ok else 'SA 已確認，待流程設計' if sa_ok else
                 '輸入已確認，待需求審查' if approved_input else '待確認此版輸入')
    if run['state'] == 'CANCELLED':
        effective = '已取消'
    return {'task_id': run['task_id'], 'run_id': str(run['run_id']),
            'updated_at': run.get('updated_at'), 'read_at': datetime.now(timezone.utc),
            'historical': historical, 'matches_current': run.get('matches_current') is True,
            'stages': stages, 'current_stage': KEYS[index], 'owner': owner,
            'completed': [LABELS[i] for i, done in enumerate(completed) if done],
            'next_action': {'label': action, 'stage': 'requirements' if run.get('failed_revision_available') and current else KEYS[index], 'enabled': enabled,
                            'type': 'DOWNLOAD' if delivered and action == '下載正式交付' else 'NAVIGATE', 'operation_enabled': enabled,
                            'blocked_reason': service_blocker},
            'services': services, 'service_blocked_reason': service_blocker,
            'operation_qualifications': qualifications,
            'milestones': milestones, 'effective_status': effective, 'delivered': delivered,
            'waiting': waiting, 'category': category, 'issues': [] if delivered else issues,
            'execution_blocked_reason': ('Hop 已完成，但尚缺有效結果比對；請檢查標準答案與比對失敗原因，不可重跑原目標。' if completed[4] is False and code == 'HOP_EXECUTED_QA_REQUIRED' else hop.get('blocked_reason')),
            'comparison_recovery': comparison_recovery,
            'source_types': source_types(run),
            'source_scope_note': source_scope_note(run),
            'release_status': release.get('status'), 'release': release.get('release'),
            'execution_authorized': False}


def source_types(run):
    sources = (((run.get('input_snapshot') or {}).get('source_config') or {}).get('sources') or [])
    return sorted({str(item.get('type') or 'UNKNOWN').upper() for item in sources})


def source_scope_note(run):
    types = source_types(run)
    pending = [t for t in types if t not in ('CSV', 'EXCEL')]
    if not types:
        return '此版本未記錄來源類型；請以需求頁的來源內容為準。'
    if pending:
        return f'{"／".join(pending)} 來源的完整執行驗收尚未完成；可檢視規格與候選證據，勿視為全鏈通過。'
    names = '／'.join('Excel' if t == 'EXCEL' else t for t in types)
    return f'{names} 來源已有真實七階段驗收案例；本版是否通過仍以本版的執行、比對、QA 與交付證據為準。'


DELIVERED = '此版已正式交付；只能查看與下載。需要變更時請另建修正版本，不回到原版本修改。'


def operation_qualifications(run, *, current, historical, delivered, approved_input, gate, sa_record, sa_ok, sa_approval,
                             developer, dev_record, specifications, spec_ok, hop, job, code, qa, qa_record, qa_ok,
                             qa_approval, release, recovery, comparison_done, service_ops, active_run):
    """Per-operation eligibility derived from existing offers/approvals. Backend writes still re-validate."""
    state = run.get('state')
    started = bool(run.get('write_started'))
    unknown = any('UNKNOWN' in str(r.get('status', '')) for r in (sa_record, dev_record, qa_record))
    common = (None if current else '歷史版本或上游內容已變更；只讀檢視，不沿用核准。')
    if common is None and delivered:
        common = DELIVERED
    if common is None and state == 'CANCELLED':
        common = '此版已取消；只保留原始輸入與歷史紀錄。'
    latest_blocker = ('歷史版本只讀；請切換到最新版本。' if historical else DELIVERED if delivered else None)

    def item(kind, ok, reason, service=None, *, allow_when_delivered=False, task_level=False):
        # task_level: prepare/cancel stay available on the latest version even when its inputs went stale.
        blocker = None if allow_when_delivered else (latest_blocker if task_level else common)
        if blocker is None and service and service in service_ops and not service_ops[service]['service_ready']:
            blocker = service_ops[service]['blocked_reason']
        if blocker is None and unknown and kind in ('AUTHORIZE_MODEL', 'EXECUTE_WRITE'):
            blocker = '有模型呼叫結果不明；請先核對原呼叫，不會重送。'
        if blocker is None and not ok:
            blocker = reason
        result = {'type': kind, 'enabled': blocker is None, 'blocked_reason': blocker}
        if service:
            result['service_ready'] = service_ops.get(service, {}).get('service_ready')
        return result

    spec_pending = any(not s.get('approval_effective') for s in specifications)
    revisable = ((state == 'NEEDS_REVIEW' and run.get('gate_result') and not started)
                 or run.get('failed_revision_available') or bool(run.get('qa_revision')))
    release_status = release.get('status')
    return {
        'prepare_run': item('CREATE_RUN', not active_run, '已有待處理或已交付的版本；不能另建準備版本。', task_level=True),
        'input_confirm': item('CONFIRM_INPUT', state == 'QUEUED' and not run.get('approval'),
                              '此版輸入已有決定，或版本不在待確認狀態。'),
        'input_cancel': item('CANCEL_RUN', state in ('QUEUED', 'NEEDS_REVIEW') and not started,
                             '已開始外部寫入或版本已結束，不能取消。', task_level=True),
        'requirement_revision': item('CREATE_REVISION', bool(revisable),
                                     '目前沒有可補正的需求缺口；已執行版本只能經 QA 補正或失敗結案後建立修正版。'),
        'sa_authorize': item('AUTHORIZE_MODEL', approved_input and gate.get('status') == 'CHECKED' and not sa_record,
                             '需先確認輸入並通過初步需求檢查；已有 SA 呼叫紀錄時不重送。', 'sa'),
        'sa_cancel': item('CANCEL_QUEUED', sa_record.get('status') == 'SA_QUEUED',
                          '只有尚未被領取的 SA 工作可以取消。'),
        'sa_approve': item('APPROVE', sa_approval.get('status') == 'AWAITING_CONFIRMATION',
                           '目前沒有待確認的 SA 審查結果。'),
        'naming_confirm': item('SAVE', sa_ok and not started,
                               '需先確認 SA；開始執行後不再修改命名。'),
        'developer_authorize': item('AUTHORIZE_MODEL', developer.get('eligible') is True and developer.get('dispatch_enabled') is True,
                                    developer.get('blocked_reason') or '需先完成 SA 確認與命名；已有 Developer 呼叫時不重送。', 'developer'),
        'specification_create': item('SAVE', sa_ok and not spec_ok and not job and not started,
                                     '需先確認 SA；規格已核准或已開始執行後不再新增規格。'),
        'specification_approve': item('APPROVE', spec_pending and not spec_ok and not job and not started,
                                      '沒有待核准的規格版本。'),
        'sdm_candidate': item('SAVE', spec_ok and not delivered, '需先有核准有效的規格。'),
        'oracle_save': item('SAVE', spec_ok and not job and not started, '需先核准規格；開始執行後標準答案不可替換。'),
        'oracle_approve': item('APPROVE', spec_ok and not job and not started, '需先核准規格；開始執行後標準答案不可替換。'),
        'hop_execute': item('EXECUTE_WRITE', bool(hop.get('offer')) and hop.get('dispatch_enabled') is True and not job and not started,
                            hop.get('blocked_reason') or '尚無有效執行條件，或此版已派發執行。', 'hop'),
        'execution_close': item('CLOSE_RECONCILIATION', code in ('HOP_RESULT_UNKNOWN', 'HOP_EXECUTION_FAILED') and not run.get('failed_revision_available'),
                                '只有失敗或結果不明的執行需要人工核對結案。'),
        'preparation_close': item('CLOSE_RECONCILIATION', job.get('status') in ('CLAIMED', 'NEEDS_REVIEW'),
                                  '只有已領取但結果不明或待核對的執行準備需要人工結案。'),
        'comparison_recovery': item('VERIFY_READ_ONLY', code == 'HOP_EXECUTED_QA_REQUIRED' and not comparison_done
                                    and recovery.get('status') not in ('QUEUED', 'CLAIMED'),
                                    '結果比對已存在或正在處理。', 'hop'),
        'qa_authorize': item('AUTHORIZE_MODEL', qa.get('eligible') is True and qa.get('dispatch_enabled') is True and not qa_ok,
                             '需完成 Hop 與結果比對；已有 QA 呼叫且不符合複核條件時不重送。', 'qa'),
        'qa_approve': item('APPROVE', qa_approval.get('status') == 'AWAITING_CONFIRMATION', '目前沒有待核准的 QA PASS 審查。'),
        'sdm_prepare': item('SAVE', qa_ok and release_status in ('SDM_AND_CANDIDATE_REQUIRED',),
                            '需先有有效人工 QA 核准；候選包建立後不再重新產生 SDM。'),
        'release_candidate': item('VERIFY_ISOLATED', release_status == 'SDM_AND_CANDIDATE_REQUIRED',
                                  '需先完成 QA 核准，或候選包已建立。', 'portability'),
        'release_approve': item('APPROVE', release_status == 'AWAITING_RELEASE_APPROVAL', '尚未完成可攜驗證，或已核准交付。'),
        'release_download': item('DOWNLOAD', delivered, '尚無正式交付。', allow_when_delivered=True),
    }


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
    from .comparison_recovery import read as recovery_read
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
        services=WorkerRegistry(queue).snapshot(before['project_id']),
        comparison_recovery=recovery_read(queue, task_id, run_id),
        active_run=any(r['state'] in ('QUEUED', 'RUNNING', 'NEEDS_REVIEW') for r in runs))
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
