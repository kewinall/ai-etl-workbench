"""Actual isolated PostgreSQL authorization/claim, no provider or ETL calls."""
from copy import deepcopy
import pytest
from app.sa_contract import build_sa_context
from app.sa_gateway import sa_material
from app.sa_journal import SAJournal
from app.sa_work_queue import SAWorkQueue,authorization_offer
from test_run_queue_integration import context,pytestmark
from test_excel_preparation_integration import prepared_excel


@pytest.mark.parametrize('stale_prompt',[False,True])
def test_excel_sa_durable_material_claim_and_no_repeat(context,tmp_path,monkeypatch,stale_prompt):
    queue,task_id,run,*_=prepared_excel(context,tmp_path,monkeypatch)
    run=queue.detail(task_id,run['run_id'])
    material=sa_material(build_sa_context(run))
    work=SAWorkQueue(queue)
    authorization=authorization_offer(run)
    reserved=work.enqueue(task_id,run['run_id'],authorization)
    assert reserved['status']=='SA_QUEUED'
    with queue.conn() as conn:
        row=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_sa'",(run['run_id'],)).fetchone()
    assert row['prompt_version']==7
    assert row['input_json']['prompt']==material['prompt']
    assert row['input_json']['prompt_checksum']==authorization['prompt_checksum']==material['prompt_checksum']
    if stale_prompt:
        # Simulate a newer deployment, without bypassing immutable journal rows.
        def changed(context):
            updated=deepcopy(material);updated['prompt_version']=8
            return updated
        monkeypatch.setattr('app.sa_work_queue.sa_material',changed)
        assert work.claim()['status']=='STALE_NOT_DISPATCHED'
    else:
        claimed=work.claim()
        assert claimed['status']=='DISPATCH_RESERVED'
        assert claimed['input_json']['prompt']==material['prompt']
        assert claimed['prompt_version']==7
    assert work.claim() is None
    assert not queue.detail(task_id,run['run_id'])['write_started']
    assert SAJournal(queue).read(task_id,run['run_id'])['invocation']['prompt_version']==7
