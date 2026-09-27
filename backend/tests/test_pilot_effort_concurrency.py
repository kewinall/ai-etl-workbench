"""Two real connections, committed synthetic events in a disposable test DB."""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
import pytest

from app.migrations import migrate
from app.pilot_cohort import PilotCohortPlan, register
from app.pilot_effort_store import record, read
from test_pilot_cohort import plan_payload

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated PostgreSQL required')


def test_concurrent_start_and_stop_preserve_one_interval():
    source = os.environ['DATABASE_URL']
    connection = conninfo_to_dict(source)
    assert connection.get('host') == 'postgres' and connection.get('dbname') == 'workbench'
    name = 'effort_race_' + uuid4().hex
    assert re.fullmatch(r'effort_race_[a-f0-9]{32}', name)
    url = make_conninfo(source, dbname=name)
    with psycopg.connect(source, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            migrate(url, Path('/app/database/migrations'))
            class Repo:
                @contextmanager
                def conn(self):
                    with psycopg.connect(url, row_factory=dict_row) as conn:
                        conn.execute("SET statement_timeout='8s'")
                        yield conn
            repo = Repo()
            project = uuid4()
            with repo.conn() as conn:
                conn.execute('INSERT INTO platform.project(project_id,project_name) VALUES(%s,%s)', (project,'Synthetic race'))
            cohort = register(repo, project, PilotCohortPlan(**plan_payload()))['cohort_id']

            def race(keys, action='START', session_id=None):
                barrier = Barrier(2)
                def invoke(key):
                    barrier.wait(timeout=5)
                    try:
                        return record(repo, project, cohort, 'case-00', key, action=action,
                            actor='FUNCTIONAL_TEST', mode='WORKBENCH', session_id=session_id)
                    except ValueError as error:
                        return str(error)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    return list(pool.map(invoke, keys))

            starts = race(['race-same-start', 'race-same-start'])
            assert starts[0] == starts[1] and starts[0]['sequence'] == 1
            ends = race(['race-same-stop', 'race-same-stop'], 'STOP', starts[0]['session_id'])
            assert ends[0] == ends[1] and ends[0]['sequence'] == 2
            different = race(['race-distinct-a', 'race-distinct-b'])
            winners = [r for r in different if isinstance(r, dict)]
            assert len(winners) == 1
            assert 'EFFORT_OPEN_SESSION_REQUIRES_CLOSE' in different
            different_ends = race(['race-end-a', 'race-end-b'], 'STOP', winners[0]['session_id'])
            assert sum(isinstance(r, dict) for r in different_ends) == 1
            assert 'EFFORT_SESSION_NOT_ACTIVE' in different_ends
            result = read(repo, project, cohort, 'case-00')
            assert [r['sequence'] for r in result['events']] == [1,2,3,4]
            assert result['summary']['excluded_nonhuman_sessions'] == 2
            assert result['summary']['totals']['WORKBENCH']['recorded_human_seconds'] is None
            assert result['recovery'] is None
        finally:
            # Only the exact random database created above; no FORCE/other DB cleanup.
            assert re.fullmatch(r'effort_race_[a-f0-9]{32}', name)
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
            assert admin.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone() is None
