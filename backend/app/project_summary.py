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
