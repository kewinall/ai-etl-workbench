import pytest
from pydantic import ValidationError
from app.pilot_effort_request import EffortRequest


def payload():
    return dict(request_key='synthetic-request',action='START',actor='FUNCTIONAL_TEST',mode='WORKBENCH',
                expected_protocol_checksum='a'*64,confirmed=True)


@pytest.mark.parametrize('change', [dict(confirmed=False),dict(confirmed=1),dict(actor='HUMAN'),
    dict(actor='HUMAN_SELF_REPORTED'),dict(human_attested=True),dict(recorded_at='2026-01-01'),
    dict(seconds=100),dict(action='STOP')])
def test_reject_unconfirmed_or_fabricated_effort(change):
    with pytest.raises(ValidationError): EffortRequest(**(payload()|change))


def test_explicit_self_report_not_identity_verification():
    assert EffortRequest(**(payload()|dict(actor='HUMAN_SELF_REPORTED',human_attested=True))).human_attested
