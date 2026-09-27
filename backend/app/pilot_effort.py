"""Strict effort-event interpretation; not a source of historical time estimates.

Timestamps must come from the future server-side recorder. This module alone
does not authenticate actors, persist evidence or make a cohort comparable.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EffortEvent(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    sequence: int = Field(strict=True, gt=0)
    session_id: str = Field(min_length=1, max_length=100)
    case_key: str = Field(min_length=1, max_length=60)
    protocol_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    actor: Literal['HUMAN', 'DELEGATED_AGENT', 'FUNCTIONAL_TEST']
    mode: Literal['WORKBENCH', 'MANUAL_BASELINE']
    action: Literal['START', 'STOP', 'ABANDON']
    recorded_at: datetime

    @model_validator(mode='after')
    def aware_time(self):
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError('EFFORT_TIMEZONE_REQUIRED')
        return self


def summarize(events: list[EffortEvent]):
    """Single-operator event stream; do not sort or repair corrupt records."""
    active = None
    seen = set()
    completed = []
    abandoned = 0
    previous = None
    for event in events:
        if previous and (event.sequence != previous.sequence + 1 or event.recorded_at < previous.recorded_at):
            raise ValueError('EFFORT_EVENT_ORDER_INVALID')
        if previous is None and event.sequence != 1:
            raise ValueError('EFFORT_EVENT_ORDER_INVALID')
        if event.action == 'START':
            if active is not None or event.session_id in seen:
                raise ValueError('EFFORT_OVERLAP_OR_REUSED_SESSION')
            active = event
            seen.add(event.session_id)
        else:
            if active is None or any(getattr(active, key) != getattr(event, key) for key in
                    ('session_id', 'case_key', 'protocol_checksum', 'actor', 'mode')):
                raise ValueError('EFFORT_SESSION_BINDING_MISMATCH')
            if event.action == 'STOP':
                completed.append({'case_key': event.case_key, 'mode': event.mode,
                    'actor': event.actor, 'protocol_checksum': event.protocol_checksum,
                    'seconds': (event.recorded_at - active.recorded_at).total_seconds()})
            else:
                abandoned += 1
            active = None
        previous = event
    totals = {}
    for mode in ('WORKBENCH', 'MANUAL_BASELINE'):
        human = [r for r in completed if r['actor'] == 'HUMAN' and r['mode'] == mode]
        totals[mode] = {'recorded_human_seconds': sum(r['seconds'] for r in human) if human else None,
                        'recorded_sessions': len(human)}
    return {'basis': 'RECORDED_SESSIONS_ONLY', 'totals': totals,
            'completed': completed, 'abandoned_sessions': abandoned,
            'open_session': active.session_id if active else None,
            'excluded_nonhuman_sessions': sum(r['actor'] != 'HUMAN' for r in completed),
            'coverage_complete': False, 'comparison_ready': False, 'improvement_rate': None}
