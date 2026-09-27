"""Real isolated PostgreSQL; rollback-only synthetic prospective registrations."""
import os
from contextlib import contextmanager
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
import pytest
from app.pilot_cohort import PilotCohortPlan, register, inventory
from test_pilot_cohort import plan_payload

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1',
                              reason='Isolated PostgreSQL required')


def test_registration_round_trip_idempotence_scope_and_immutability():
    assert os.getenv('DATABASE_HOST') == 'postgres'
    with psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row) as conn:
        with conn.transaction(force_rollback=True):
            project = uuid4()
            conn.execute('INSERT INTO platform.project(project_id,project_name) VALUES(%s,%s)',
                         (project, f'Synthetic cohort {project}'))
            class Repo:
                @contextmanager
                def conn(self):
                    with conn.transaction():
                        yield conn
            repo = Repo()
            plan = PilotCohortPlan(**plan_payload())
            first = register(repo, project, plan)
            second = register(repo, project, plan)
            assert first['cohort_id'] == second['cohort_id']
            assert first['execution_verified'] is False
            saved = inventory(repo, project)['cohorts']
            assert len(saved) == 1
            assert len(saved[0]['cases']) == 20
            assert [case['ordinal'] for case in saved[0]['cases']] == list(range(1, 21))
            assert saved[0]['comparison_ready'] is False
            assert inventory(repo, uuid4())['cohorts'] == []
            for sql in (
                'DELETE FROM platform.pilot_cohort_case WHERE cohort_id=%s',
                "UPDATE platform.pilot_cohort SET name='changed' WHERE cohort_id=%s",
            ):
                with pytest.raises(psycopg.Error):
                    with conn.transaction():
                        conn.execute(sql, (first['cohort_id'],))
            assert len(inventory(repo, project)['cohorts'][0]['cases']) == 20
