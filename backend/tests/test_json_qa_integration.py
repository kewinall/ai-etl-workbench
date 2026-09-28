"""Actual isolated PG loader/journal, deliberately synthetic engine/cursor/AI."""
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import Mock
from xml.etree import ElementTree as ET
import json
import pytest
from app.run_queue import RunQueue
from app.approved_candidate import load_approved_candidate
from app.delivery_compiler import compile_delivery_components
from app.specification_store import context as specification_context
from app.target_ownership import claim_target
from app.hop_worker import execute_once
from app.comparison_store import record_execution_comparison
from app.qa_context import load_qa_context
from app.qa_gateway import qa_material, complete_qa_review
from app.qa_contract import validate_qa_review
from app.qa_journal import QAJournal
from app.qa_dispatch import claim_dispatch
from app.json_runtime_evidence import MARKER
from test_json_preparation_integration import candidate
from test_run_queue_integration import context, pytestmark


@pytest.mark.parametrize('receipt', [True, False])
def test_json_persisted_qa_loader_and_journal_keep_evidence_scope(context, tmp_path, monkeypatch, receipt):
    base, task, run, sid, consent, aid = candidate(context, tmp_path, monkeypatch)
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', 'true')
    with base.conn() as conn:
        class Queue(RunQueue):
            def conn(self): return nullcontext(conn)
        queue = Queue(base.url)
        try:
            bound = load_approved_candidate(queue, conn, task, run['run_id'], sid)
            saved, naming = specification_context(queue, conn, task, run['run_id'])
            compiled = compile_delivery_components(bound['compiled']['specification'], saved, naming)
            spec = compiled['specification']
            # Register a synthetic claim only; no Vertica DDL or result provenance is invented.
            conn.execute('''INSERT INTO platform.platform_sample_table
                (project_id,schema_name,table_name,task_id,ddl_checksum,row_count) VALUES(%s,%s,%s,%s,%s,0)''',
                (run['project_id'], spec['target_schema'], spec['target_table'], task, compiled['ddl_checksum']))
            claim_target(queue, task, run['run_id'], sid)
            nodes = [n.findtext('name') for n in ET.fromstring(compiled['hpl']).findall('transform')]
            log = (b'SYNTHETIC CONTROL TEST - NOT A REAL HOP RUN\n' + (MARKER + b'\n' if receipt else b'')
                + ''.join(f'WORKBENCH_NODE_V1 {n} 0 0 0 0 0 0\n' for n in nodes).encode()
                + f'WORKBENCH_METRICS_END_V1 {len(nodes)}\n'.encode())
            def engine(prepared, lost, sink):
                stored = sink(log)
                return dict(status='COMPLETED', exit_code=0, errors=0, log_checksum=stored['checksum'])
            assert execute_once(queue, task, run['run_id'], sid, aid, engine)['status'] == 'HOP_EXECUTED_QA_REQUIRED'
            cursor = Mock(description=[('category',), ('total_amount',), ('row_count',)])
            cursor.fetchmany.side_effect = [[('A', Decimal('251.75'), 2), ('C', Decimal('201.00'), 1)], []]
            comparison = record_execution_comparison(queue, task, run['run_id'], cursor)
            if not receipt:
                with pytest.raises(ValueError, match='JSON_RUNTIME_RECEIPT_REQUIRED'):
                    load_qa_context(queue, task, run['run_id'], comparison['comparison_id'])
                assert conn.execute("SELECT count(*) n FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_qa'", (run['run_id'],)).fetchone()['n'] == 0
                return
            captured = load_qa_context(queue, task, run['run_id'], comparison['comparison_id'])
            value = captured['context']
            assert value['version'] == 15
            assert load_qa_context(queue, task, run['run_id'], comparison['comparison_id'])['context'] == value
            assert next(c for c in value['evidence'] if c['id'] == 'result_source')['status'] == 'MISSING'
            assert next(c for c in value['evidence'] if c['id'] == 'static_validation')['status'] == 'PASS'
            details = value['semantics']['execution_details']
            assert details['json_runtime_receipt']['log_checksum'] == next(c for c in value['evidence'] if c['id'] == 'hop_execution')['checksum']
            journal = QAJournal(queue)
            intent = journal.reserve(task, run['run_id'], comparison['comparison_id'], value['context_checksum'], True)
            identity = intent['invocation_id']
            record = conn.execute('SELECT * FROM platform.agent_invocation WHERE invocation_id=%s', (identity,)).fetchone()
            assert record['prompt_version'] == 12 and record['input_json']['prompt_checksum'] == qa_material(value)['prompt_checksum']
            claim_dispatch(queue, task, identity)
            with pytest.raises(ValueError, match='QA_DISPATCH_ALREADY_CONSUMED'): claim_dispatch(queue, task, identity)
            output = {**{k: value[k] for k in ('run_id', 'context_checksum', 'specification_checksum')}, 'version': 1,
                'status': 'NEEDS_REVIEW', 'summary': 'Synthetic result lacks real DB query provenance',
                'evidence_ids': ['result_source', 'semantic_design'],
                'issues': [dict(message='No real target provenance in this synthetic test', evidence_ids=['result_source'])]}
            with pytest.raises(ValueError, match='QA_PASS_REQUIRES_COMPLETE_EVIDENCE'):
                validate_qa_review({**output, 'status': 'PASS', 'issues': []}, value)
            profile = dict(enabled=True, provider_type='LITELLM_BEDROCK', region='us-east-1',
                           model_routes=captured['run']['settings_snapshot']['model_routes'])
            completion = Mock(return_value=NS(choices=[NS(message=NS(content=json.dumps(output)))],
                usage=NS(prompt_tokens=3, completion_tokens=4, total_tokens=7)))
            review, trace = complete_qa_review(captured['run'], profile, value, completion=completion)
            assert completion.call_count == 1
            assert journal.finish(task, identity, review, trace)['status'] == 'VALIDATED_NOT_APPROVED'
            public = journal.read(task, run['run_id'])
            assert public['invocation']['context'] == value
            assert public['invocation']['review']['status'] == 'NEEDS_REVIEW'
            assert not public['qa_approved'] and not public['approval_available'] and not public['release_ready']
        finally:
            conn.rollback()
