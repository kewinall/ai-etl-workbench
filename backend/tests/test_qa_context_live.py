"""Explicitly selected persisted real execution; no model, ETL or data writes."""
import os
import pytest
from uuid import uuid4
from app.run_queue import RunQueue
from app.qa_context import load_qa_context
from app.qa_contract import REQUIRED_CHECKS

pytestmark=pytest.mark.skipif(not os.getenv('WORKBENCH_QA_CONTEXT_RUN'),reason='Explicit persisted execution required')


def selected():
    assert os.getenv('DATABASE_HOST')=='postgres' and os.getenv('DATABASE_NAME')=='workbench'
    return RunQueue(os.environ['DATABASE_URL']),os.environ['WORKBENCH_QA_CONTEXT_TASK'],os.environ['WORKBENCH_QA_CONTEXT_RUN'],os.environ['WORKBENCH_QA_CONTEXT_COMPARISON']


def test_context_is_repeatable_and_excludes_runtime_settings():
    queue,task,run,comparison=selected()
    first=load_qa_context(queue,task,run,comparison)
    second=load_qa_context(queue,task,run,comparison)
    assert first['context']==second['context']
    assert {e['id'] for e in first['context']['evidence']}==set(REQUIRED_CHECKS)
    assert all(e['status']=='PASS' for e in first['context']['evidence'])
    assert set(first['context'])=={'version','run_id','specification_checksum','evidence','context_checksum','semantics'}
    assert first['context']['version']==3
    assert first['context']['semantics']['requirement']==first['run']['input_snapshot']['requirement_text']
    assert first['context']['semantics']['nodes']
    assert not any(key in str(first['context']['semantics']) for key in ('password','secret_ref','file_path','connection_id'))
    assert not first['qa_approved'] and not first['release_ready']


def test_foreign_comparison_is_not_accepted():
    queue,task,run,_=selected()
    with pytest.raises(ValueError,match='QA_EVIDENCE_NOT_FOUND'):
        load_qa_context(queue,task,run,str(uuid4()))
