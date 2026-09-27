"""Persisted project evidence inventory, not a claim of measured Pilot improvement."""


def read(repo, project_id):
    with repo.conn() as conn:
        rows = conn.execute('''
            SELECT t.task_id, t.task_name AS name, r.run_id, r.state, r.phase, r.outcome_code,
                   r.created_at,
                   (SELECT count(*) FROM platform.release_delivery d
                    JOIN platform.release_candidate_record c USING(candidate_id)
                    WHERE c.run_id=r.run_id AND c.task_id=t.task_id AND c.project_id=t.project_id) AS historical_release_count
            FROM platform.task t
            LEFT JOIN platform.task_run r ON r.task_id=t.task_id
            WHERE t.project_id=%s
            ORDER BY t.created_at DESC,t.task_id,r.created_at DESC,r.run_id DESC
        ''', (project_id,)).fetchall()
    return {'project_id':str(project_id), 'basis':'ALL_PERSISTED_RUNS',
            'cases':[dict(row) for row in rows],
            'comparison_ready':False, 'human_baseline':None,
            'improvement_rate':None, 'cost':None,
            'limitations':['案例尚未正式納入比較 cohort，不計算成功率或改善率。',
                           '歷史 Release 數量不代表目前證據仍有效，下載須重新通過交付核對。',
                           '人工基準與費率版本尚未提供，不以估算值冒充實測。']}
