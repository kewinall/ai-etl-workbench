"""Selected real evidence, synthetic QA output, transaction rollback, no model."""
import os
from contextlib import nullcontext
import pytest
import psycopg
from app.run_queue import RunQueue
from app.qa_context import load_qa_context
from app.qa_journal import QAJournal
from app.qa_contract import QAReviewV1,REQUIRED_CHECKS
from app.qa_gateway import PROMPT,PROMPT_VERSION
from app.sa_contract import digest

pytestmark=pytest.mark.skipif(not os.getenv('WORKBENCH_QA_CONTEXT_RUN'),reason='Explicit persisted execution required')


@pytest.mark.parametrize('uncertain',[False,True])
def test_qa_journal_roundtrip_without_persisting_synthetic_advice(uncertain):
    assert os.getenv('DATABASE_HOST')=='postgres' and os.getenv('DATABASE_NAME')=='workbench'
    task=os.environ['WORKBENCH_QA_CONTEXT_TASK'];run=os.environ['WORKBENCH_QA_CONTEXT_RUN'];comparison=os.environ['WORKBENCH_QA_CONTEXT_COMPARISON']
    base=RunQueue(os.environ['DATABASE_URL'])
    with base.conn() as connection:
        class FixedQueue(RunQueue):
            def conn(self):return nullcontext(connection)
        queue=FixedQueue(base.url);journal=QAJournal(queue)
        try:
            assert not connection.execute("SELECT 1 FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa'",(run,)).fetchone()
            captured=load_qa_context(queue,task,run,comparison);context=captured['context']
            assert journal.read(task,run)['invocation'] is None
            with pytest.raises(ValueError,match='QA_EXPLICIT_CONSENT_REQUIRED'):
                journal.reserve(task,run,comparison,context['context_checksum'],False)
            saved=journal.reserve(task,run,comparison,context['context_checksum'],True)
            assert saved==journal.reserve(task,run,comparison,context['context_checksum'],True)
            if uncertain:
                journal.hold_uncertain(task,saved['invocation_id'])
                assert journal.reserve(task,run,comparison,context['context_checksum'],True)['status']=='QA_OUTCOME_UNKNOWN'
            else:
                output={key:context[key] for key in ('run_id','context_checksum','specification_checksum')}
                output.update(version=1,status='PASS',summary='Synthetic contract test only',evidence_ids=[*REQUIRED_CHECKS,'semantic_design'],issues=[])
                settings=captured['run']['settings_snapshot']
                trace=dict(run_id=run,context_checksum=context['context_checksum'],provider=settings['ai']['provider_type'],
                    model=settings['model_routes']['qa_review'],prompt_version=PROMPT_VERSION,prompt_checksum=digest(PROMPT),
                    schema_checksum=digest(QAReviewV1.model_json_schema()),status='VALIDATED_NOT_APPROVED',
                    output_checksum=digest(output),duration_ms=1,usage={'input_tokens':None,'output_tokens':None,'total_tokens':None},
                    raw_secret='must-not-persist')
                result=journal.finish(task,saved['invocation_id'],output,trace)
                assert result['status']=='VALIDATED_NOT_APPROVED' and not result['qa_approved']
                row=connection.execute('SELECT output_json FROM platform.agent_invocation WHERE invocation_id=%s',(saved['invocation_id'],)).fetchone()
                assert 'must-not-persist' not in str(row['output_json'])
                with pytest.raises(ValueError,match='QA_RESULT_NOT_WRITABLE'):
                    journal.finish(task,saved['invocation_id'],output,trace)
            assert connection.execute("SELECT count(*) AS n FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa'",(run,)).fetchone()['n']==1
            public=journal.read(task,run)
            assert public['invocation']['status']==('QA_OUTCOME_UNKNOWN' if uncertain else 'VALIDATED_NOT_APPROVED')
            assert public['invocation']['context']==context
            assert 'input_json' not in public['invocation'] and not public['qa_approved']
            for sql in ('DELETE FROM platform.agent_invocation WHERE invocation_id=%s',
                        "UPDATE platform.agent_invocation SET status='QA_RESERVED' WHERE invocation_id=%s"):
                with pytest.raises(psycopg.errors.RaiseException,match='immutable'):
                    with connection.transaction():connection.execute(sql,(saved['invocation_id'],))
        finally:
            connection.rollback()
