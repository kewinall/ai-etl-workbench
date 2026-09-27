"""Real isolated PostgreSQL atomicity; synthetic upload receipts, no ETL claim."""
from contextlib import contextmanager
from hashlib import sha256
import os
from uuid import uuid4

import pytest

from app.pilot_cohort import register, inventory, PilotEnrollmentConflict
from app.pilot_fixture_catalog import template
from app.pilot_prepare_service import prepare
from app.repository import PostgresRepository
from test_run_queue_integration import context

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1',
                              reason='Isolated PostgreSQL required')


def test_prepare_atomic_idempotent_and_rollback(context, monkeypatch):
    queue, task_id = context
    uploads = []
    def upload(name, content, *args):
        uploads.append(name)
        return {'source_type': 'CSV', 'upload_id': str(uuid4()), 'original_name': name,
                'path': '/synthetic-test/source.csv', 'size': len(content),
                'checksum': sha256(content).hexdigest(),
                'fields': [{'name': name} for name in content.decode().splitlines()[0].split(',')]}
    monkeypatch.setattr('app.pilot_prepare_service.save_and_profile', upload)
    with queue.conn() as conn:
        with conn.transaction(force_rollback=True):
            repo = PostgresRepository(queue.url)
            @contextmanager
            def shared():
                with conn.transaction(): yield conn
            repo.conn = shared
            project = conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s',
                                   (task_id,)).fetchone()['project_id']
            cohort = register(repo, project, template())['cohort_id']
            first = prepare(repo, project, cohort, 'success-filter-aggregate')
            repeat = prepare(repo, project, cohort, 'success-filter-aggregate')
            assert first['created'] and not repeat['created']
            assert repeat['task_id'] == first['task_id'] and len(uploads) == 1
            assert inventory(repo, project)['cohorts'][0]['bound_cases'] == 1
            assert conn.execute('SELECT count(*) n FROM platform.task_run WHERE task_id=%s',
                                (first['task_id'],)).fetchone()['n'] == 0
            assert repo.get_task(first['task_id'])['status'] == 'CREATED'
            with pytest.raises(PilotEnrollmentConflict):
                prepare(repo, uuid4(), cohort, 'success-filter-aggregate')
            assert len(uploads) == 1
            before = conn.execute('SELECT count(*) n FROM platform.task').fetchone()['n']
            def fail(*args): raise RuntimeError('synthetic bind failure')
            monkeypatch.setattr('app.pilot_prepare_service.bind_task', fail)
            with pytest.raises(RuntimeError, match='synthetic bind failure'):
                prepare(repo, project, cohort, 'success-date-boundaries')
            assert conn.execute('SELECT count(*) n FROM platform.task').fetchone()['n'] == before
            assert inventory(repo, project)['cohorts'][0]['bound_cases'] == 1
