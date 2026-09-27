from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.pilot_effort import EffortEvent, summarize


def event(sequence, action, seconds, **changes):
    payload = dict(sequence=sequence, session_id='session-1', case_key='case-01',
        protocol_checksum='a'*64, actor='HUMAN', mode='WORKBENCH', action=action,
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc)+timedelta(seconds=seconds))
    return EffortEvent(**(payload | changes))


def test_only_closed_human_active_intervals_count_not_waits():
    result = summarize([event(1, 'START', 0), event(2, 'STOP', 10),
        event(3, 'START', 100, session_id='session-2'), event(4, 'STOP', 105, session_id='session-2')])
    assert result['totals']['WORKBENCH']['recorded_human_seconds'] == 15
    assert result['totals']['MANUAL_BASELINE']['recorded_human_seconds'] is None
    assert result['comparison_ready'] is False and result['improvement_rate'] is None


@pytest.mark.parametrize('actor', ['DELEGATED_AGENT', 'FUNCTIONAL_TEST'])
def test_nonhuman_never_counts_as_human(actor):
    result = summarize([event(1, 'START', 0, actor=actor), event(2, 'STOP', 10, actor=actor)])
    assert result['totals']['WORKBENCH']['recorded_human_seconds'] is None
    assert result['excluded_nonhuman_sessions'] == 1


def test_open_abandoned_and_empty_are_not_zero_completed_effort():
    for events in ([], [event(1, 'START', 0)], [event(1, 'START', 0), event(2, 'ABANDON', 10)]):
        result = summarize(events)
        assert result['totals']['WORKBENCH']['recorded_human_seconds'] is None
        assert not result['coverage_complete']


@pytest.mark.parametrize('change', [dict(session_id='other'), dict(case_key='case-02'),
    dict(protocol_checksum='b'*64), dict(actor='DELEGATED_AGENT'), dict(mode='MANUAL_BASELINE')])
def test_stop_must_match_start_binding(change):
    with pytest.raises(ValueError, match='BINDING'):
        summarize([event(1, 'START', 0), event(2, 'STOP', 10, **change)])


def test_reject_overlap_clock_reversal_gaps_or_missing_start():
    for events in ([event(1, 'START', 0), event(2, 'START', 1, session_id='second')],
                   [event(1, 'START', 10), event(2, 'STOP', 0)],
                   [event(1, 'START', 0), event(3, 'STOP', 10)], [event(1, 'STOP', 10)]):
        with pytest.raises(ValueError): summarize(events)


def test_reject_naive_time_and_unmeasured_claims():
    with pytest.raises(ValidationError): event(1, 'START', 0, recorded_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError): event(1, 'START', 0, inferred_seconds=100)


def test_manual_baseline_separate_and_not_automatically_comparable():
    result = summarize([event(1, 'START', 0, mode='MANUAL_BASELINE'),
                        event(2, 'STOP', 12, mode='MANUAL_BASELINE')])
    assert result['totals']['MANUAL_BASELINE']['recorded_human_seconds'] == 12
    assert result['totals']['WORKBENCH']['recorded_human_seconds'] is None
    assert result['comparison_ready'] is False


def test_self_reported_human_is_measured_but_not_identity_verified():
    result = summarize([event(1,'START',0,actor='HUMAN_SELF_REPORTED'),
                        event(2,'STOP',8,actor='HUMAN_SELF_REPORTED')])
    assert result['totals']['WORKBENCH']['recorded_human_seconds'] == 8
    assert result['excluded_nonhuman_sessions'] == 0
    assert result['identity_verified'] is False
    assert result['human_source'] == 'OPERATOR_SELF_DECLARATION'
    assert result['comparison_ready'] is False
