"""Journal usage accounting, including failed revisions; never estimates invoices."""
from collections import defaultdict
from decimal import Decimal
from .invocation_usage import checked_usage

METRICS = ('input_tokens', 'output_tokens', 'total_tokens', 'ai_credits', 'premium_requests', 'duration_ms')


def observation(row):
    # Failure usage was validated on persistence. It stays failure evidence, not an accepted review.
    usage = row['failure_usage'] if row['role'] == 'pilot_developer' and row['status'] == 'DEVELOPER_OUTCOME_UNKNOWN' else row['trace_usage']
    duration = row['failure_duration'] if row['role'] == 'pilot_developer' and row['status'] == 'DEVELOPER_OUTCOME_UNKNOWN' else row['trace_duration']
    try:
        safe = checked_usage(usage)
    except (ValueError, TypeError):
        return {}
    if type(duration) is int and duration >= 0:
        safe['duration_ms'] = duration
    return safe


def summarize(rows):
    ids = [str(row['invocation_id']) for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('DUPLICATE_USAGE_INVOCATION')
    observations = [observation(row) for row in rows]
    metrics = {}
    for key in METRICS:
        values = [o[key] for o in observations if o.get(key) is not None]
        known = sum((Decimal(str(v)) for v in values), Decimal(0)) if values else None
        # null means unavailable, including an empty cohort: never report zero consumption by inference.
        number = float(known) if key in ('ai_credits','premium_requests') and known is not None else int(known) if known is not None else None
        metrics[key] = {'reported_sum': number, 'reported_invocations': len(values),
                        'missing_invocations': len(rows)-len(values),
                        'complete_sum': number if values and len(values)==len(rows) else None}
    return {'journal_invocations': len(rows),
            'nonaccepted_invocations': sum(r['status'] != 'VALIDATED_NOT_APPROVED' for r in rows),
            'provider_partial_records': sum(o.get('usage_type') == 'PARTIAL' for o in observations),
            'metrics': metrics, 'cost': None, 'currency': None, 'rate_version': None}


def read(repo, project_id, cohort_id):
    with repo.conn() as conn:
        rows = conn.execute('''SELECT i.invocation_id,i.run_id,i.task_id,i.role,i.provider,i.model,i.status,
            i.output_json->'trace'->'usage' AS trace_usage,
            i.output_json->'trace'->'duration_ms' AS trace_duration,
            i.output_json->'failure_trace'->'usage' AS failure_usage,
            i.output_json->'failure_trace'->'duration_ms' AS failure_duration
            FROM platform.pilot_case_task b JOIN platform.pilot_cohort c USING(cohort_id)
            JOIN platform.task t ON t.task_id=b.task_id AND t.project_id=c.project_id
            JOIN platform.task_run r ON r.task_id=t.task_id AND r.project_id=c.project_id
            JOIN platform.agent_invocation i ON i.run_id=r.run_id AND i.task_id=t.task_id
            WHERE c.project_id=%s AND c.cohort_id=%s
              AND i.role IN ('pilot_sa','pilot_developer','pilot_qa')
            ORDER BY i.created_at,i.invocation_id''', (project_id,cohort_id)).fetchall()
    groups = defaultdict(list)
    for row in rows:
        groups[(row['provider'],row['model'])].append(row)
    return {'basis': 'ALL_BOUND_RUN_JOURNAL_RECORDS',
            'groups': [{'provider':p,'model':m,**summarize(values)} for (p,m),values in sorted(groups.items())],
            'cases': {task: summarize([r for r in rows if r['task_id']==task]) for task in sorted({r['task_id'] for r in rows})},
            'limitations': [
                '包含正式集合所有版本及失敗／不明紀錄；journal 筆數不是已確認的供應商呼叫次數。',
                '只加總已回報欄位並顯示覆蓋數；缺少任何一筆時完整總量為 null，不補零。',
                '耗時取自角色保存的 trace，含模型請求與本機處理，不是人工工時。',
                'AI credits 與 premium requests 是供應商回報額度，不等同金額或帳單；無費率版本，不估算成本。']}
