"""Read-only latest-Run summary. Legacy Task success never grants QA/release."""


def project_summary(repo,project_id):
    with repo.conn() as conn:
        rows=conn.execute('''
            SELECT COALESCE(latest.state,'NO_RUN') AS state,count(*) AS count
            FROM platform.task t
            LEFT JOIN LATERAL (
                SELECT r.state FROM platform.task_run r WHERE r.task_id=t.task_id
                ORDER BY r.created_at DESC,r.run_id DESC LIMIT 1
            ) latest ON true
            WHERE t.project_id=%s
            GROUP BY COALESCE(latest.state,'NO_RUN') ORDER BY state
        ''',(project_id,)).fetchall()
    return {'project_id':str(project_id),'basis':'LATEST_RUN_PER_TASK',
            'task_count':sum(row['count'] for row in rows),
            'states':[dict(row) for row in rows],
            'qa_evaluated':False,'release_evaluated':False}


def workflow_overview(queue, repo, project_id):
    """Per-Task status from the same read-only aggregator used by each Task page.

    A Task whose status cannot be verified is reported as 待確認/stale, never as zero or complete."""
    from .workflow_status import read as workflow_read
    with queue.conn() as conn:
        rows = conn.execute('''
            SELECT t.task_id,latest.run_id FROM platform.task t
            LEFT JOIN LATERAL (
                SELECT r.run_id FROM platform.task_run r WHERE r.task_id=t.task_id
                ORDER BY r.created_at DESC,r.run_id DESC LIMIT 1
            ) latest ON true
            WHERE t.project_id=%s ORDER BY t.task_id
        ''', (project_id,)).fetchall()
    tasks, counts = [], {}
    for row in rows:
        entry = {'task_id': row['task_id'], 'run_id': str(row['run_id']) if row['run_id'] else None,
                 'category': '待你確認', 'current_stage': 'requirements',
                 'next_action': '建立準備版本', 'effective_status': '尚未建立準備版本',
                 'delivered': False, 'waiting': False, 'stale': False}
        if row['run_id']:
            try:
                status = workflow_read(queue, repo, row['task_id'], row['run_id'])
                entry.update(category=status['category'], current_stage=status['current_stage'],
                             next_action=status['next_action']['label'], effective_status=status['effective_status'],
                             delivered=status['delivered'], waiting=status['waiting'])
            except Exception:
                entry.update(category='待確認', current_stage=None, next_action='重新讀取此 Task 狀態',
                             effective_status='狀態無法核對', stale=True)
        counts[entry['category']] = counts.get(entry['category'], 0) + 1
        tasks.append(entry)
    return {'workflow_basis': 'WORKFLOW_STATUS_LATEST_RUN', 'workflow_counts': counts,
            'workflow_unverified': sum(1 for t in tasks if t['stale']), 'tasks': tasks}
