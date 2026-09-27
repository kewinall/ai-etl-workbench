"""Internal prospective recorder. Human recording remains disabled pending attestation.

No public API accepts timestamps or a claimed human identity. A short interval
must be closed within two minutes; expired intervals are abandoned, never billed
as active effort. UI activity segmentation is a separate, not-yet-enabled layer.
"""
from uuid import UUID, uuid4
from .pilot_effort import EffortEvent, summarize

MAX_INTERVAL_SECONDS = 120
LOCK_ID = 714032954


def _events(conn):
    return conn.execute('SELECT * FROM platform.pilot_effort_event ORDER BY sequence').fetchall()


def _summary(rows):
    return summarize([EffortEvent(**{k: (str(row[k]) if k == 'session_id' else row[k])
        for k in EffortEvent.model_fields}) for row in rows])


def _scope(conn, project_id, cohort_id, case_key):
    row = conn.execute('''SELECT c.plan_checksum FROM platform.pilot_cohort c
        JOIN platform.pilot_cohort_case p USING(cohort_id)
        WHERE c.project_id=%s AND c.cohort_id=%s AND p.case_key=%s''',
        (project_id, cohort_id, case_key)).fetchone()
    if not row:
        raise ValueError('EFFORT_CASE_SCOPE_INVALID')
    return row['plan_checksum']


def read(repo, project_id, cohort_id, case_key):
    """Read-only recovery view; never close, resume or count an open interval."""
    with repo.conn() as conn:
        conn.execute('SELECT pg_advisory_xact_lock_shared(%s)', (LOCK_ID,))
        checksum = _scope(conn, project_id, cohort_id, case_key)
        rows = _events(conn)
        global_summary = _summary(rows)
        scoped = [r for r in rows if str(r['cohort_id']) == str(cohort_id) and r['case_key'] == case_key]
        # Global order was validated above. Rebase only this in-memory projection;
        # the returned persisted events retain their authoritative sequence numbers.
        summary = _summary([{**r, 'sequence': n} for n, r in enumerate(scoped, 1)])
        now = conn.execute('SELECT clock_timestamp() AS stamp').fetchone()['stamp']
        recovery = None
        if summary['open_session']:
            start = scoped[-1]
            age = (now - start['recorded_at']).total_seconds()
            if age < 0:
                raise ValueError('EFFORT_CLOCK_REVERSED')
            recovery = {'session_id': str(start['session_id']),
                'status': 'EXPIRED_REQUIRES_ABANDON' if age > MAX_INTERVAL_SECONDS else 'OPEN_REQUIRES_EXPLICIT_CLOSE',
                'started_at': start['recorded_at'], 'counted_seconds': None,
                'automatic_resume': False}
        return {'project_id': str(project_id), 'cohort_id': str(cohort_id), 'case_key': case_key,
            'protocol_checksum': checksum, 'checked_at': now, 'summary': summary,
            'recovery': recovery, 'other_case_open': bool(global_summary['open_session'] and not recovery),
            'events': [{k: r[k] for k in ('sequence', 'session_id', 'action', 'actor', 'mode', 'recorded_at')} for r in scoped],
            'human_recording_enabled': False, 'comparison_ready': False}


def record(repo, project_id, cohort_id, case_key, request_key, *, action,
           actor, mode, session_id=None):
    if actor not in ('DELEGATED_AGENT', 'FUNCTIONAL_TEST'):
        raise ValueError('EFFORT_HUMAN_ATTESTATION_NOT_ENABLED')
    if mode not in ('WORKBENCH', 'MANUAL_BASELINE') or action not in ('START', 'STOP', 'ABANDON'):
        raise ValueError('EFFORT_ACTION_INVALID')
    if not isinstance(request_key, str) or not 8 <= len(request_key) <= 160:
        raise ValueError('EFFORT_REQUEST_KEY_INVALID')
    if (action == 'START') != (session_id is None):
        raise ValueError('EFFORT_SESSION_REQUIRED_ONLY_FOR_END')
    with repo.conn() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_ID,))
        checksum = _scope(conn, project_id, cohort_id, case_key)
        old = conn.execute('SELECT * FROM platform.pilot_effort_event WHERE request_key=%s', (request_key,)).fetchone()
        if old:
            if (str(old['cohort_id']), old['case_key'], old['actor'], old['mode']) != (str(cohort_id), case_key, actor, mode):
                raise ValueError('EFFORT_REQUEST_CONFLICT')
            # Expired STOP records ABANDON; permit only the same end-session retry.
            if action == 'START' and old['action'] != 'START' or action != 'START' and (
                old['action'] == 'START' or str(old['session_id']) != str(session_id)):
                raise ValueError('EFFORT_REQUEST_CONFLICT')
            return dict(old)
        rows = _events(conn)
        summary = _summary(rows)
        if action == 'START':
            if summary['open_session']:
                raise ValueError('EFFORT_OPEN_SESSION_REQUIRES_CLOSE')
            session_id = uuid4()
        else:
            if summary['open_session'] != str(session_id):
                raise ValueError('EFFORT_SESSION_NOT_ACTIVE')
            start = next(r for r in reversed(rows) if str(r['session_id']) == str(session_id))
            if (str(start['cohort_id']), start['case_key'], start['actor'], start['mode']) != (str(cohort_id), case_key, actor, mode):
                raise ValueError('EFFORT_SESSION_BINDING_MISMATCH')
            now = conn.execute('SELECT clock_timestamp() AS stamp').fetchone()['stamp']
            if (now - start['recorded_at']).total_seconds() > MAX_INTERVAL_SECONDS:
                action = 'ABANDON'
        row = conn.execute('''INSERT INTO platform.pilot_effort_event
            (sequence,request_key,session_id,cohort_id,case_key,protocol_checksum,actor,mode,action)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (len(rows)+1, request_key, UUID(str(session_id)), cohort_id, case_key, checksum, actor, mode, action)).fetchone()
        _summary([*rows, row])  # Fail closed on clock reversal or corrupted stream.
        return dict(row)
