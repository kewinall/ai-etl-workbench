"""Recorded interval coverage is never complete-case effort or improvement."""
from .pilot_effort_store import LOCK_ID, _events, _summary


def coverage(case_keys, summary):
    if len(case_keys)!=20 or len(set(case_keys))!=20:
        raise ValueError('EFFORT_POPULATION_INVALID')
    modes={}
    for mode in ('WORKBENCH','MANUAL_BASELINE'):
        intervals=[r for r in summary['completed'] if r['mode']==mode and r['actor']=='HUMAN_SELF_REPORTED']
        if any(r['case_key'] not in case_keys for r in intervals):
            raise ValueError('EFFORT_CASE_OUTSIDE_COHORT')
        recorded={key:sum(r['seconds'] for r in intervals if r['case_key']==key)
                  for key in case_keys if any(r['case_key']==key for r in intervals)}
        modes[mode]={'recorded_seconds':sum(recorded.values()) if recorded else None,
            'cases_with_recorded_intervals':len(recorded), 'cases_without_recorded_intervals':20-len(recorded),
            'recorded_sessions':len(intervals), 'case_seconds':{key:recorded.get(key) for key in case_keys}}
    return {'status':'RECORDED_INTERVALS_ONLY','denominator':20,'modes':modes,
        'excluded_nonhuman_sessions':summary['excluded_nonhuman_sessions'],
        'abandoned_sessions':summary['abandoned_sessions'], 'has_open_session':summary['open_session'] is not None,
        'identity_verified':False,'complete_case_count':0,'comparison_ready':False,'improvement_rate':None}


def read(repo,project_id,cohort_id):
    with repo.conn() as conn:
        conn.execute('SELECT pg_advisory_xact_lock_shared(%s)',(LOCK_ID,))
        cases=conn.execute('''SELECT p.case_key FROM platform.pilot_cohort_case p
            JOIN platform.pilot_cohort c USING(cohort_id)
            WHERE c.project_id=%s AND c.cohort_id=%s ORDER BY p.ordinal''',(project_id,cohort_id)).fetchall()
        rows=_events(conn)
        _summary(rows)  # Validate global authoritative order before projecting.
        scoped=[r for r in rows if str(r['cohort_id'])==str(cohort_id)]
        summary=_summary([{**r,'sequence':i} for i,r in enumerate(scoped,1)])
    return coverage([r['case_key'] for r in cases],summary)
