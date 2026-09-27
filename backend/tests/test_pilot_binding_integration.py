"""Prospective membership and complete run denominator on isolated PostgreSQL."""
import os
from contextlib import contextmanager
from uuid import uuid4
import psycopg
import pytest
from app.pilot_cohort import PilotCohortPlan, register, inventory, bind_task, PilotEnrollmentConflict
from app.run_queue import RunQueue
from test_pilot_cohort import plan_payload
from test_run_queue_integration import context

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1',
                              reason='Isolated PostgreSQL required')


def test_binding_preserves_cancelled_and_all_revisions_and_blocks_reassignment(context):
    original, task_id = context
    with original.conn() as conn:
        with conn.transaction(force_rollback=True):
            class Repo:
                @contextmanager
                def conn(self):
                    with conn.transaction(): yield conn
            repo = Repo()
            queue = RunQueue(original.url)
            queue.conn = repo.conn
            project = conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s',
                                   (task_id,)).fetchone()['project_id']
            cohort = register(repo, project, PilotCohortPlan(**plan_payload()))['cohort_id']
            first = bind_task(repo, project, cohort, 'case-00', task_id)
            assert bind_task(repo, project, cohort, 'case-00', task_id) == first
            with pytest.raises(PilotEnrollmentConflict):
                bind_task(repo, project, cohort, 'case-01', task_id)
            run = queue.enqueue(task_id, 'pilot-binding-first')
            queue.cancel_unstarted(task_id, run['run_id'])
            second = queue.enqueue(task_id, 'pilot-binding-second')
            # A response-loss replay remains valid after execution preparation begins.
            assert bind_task(repo, project, cohort, 'case-00', task_id) == first
            saved = inventory(repo, project)['cohorts'][0]
            assert saved['registered_cases'] == 20 and saved['bound_cases'] == 1
            # Both are created inside one rollback-only transaction, so now() ties.
            # Inventory must retain both; UUID tie-breaking does not prove first-attempt order.
            assert {str(row['run_id']):row['state'] for row in saved['cases'][0]['runs']} == {
                str(run['run_id']):'CANCELLED', str(second['run_id']):'QUEUED'}
            assert all(case['runs'] == [] for case in saved['cases'][1:])
            with pytest.raises(PilotEnrollmentConflict):
                bind_task(repo, uuid4(), cohort, 'case-00', task_id)
            with pytest.raises(PilotEnrollmentConflict):
                bind_task(repo, project, cohort, 'case-01', task_id)
            for sql, args in [
                ('DELETE FROM platform.pilot_case_task WHERE task_id=%s', (task_id,)),
                ('UPDATE platform.task SET project_id=%s WHERE task_id=%s', (uuid4(), task_id)),
            ]:
                with pytest.raises(psycopg.Error):
                    with conn.transaction(): conn.execute(sql, args)


def test_cannot_enroll_previously_started_task(context):
    queue, task_id = context
    queue.enqueue(task_id, 'pilot-already-started')
    with queue.conn() as conn:
        with conn.transaction(force_rollback=True):
            class Repo:
                @contextmanager
                def conn(self):
                    with conn.transaction(): yield conn
            repo = Repo()
            project = conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s',
                                   (task_id,)).fetchone()['project_id']
            cohort = register(repo, project, PilotCohortPlan(**plan_payload()))['cohort_id']
            with pytest.raises(PilotEnrollmentConflict, match='事後'):
                bind_task(repo, project, cohort, 'case-00', task_id)
            with pytest.raises(psycopg.Error, match='PILOT_TASK_ALREADY_STARTED'):
                with conn.transaction():
                    conn.execute('INSERT INTO platform.pilot_case_task(cohort_id,case_key,task_id) VALUES(%s,%s,%s)',
                                 (cohort, 'case-00', task_id))
