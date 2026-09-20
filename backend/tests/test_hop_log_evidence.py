import pytest
from app.hop_log_evidence import hop_log_evidence

LINE=b'2026/09/13 05:29:11 - target.0 - Finished processing (I=0, O=0, R=3, W=3, U=0, E=0)\n'

def evidence(data=LINE,**changes):
    return hop_log_evidence(dict(started=True,reason='EXITED',exit_code=0,output=data,**changes),['target'])

def test_complete_is_engine_only():
    value=evidence()
    assert value['result']['status']=='COMPLETED' and value['nodes']['target']['read']==3
    assert value['qa_passed'] is False

@pytest.mark.parametrize('data',[b'',LINE+LINE,LINE.replace(b'target.0',b'other.0')])
def test_missing_duplicate_or_unexpected_nodes_never_pass(data):
    assert evidence(data)['result']['status']=='UNKNOWN'

def test_nonterminal_and_failure():
    for reason in ('TIMEOUT','OUTPUT_LIMIT','OUTPUT_NOT_CLOSED','CANCELLED'):
        value=hop_log_evidence(dict(started=True,reason=reason,exit_code=0,output=LINE),['target'])
        assert value['result']['status']=='UNKNOWN'
    assert evidence(LINE.replace(b'E=0',b'E=1'))['result']['status']=='FAILED'
