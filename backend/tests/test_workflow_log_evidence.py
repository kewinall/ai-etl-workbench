import pytest
from app.workflow_log_evidence import workflow_log_evidence
from test_hop_log_evidence import LINE

NAME='etl_0123456789abcdef'
PREFIX=f'2026/09/17 13:24:19 - {NAME} - '.encode()
START=PREFIX+b'Starting action [Run pipeline]\n'
SUCCESS=PREFIX+b'Finished action [Run pipeline] (result=[true])\n'
FAILURE=PREFIX+b'Finished action [Run pipeline] (result=[false])\n'
END=PREFIX+b'Workflow execution finished\n'


def result(content):
    return workflow_log_evidence(dict(started=True,reason='EXITED',exit_code=0,output=content),['target'],NAME)


def test_fixed_workflow_requires_pipeline_and_action_success():
    value=result(START+LINE+SUCCESS+END)
    assert value['workflow_completed'] and value['result']['status']=='COMPLETED'
    assert not value['qa_passed']


@pytest.mark.parametrize('content',[LINE,START+LINE+SUCCESS,START+LINE+END,
    START+LINE+SUCCESS+SUCCESS+END,START+START+LINE+SUCCESS+END,
    START+LINE+SUCCESS+END+END,END+START+LINE+SUCCESS,
    START+LINE+FAILURE+END,START+LINE+SUCCESS+FAILURE+END,
    START+SUCCESS+END, (START+LINE+SUCCESS+END).replace(NAME.encode(),b'etl_ffffffffffffffff')])
def test_missing_duplicate_failed_foreign_or_reordered_workflow_never_passes(content):
    value=result(content)
    assert not value['workflow_completed'] and value['result']['status']!='COMPLETED'
