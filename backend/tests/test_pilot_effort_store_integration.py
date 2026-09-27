"""Rollback-only synthetic storage acceptance; never human timing evidence."""
import os
from contextlib import contextmanager
from uuid import uuid4
import psycopg
import pytest
from psycopg.rows import dict_row
from app.pilot_cohort import PilotCohortPlan, register
from app.pilot_effort_store import record, _events, _summary
from test_pilot_cohort import plan_payload

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated PostgreSQL required')


def test_effort_storage_scope_replay_immutability_and_expiry(monkeypatch):
    assert os.environ['DATABASE_HOST'] == 'postgres'
    with psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row) as conn:
        with conn.transaction(force_rollback=True):
            class Repo:
                @contextmanager
                def conn(self):
                    with conn.transaction(): yield conn
            repo=Repo(); project=uuid4()
            conn.execute('INSERT INTO platform.project(project_id,project_name) VALUES(%s,%s)', (project, 'Synthetic effort'))
            cohort=register(repo, project, PilotCohortPlan(**plan_payload()))['cohort_id']
            def call(key, action='START', **kwargs):
                return record(repo, project, cohort, 'case-00', key, action=action,
                    actor='FUNCTIONAL_TEST', mode='WORKBENCH', **kwargs)
            first=call('effort-start-test')
            assert call('effort-start-test') == first
            with pytest.raises(ValueError, match='OPEN_SESSION'): call('effort-second-test')
            with pytest.raises(ValueError, match='SCOPE'):
                record(repo, uuid4(), cohort, 'case-00', 'effort-start-test', action='START', actor='FUNCTIONAL_TEST', mode='WORKBENCH')
            with pytest.raises(ValueError, match='ATTESTATION'):
                record(repo, project, cohort, 'case-00', 'effort-human-test', action='START', actor='HUMAN', mode='WORKBENCH')
            stopped=call('effort-stop-test', 'STOP', session_id=first['session_id'])
            assert stopped['action']=='STOP'
            assert call('effort-stop-test', 'STOP', session_id=first['session_id']) == stopped
            second=call('effort-next-test')
            monkeypatch.setattr('app.pilot_effort_store.MAX_INTERVAL_SECONDS', -1)
            expired=call('effort-expired-test', 'STOP', session_id=second['session_id'])
            assert expired['action']=='ABANDON'
            assert call('effort-expired-test', 'STOP', session_id=second['session_id']) == expired
            summary=_summary(_events(conn))
            assert summary['abandoned_sessions']==1
            assert summary['excluded_nonhuman_sessions']==1
            assert summary['totals']['WORKBENCH']['recorded_human_seconds'] is None
            for query in ('DELETE FROM platform.pilot_effort_event', 'UPDATE platform.pilot_effort_event SET mode=mode'):
                with pytest.raises(psycopg.Error):
                    with conn.transaction(): conn.execute(query)
