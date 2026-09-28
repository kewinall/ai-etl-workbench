"""Synthetic evidence contract tests, not a real model or Vertica acceptance."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock
from xml.etree import ElementTree as ET
import pytest
from app import qa_execution_details as module
from app.hpl_compiler import compile_hpl
from app.source_binding import execution_sources
from app.qa_contract import build_qa_context, validate_qa_review, REQUIRED_CHECKS
from app.qa_gateway import qa_material, complete_qa_review, QAInvocationError, PROMPT, PROMPT_VERSION
from app.qa_source_formats import inspect_formats
from app.qa_target_contract import expected_target
from app.sa_contract import digest
from test_excel_specification import excel_design


def fixture(monkeypatch):
    content = []
    spec, run, naming = excel_design(capture=content)
    config = run['input_snapshot']['source_config']
    source = config['sources'][0]
    read = Mock(return_value=content[0])
    monkeypatch.setattr(module, 'read_verified_upload', read)
    compiled = compile_hpl(spec, run, naming)
    auth = dict(hpl_checksum=compiled['hpl_checksum'], **execution_sources(config, 4))
    details = module.execution_details(run, compiled, auth)
    read.assert_called_once_with(source['upload_id'], 'EXCEL', source['checksum'], source['size'])
    details['source_formats'] = inspect_formats(compiled)
    # Synthetic expected target description only. Actual loader must inspect the DB claim.
    details['target_contract'] = expected_target(spec, details)
    checks = [dict(id=key, status='PASS', checksum='a' * 64, summary='Synthetic contract check only')
              for key in REQUIRED_CHECKS]
    next(check for check in checks if check['id'] == 'static_validation')['checksum'] = compiled['hpl_checksum']
    semantics = dict(requirement=run['input_snapshot']['requirement_text'],
        conditions=run['input_snapshot']['target_config']['requirements_v1'], specification=spec,
        execution_details=details, nodes=[dict(id=node.findtext('name'), component=node.findtext('type'))
        for node in ET.fromstring(compiled['hpl']).findall('transform')])
    return run, compiled, auth, checks, semantics


def test_excel_v14_context_is_complete_canonical_and_advisory(monkeypatch):
    run, compiled, auth, checks, semantics = fixture(monkeypatch)
    context = build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)
    assert context['version'] == 14
    assert build_qa_context(context['run_id'], context['specification_checksum'], context['evidence'], context['semantics']) == context
    details = context['semantics']['execution_details']
    assert details['source_format'] == 'XLSX'
    assert details['excel_structure_validation']['complete'] is True
    assert details['excel_structure_validation']['column_types_checked'] is True
    assert details['excel_structure_validation']['type_conversion_verified'] is False
    assert len(details['source_formats']['sources']) == 1
    assert 'upload_id' not in str(context) and 'sample_rows' not in str(context)
    review = {key: context[key] for key in ('run_id', 'context_checksum', 'specification_checksum')}
    review.update(version=1, status='PASS', summary='Synthetic contract review',
        evidence_ids=[*REQUIRED_CHECKS, 'semantic_design', 'node.source'], issues=[])
    accepted = validate_qa_review(review, context)
    assert accepted['advisory_only'] and not accepted['qa_approved'] and not accepted['release_ready']
    assert qa_material(context)['prompt_version'] == 11
    assert 'native XLSX' in qa_material(context)['prompt']
    assert qa_material(None) == {'prompt': PROMPT, 'prompt_version': PROMPT_VERSION, 'prompt_checksum': digest(PROMPT)}


@pytest.mark.parametrize('changed', ['contract', 'fingerprint', 'complete', 'types', 'conversion_claim',
    'format', 'runtime', 'selection', 'target', 'missing_formats', 'missing_runtime', 'missing_target'])
def test_excel_qa_context_rejects_mutated_or_incomplete_evidence(monkeypatch, changed):
    run, compiled, auth, checks, semantics = fixture(monkeypatch)
    details = semantics['execution_details']
    if changed == 'contract': details['excel_input_contract']['blank_rows'] = 'PRESERVE'
    elif changed == 'fingerprint': details['excel_source']['profile_checksum'] = 'f' * 64
    elif changed == 'complete': details['excel_structure_validation']['complete'] = False
    elif changed == 'types': details['excel_structure_validation']['column_types_checked'] = False
    elif changed == 'conversion_claim': details['excel_structure_validation']['type_conversion_verified'] = True
    elif changed == 'format': details['source_format'] = 'CSV'
    elif changed == 'runtime': details['runtime_options']['sources'][0]['options']['error_ignored'] = 'Y'
    elif changed == 'selection': details['compiler_plan']['stages'][0]['contract']['worksheet'] = 'other'
    elif changed == 'target': details['target_contract']['checksum'] = 'f' * 64
    else: details.pop({'missing_formats': 'source_formats', 'missing_runtime': 'runtime_options', 'missing_target': 'target_contract'}[changed])
    with pytest.raises(ValueError):
        build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)


@pytest.mark.parametrize('key', ['source_format', 'source_checksum', 'hpl_checksum'])
def test_excel_qa_rejects_unbound_execution_before_reading(monkeypatch, key):
    run, compiled, auth, checks, semantics = fixture(monkeypatch)
    auth.pop(key)
    read = Mock(side_effect=AssertionError('Do not read unbound data'))
    monkeypatch.setattr(module, 'read_verified_upload', read)
    with pytest.raises(ValueError, match='QA_EXECUTED_SOURCE_BINDING_CHANGED'):
        module.execution_details(run, compiled, auth)
    read.assert_not_called()


def test_excel_qa_requires_same_bytes_and_full_scan(monkeypatch):
    run, compiled, auth, checks, semantics = fixture(monkeypatch)
    changed = []
    excel_design(capture=changed, rows=[['A', '999']])
    monkeypatch.setattr(module, 'read_verified_upload', Mock(return_value=changed[0]))
    with pytest.raises(ValueError):
        module.execution_details(run, compiled, auth)


@pytest.mark.parametrize('failed', [False, True])
def test_excel_prompt_trace_and_deterministic_failure_cannot_be_overridden(monkeypatch, failed):
    run, compiled, auth, checks, semantics = fixture(monkeypatch)
    if failed:
        next(check for check in checks if check['id'] == 'result_comparison')['status'] = 'FAIL'
    context = build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)
    run.update(state='NEEDS_REVIEW', write_started=True, matches_current=True, lease_token=None,
               outcome_code='HOP_EXECUTED_QA_REQUIRED')
    profile = dict(enabled=True, provider_type='LITELLM_BEDROCK', region='us-east-1',
                   model_routes={'qa_review': 'bedrock/synthetic-qa'})
    run['settings_snapshot']['model_routes'] = profile['model_routes'].copy()
    review = {key: context[key] for key in ('run_id', 'context_checksum', 'specification_checksum')}
    review.update(version=1, status='PASS', summary='Synthetic response', evidence_ids=[*REQUIRED_CHECKS, 'semantic_design'], issues=[])
    calls = []
    def complete(**kwargs):
        assert json.loads(kwargs['messages'][1]['content'])['context'] == context
        assert kwargs['messages'][0]['content'] == qa_material(context)['prompt']
        calls.append(kwargs['model'])
        return NS(choices=[NS(message=NS(content=json.dumps(review)))], usage=NS(prompt_tokens=3, completion_tokens=4, total_tokens=7))
    if failed:
        with pytest.raises(QAInvocationError, match='QA_OUTPUT_CONTRACT_INVALID'):
            complete_qa_review(run, profile, context, completion=complete)
    else:
        result, trace = complete_qa_review(run, profile, context, completion=complete)
        assert trace['prompt_version'] == 11 and trace['prompt_checksum'] == qa_material(context)['prompt_checksum']
        assert not result['qa_approved'] and not result['release_ready']
    assert calls == ['bedrock/synthetic-qa']
