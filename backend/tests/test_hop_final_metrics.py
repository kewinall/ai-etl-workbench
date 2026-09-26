from app.hop_log_evidence import hop_log_evidence
import pytest


def check(text,code=0,reason='EXITED'):
    return hop_log_evidence(dict(output=text.encode(),started=True,exit_code=code,reason=reason),['source','discard'])


GOOD='WORKBENCH_NODE_V1 source 1 0 0 1 0 0\nWORKBENCH_NODE_V1 discard 0 0 0 0 0 0\nWORKBENCH_METRICS_END_V1 2\n'


def test_authoritative_zero_node():
    result=check(GOOD)
    assert result['result']['status']=='COMPLETED'
    assert result['nodes']['discard']['read']==0


@pytest.mark.parametrize('text',[GOOD.replace('END_V1 2','END_V1 3'),GOOD+GOOD,
    GOOD.replace('WORKBENCH_NODE_V1 discard 0 0 0 0 0 0\n',''),
    GOOD.replace('discard 0','discard -1'),GOOD.replace('discard','other'),
    GOOD.replace('WORKBENCH_METRICS_END_V1 2\n',''),
    GOOD+'WORKBENCH_NODE_V1 other 0 0 0 0 0 0\n',
    '2026/09/26 10:00:00 - source.0 - Finished processing (I=2, O=0, R=0, W=2, U=0, E=0)\n'+GOOD])
def test_incomplete_or_conflicting_metrics_never_pass(text):
    assert check(text)['result']['status']=='UNKNOWN'


def test_failure_and_timeout_not_overridden():
    assert check(GOOD,1)['result']['status']=='FAILED'
    assert check(GOOD,0,'TIMED_OUT')['result']['status']=='UNKNOWN'
    assert check(GOOD.replace('discard 0 0 0 0 0 0','discard 0 0 0 0 0 1'))['result']['status']=='FAILED'
