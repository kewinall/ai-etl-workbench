"""Read-only, fixed-population delivery measurements; no inferred human effort."""
from datetime import datetime, timezone
from .pilot_cohort import inventory
from .run_queue import RunQueue
from .release_store import status as release_status


def elapsed_seconds(start, finish):
    try:
        start = datetime.fromisoformat(start) if isinstance(start, str) else start
        finish = datetime.fromisoformat(finish) if isinstance(finish, str) else finish
        if not start.tzinfo or not finish.tzinfo or finish < start:
            return None
        return (finish - start).total_seconds()
    except (ValueError, TypeError, AttributeError):
        return None


def measure(cohort, inspect_release):
    cases = cohort['cases']
    if len(cases) != 20 or len({c['case_key'] for c in cases}) != 20:
        raise ValueError('PILOT_MEASUREMENT_POPULATION_INVALID')
    rows = []
    for case in cases:
        runs = case['runs']
        row = {'case_key': case['case_key'], 'title': case['definition']['title'],
               'scenario': case['definition']['scenario'], 'task_id': case['task_id'],
               'attempt_count': len(runs), 'revision_count': sum(r['parent_run_id'] is not None for r in runs),
               'status': 'NOT_STARTED' if case['task_id'] else 'NOT_ENROLLED',
               'run_id': None, 'release_id': None, 'release_checksum': None,
               'elapsed_to_delivery_seconds': None, 'scenario_acceptance_verified': False}
        if runs:
            if not case['attempt_order_verified']:
                row['status'] = 'ATTEMPT_ORDER_UNVERIFIED'
            else:
                latest = runs[-1]
                row['run_id'] = str(latest['run_id'])
                try:
                    result = inspect_release(case['task_id'], latest['run_id'])
                    row['status'] = result['status']
                    release = result.get('release') or {}
                    if result['status'] == 'RELEASE_READY':
                        if result.get('release_ready') is not True or not all(release.get(k) for k in ('release_id','checksum','approved_at')):
                            raise ValueError('INCOMPLETE_RELEASE_PROOF')
                        row.update(release_id=str(release['release_id']), release_checksum=release['checksum'],
                                   elapsed_to_delivery_seconds=elapsed_seconds(runs[0]['created_at'], release['approved_at']))
                except Exception:
                    # Never convert a failed check to zero cases, success, or leak raw exceptions.
                    row['status'] = 'CHECK_UNAVAILABLE'
        rows.append(row)
    return {'cohort_id': str(cohort['cohort_id']), 'name': cohort['name'],
            'plan_checksum': cohort['plan_checksum'], 'denominator': 20,
            'release_ready_count': sum(r['status'] == 'RELEASE_READY' for r in rows),
            'unverified_count': sum(r['status'] in ('CHECK_UNAVAILABLE','ATTEMPT_ORDER_UNVERIFIED') for r in rows),
            'attempt_count': sum(r['attempt_count'] for r in rows),
            'revision_count': sum(r['revision_count'] for r in rows),
            'first_pass_rate': None, 'human_active_seconds': None, 'human_baseline_seconds': None,
            'improvement_rate': None, 'cost': None, 'comparison_ready': False, 'cases': rows}


def read(repo, project_id):
    started = datetime.now(timezone.utc)
    cohorts = inventory(repo, project_id)['cohorts']
    queue = RunQueue(repo.url)
    result = [measure(c, lambda task, run: release_status(queue, repo, task, run)) for c in cohorts]
    from .pilot_usage import read as read_usage
    for cohort in result:
        cohort['usage'] = read_usage(repo, project_id, cohort['cohort_id'])
    return {'project_id': str(project_id), 'basis': 'FROZEN_COHORT_CURRENT_DELIVERY_V1',
            'checked_from': started, 'checked_until': datetime.now(timezone.utc), 'cohorts': result,
            'limitations': [
                '分母固定為每組登錄的 20 案；未綁定、失敗、取消或無法檢查的案例不移除。',
                '交付數逐案重驗最新版 Release gate；不是情境驗收率或首次通過率，亦非全組同時點的原子快照。',
                '總經過時間從首版建立至目前交付核准，包含等待、失敗與修訂；不是人工操作工時。',
                '人工基準、操作工時、首次通過率、費率及完整情境證據評估尚未完成，不以零或推估值替代。']}
