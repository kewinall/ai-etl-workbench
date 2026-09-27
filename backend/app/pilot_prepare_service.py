"""Create and prospectively bind one synthetic Task, never enqueue a Run."""
from contextlib import contextmanager
from copy import copy

from .pilot_case_preparation import registered_case, build_task_payload
from .pilot_cohort import bind_task, PilotEnrollmentConflict
from .task_uploads import save_and_profile


def prepare(repo, project_id, cohort_id, case_key):
    with repo.conn() as conn:
        case = conn.execute('''SELECT c.definition FROM platform.pilot_cohort_case c
            JOIN platform.pilot_cohort p USING(cohort_id)
            WHERE c.cohort_id=%s AND c.case_key=%s AND p.project_id=%s
            FOR UPDATE OF c''', (cohort_id, case_key, project_id)).fetchone()
        if not case:
            raise PilotEnrollmentConflict('找不到此專案的案例')
        try:
            frozen = registered_case(case['definition'])
        except ValueError:
            raise PilotEnrollmentConflict('案例與固定目錄指紋不一致，未建立 Task') from None
        prior = conn.execute('''SELECT b.task_id FROM platform.pilot_case_task b
            WHERE b.cohort_id=%s AND b.case_key=%s''', (cohort_id, case_key)).fetchone()
        if prior:
            # Read-only replay, even if the bound Task has since been executed.
            return {'task_id': prior['task_id'], 'created': False, 'run_enqueued': False,
                    'message': '案例已有固定 Task；本次未建立、上傳或啟動執行。'}
        policy = repo.setting('upload_policy', {}) or {}
        receipts = [save_and_profile(source['filename'], source['content'].encode('utf-8'),
                                    int(policy.get('retention_days', 7)), int(policy.get('max_file_mb', 50)))
                    for source in frozen['fixture']['sources']]
        payload = build_task_payload(project_id, cohort_id, case['definition'], receipts)
        # Repository methods use nested transactions on the same connection.
        # Never replace conn() on the shared web application's repository.
        scoped = copy(repo)
        @contextmanager
        def nested_connection():
            with conn.transaction():
                yield conn
        scoped.conn = nested_connection
        task = scoped.create_task(payload)
        bind_task(scoped, project_id, cohort_id, case_key, task['id'])
        # Failure rolls back Task, nodes, creation key and binding together.
        # Uploaded orphan bytes on failure are retained for safe later cleanup;
        # they are not attached to a Task and never authorize execution.
        return {'task_id': task['id'], 'created': True, 'run_enqueued': False,
                'message': '已核對固定樣本並建立、綁定 Task；尚未執行或通過驗收。'}
