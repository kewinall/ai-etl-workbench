"""Real PostgreSQL dispatch claim + synthetic provider, all journal rows rolled back."""
import os
import json
from contextlib import nullcontext
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from app.run_queue import RunQueue
from app.repository import PostgresRepository
from app.qa_context import load_qa_context
from app.qa_contract import REQUIRED_CHECKS
from app.qa_dispatch import dispatch_qa,claim_dispatch
from app.qa_journal import QAJournal
from app.qa_recovery import reap_expired_qa
from app.local_qa_bridge import handle as native_handle
from app.qa_approval import load_approval_offer,approval_binding,approve_review,read_approval
from app.delivery_context import load_delivery_context

pytestmark=pytest.mark.skipif(not os.getenv('WORKBENCH_QA_CONTEXT_RUN'),reason='Explicit real evidence required')


def test_native_bridge_rejects_real_run_with_non_native_profile(monkeypatch):
    monkeypatch.setenv('WORKBENCH_QA_DISPATCH_ENABLED','true')
    task=os.environ['WORKBENCH_QA_CONTEXT_TASK'];run=os.environ['WORKBENCH_QA_CONTEXT_RUN'];comparison=os.environ['WORKBENCH_QA_CONTEXT_COMPARISON']
    q=RunQueue(os.environ['DATABASE_URL'])
    captured=load_qa_context(q,task,run,comparison)
    assert captured['run']['settings_snapshot']['ai']['provider_type']!='LOCAL_COPILOT'
    with q.conn() as conn:
        before=conn.execute("SELECT count(*) n FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa'",(run,)).fetchone()['n']
    with pytest.raises(ValueError,match='QA_NATIVE_PROFILE_REQUIRED'):
        native_handle(q,dict(action='claim',task_id=task,run_id=run,comparison_id=comparison,
            context_checksum=captured['context']['context_checksum'],authorize_model_call=True))
    with q.conn() as conn:
        assert conn.execute("SELECT count(*) n FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa'",(run,)).fetchone()['n']==before


@pytest.mark.parametrize('expired',[False,True])
def test_recovery_closes_only_expired_claims_without_replay(expired):
    task=os.environ['WORKBENCH_QA_CONTEXT_TASK'];run=os.environ['WORKBENCH_QA_CONTEXT_RUN'];comparison=os.environ['WORKBENCH_QA_CONTEXT_COMPARISON']
    base=RunQueue(os.environ['DATABASE_URL'])
    with base.conn() as connection:
        class Queue(RunQueue):
            def conn(self):return nullcontext(connection)
        q=Queue(base.url)
        try:
            context=load_qa_context(q,task,run,comparison)['context']
            saved=QAJournal(q).reserve(task,run,comparison,context['context_checksum'],True)
            assert reap_expired_qa(q)==0  # An unclaimed intent is not a model timeout.
            connection.execute('''INSERT INTO platform.qa_dispatch_claim(invocation_id,claim_token,expires_at)
                VALUES(%s,gen_random_uuid(),clock_timestamp()+(%s * interval '1 minute'))''',
                (saved['invocation_id'],-1 if expired else 10))
            assert reap_expired_qa(q)==int(expired)
            assert reap_expired_qa(q)==0
            record=QAJournal(q).read(task,run)['invocation']
            assert record['status']==('QA_OUTCOME_UNKNOWN' if expired else 'QA_RESERVED')
            assert record['qa_approved'] is False
            with pytest.raises(ValueError,match='QA_NOT_DISPATCHABLE' if expired else 'QA_DISPATCH_ALREADY_CONSUMED'):
                claim_dispatch(q,task,saved['invocation_id'])
        finally:connection.rollback()


@pytest.mark.parametrize('failure',[False,True])
def test_dispatch_once_and_never_replay_on_failure(failure,monkeypatch):
    assert os.getenv('DATABASE_HOST')=='postgres' and os.getenv('DATABASE_NAME')=='workbench'
    monkeypatch.setenv('WORKBENCH_QA_DISPATCH_ENABLED','true')
    task=os.environ['WORKBENCH_QA_CONTEXT_TASK'];run=os.environ['WORKBENCH_QA_CONTEXT_RUN'];comparison=os.environ['WORKBENCH_QA_CONTEXT_COMPARISON']
    base=RunQueue(os.environ['DATABASE_URL'])
    with base.conn() as connection:
        class Queue(RunQueue):
            def conn(self):return nullcontext(connection)
        class Repo(PostgresRepository):
            def conn(self):return nullcontext(connection)
        q=Queue(base.url);repo=Repo(base.url)
        try:
            context=load_qa_context(q,task,run,comparison)['context']
            def response(**kwargs):
                if failure:raise RuntimeError('private provider failure')
                supplied=json.loads(kwargs['messages'][1]['content'])['context'];assert supplied==context
                review={key:context[key] for key in ('run_id','context_checksum','specification_checksum')}
                review.update(version=1,status='PASS',summary='Synthetic integration response',evidence_ids=[*REQUIRED_CHECKS,'semantic_design'],issues=[])
                return NS(choices=[NS(message=NS(content=json.dumps(review)))],usage=NS(prompt_tokens=1,completion_tokens=1,total_tokens=2))
            provider=Mock(side_effect=response)
            args=(q,repo,task,run,comparison,context['context_checksum'])
            first=dispatch_qa(*args,authorize_model_call=True,completion=provider)
            assert first['status']==('QA_OUTCOME_UNKNOWN' if failure else 'VALIDATED_NOT_APPROVED')
            if failure:
                with pytest.raises(ValueError,match='QA_PASS_REVIEW_REQUIRED'):
                    load_approval_offer(q,task,run,connection=connection)
            else:
                offer=load_approval_offer(q,task,run,connection=connection)
                assert offer['invocation_id']==first['invocation_id']
                assert offer['context_checksum']==context['context_checksum']
                assert load_approval_offer(q,task,run,connection=connection)==offer
                from pathlib import Path
                if not connection.execute("SELECT to_regclass('platform.qa_review_approval') AS name").fetchone()['name']:
                    connection.execute(Path('/app/database/migrations/042_qa_approval.sql').read_text())
                with pytest.raises(ValueError,match='QA_HUMAN_CONFIRMATION_REQUIRED'):
                    approve_review(q,task,run,offer['checksum'])
                with pytest.raises(ValueError,match='QA_APPROVAL_VERSION_CONFLICT'):
                    approve_review(q,task,run,'0'*64,confirmed=True)
                approval=approve_review(q,task,run,offer['checksum'],confirmed=True)
                assert approval['qa_approved'] and not approval['release_ready']
                loaded=read_approval(q,task,run)
                assert loaded['status']=='APPROVED_CURRENT' and loaded['qa_approved']
                assert loaded['approval']['approval_id']==approval['approval_id']
                delivery=load_delivery_context(q,task,run,connection=connection)
                assert delivery['qa_approval_id']==approval['approval_id']
                assert delivery['specification_checksum']==offer['specification_checksum']
                assert delivery['release_ready'] is False
                from tempfile import TemporaryDirectory
                from app.sdm_store import save_delivery_candidate,download_candidate
                from app.sdm_qa_binding import bind_sdm_qa
                if not connection.execute("SELECT to_regclass('platform.sdm_qa_binding') name").fetchone()['name']:
                    connection.execute(Path('/app/database/migrations/043_sdm_qa_binding.sql').read_text())
                with TemporaryDirectory(prefix='sdm-delivery-test-') as sdm_root:
                    document=save_delivery_candidate(q,task,run,delivery['specification_id'],delivery['specification_checksum'],offer['checksum'],root=sdm_root)
                    same=save_delivery_candidate(q,task,run,delivery['specification_id'],delivery['specification_checksum'],offer['checksum'],root=sdm_root)
                    assert same['sdm_id']==document['sdm_id']
                    metadata,content=download_candidate(q,task,run,document['sdm_id'],root=sdm_root)
                    assert len(content)==metadata['file_size'] and content.startswith(b'PK')
                    assert metadata['status']=='CANDIDATE_NOT_RELEASED' and not metadata['release_ready']
                    linked=bind_sdm_qa(q,task,run,document['sdm_id'],offer['checksum'],root=sdm_root)
                    assert bind_sdm_qa(q,task,run,document['sdm_id'],offer['checksum'],root=sdm_root)==linked
                    assert not linked['release_ready']
                    from app.sdm_delivery import prepare_sdm_delivery
                    prepared=prepare_sdm_delivery(q,task,run,offer['checksum'],root=sdm_root)
                    assert prepared['document']['sdm_id']==document['sdm_id']
                    assert prepared['qa_binding']==linked and not prepared['release_ready']
                    from app.release_candidate import assemble_release_candidate
                    bundle=assemble_release_candidate(q,task,run,document['sdm_id'],offer['checksum'],repo=repo,root=sdm_root)
                    assert bundle['status']=='CANDIDATE_NOT_RELEASED' and not bundle['release_ready']
                    assert bundle['content_screen']['status']=='CONTENT_SCREEN_PASSED'
                    from zipfile import ZipFile
                    from io import BytesIO
                    with ZipFile(BytesIO(bundle['content'])) as archive:
                        assert set(archive.namelist())=={'hop/pipeline.hpl','hop/workflow.hwf','vertica-ddl.sql','SDM.xlsx','parameters.example','release-manifest.json'}
                        assert archive.read('SDM.xlsx')==content
                    assert connection.execute('SELECT write_started FROM platform.task_run WHERE run_id=%s',(run,)).fetchone()['write_started'] is True
                    if os.getenv('WORKBENCH_SDM_VERIFY_OUTPUT'):
                        Path(os.environ['WORKBENCH_SDM_VERIFY_OUTPUT']).write_bytes(content)
                from sdm_qa_database_checks import check_sdm_qa_database
                check_sdm_qa_database(q,connection,task,run,delivery,approval,offer['checksum'])
                assert approve_review(q,task,run,offer['checksum'],confirmed=True)==approval
                assert connection.execute("SELECT count(*) n FROM platform.task_run_event WHERE run_id=%s AND event_type='QA_HUMAN_APPROVED'",(run,)).fetchone()['n']==1
                import psycopg
                for sql in ('UPDATE platform.qa_review_approval SET binding_checksum=binding_checksum WHERE approval_id=%s',
                            'DELETE FROM platform.qa_review_approval WHERE approval_id=%s'):
                    with pytest.raises(psycopg.Error):
                        with connection.transaction():connection.execute(sql,(approval['approval_id'],))
                record=connection.execute('SELECT * FROM platform.agent_invocation WHERE invocation_id=%s',(first['invocation_id'],)).fetchone()
                captured=load_qa_context(q,task,run,comparison)
                with pytest.raises(ValueError,match='QA_RUN_NOT_APPROVABLE'):
                    approval_binding({**captured['run'],'matches_current':False},record,context)
                with pytest.raises(ValueError,match='QA_APPROVAL_CONTEXT_CHANGED'):
                    approval_binding(captured['run'],record,{**context,'context_checksum':'0'*64})
            second=dispatch_qa(*args,authorize_model_call=True,completion=provider)
            assert second['invocation_id']==first['invocation_id'] and second['status']==first['status']
            assert provider.call_count==1
            assert connection.execute('SELECT count(*) AS n FROM platform.qa_dispatch_claim WHERE invocation_id=%s',(first['invocation_id'],)).fetchone()['n']==1
        finally:connection.rollback()


def test_reserved_intent_cannot_be_claimed_twice():
    task=os.environ['WORKBENCH_QA_CONTEXT_TASK'];run=os.environ['WORKBENCH_QA_CONTEXT_RUN'];comparison=os.environ['WORKBENCH_QA_CONTEXT_COMPARISON']
    base=RunQueue(os.environ['DATABASE_URL'])
    with base.conn() as connection:
        class Queue(RunQueue):
            def conn(self):return nullcontext(connection)
        q=Queue(base.url)
        try:
            context=load_qa_context(q,task,run,comparison)['context']
            saved=QAJournal(q).reserve(task,run,comparison,context['context_checksum'],True)
            claim_dispatch(q,task,saved['invocation_id'])
            with pytest.raises(ValueError,match='QA_DISPATCH_ALREADY_CONSUMED'):
                claim_dispatch(q,task,saved['invocation_id'])
        finally:connection.rollback()
