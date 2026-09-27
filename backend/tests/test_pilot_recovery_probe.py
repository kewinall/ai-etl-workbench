from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from app import pilot_recovery_probe as probe
from app.pilot_fixture_catalog import corpus


def test_opt_in_required_before_any_access(monkeypatch):
    monkeypatch.delenv('WORKBENCH_SYNTHETIC_FAILURE_PROBE', raising=False)
    queue = Mock()
    with pytest.raises(ValueError, match='EXPLICIT_RECOVERY_PROBE_REQUIRED'):
        probe.run(queue,Mock(),'task','run','binding')
    queue.conn.assert_not_called()


@pytest.mark.parametrize('rows', [[], [{'project_id':'other'}],
                                   [{'project_id':'project'},{'project_id':'project'}]])
def test_enrollment_must_be_unique_same_project(rows):
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = rows
    with pytest.raises(ValueError,match='RECOVERY_ENROLLMENT_REQUIRED'):
        probe.enrolled_scope(conn,{'run':{'project_id':'project'}},'task','binding')


def test_claimed_failure_is_not_retried(monkeypatch):
    monkeypatch.setenv('WORKBENCH_SYNTHETIC_FAILURE_PROBE','frozen-cohort-missing-column-v1')
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = {'specification_id':'spec'}
    @contextmanager
    def connection():
        yield conn
    queue = Mock(); queue.conn = connection
    monkeypatch.setattr(probe,'offer',Mock(return_value={}))
    monkeypatch.setattr(probe,'enrolled_scope',Mock(return_value={}))
    request = {'request_id':'request'}
    claimant = Mock(return_value=request)
    prepare = Mock(side_effect=ValueError('stop'))
    finish = Mock()
    monkeypatch.setattr(probe,'claim',claimant)
    monkeypatch.setattr(probe,'prepare_new_target',prepare)
    monkeypatch.setattr(probe,'finish',finish)
    with pytest.raises(ValueError,match='stop'):
        probe.run(queue,Mock(),'task','run','binding')
    assert claimant.call_count == prepare.call_count == 1
    finish.assert_called_once_with(queue,request,'NEEDS_REVIEW','RECOVERY_PROBE_REQUIRES_EVIDENCE_REVIEW')
