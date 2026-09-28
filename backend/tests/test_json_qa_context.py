"""Managed synthetic JSON, generated checks: not real model/Vertica acceptance."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
from xml.etree import ElementTree as ET
import pytest
from app import task_uploads
from app.json_source_profile import confirmed_json_profile
from app.json_contract_binding import validated_json_contract
from app.hpl_compiler import compile_hpl
from app.qa_execution_details import execution_details
from app.source_binding import execution_sources
from app.qa_contract import build_qa_context, validate_qa_review, REQUIRED_CHECKS
from app.qa_gateway import qa_material, complete_qa_review, QAInvocationError
from app.qa_source_formats import inspect_formats
from app.qa_target_contract import expected_target
from app.json_runtime_evidence import require_json_runtime_receipt, MARKER
from test_json_specification import json_design, CONTENT


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    data = b'\xef\xbb\xbf' + CONTENT
    spec, run, naming = json_design(data)
    upload = task_uploads.save_and_profile('synthetic.json', data)
    profile = confirmed_json_profile(upload['upload_id'], upload['checksum'], upload['size'])
    config = run['input_snapshot']['source_config']
    config['sources'] = [{**upload, **profile, 'type': 'JSON', 'has_actual_data': True}]
    spec['json_source'] = validated_json_contract(config)['reference']
    compiled = compile_hpl(spec, run, naming)
    auth = dict(hpl_checksum=compiled['hpl_checksum'], **execution_sources(config, 5))
    details = execution_details(run, compiled, auth)
    details['source_formats'] = inspect_formats(compiled)
    details['target_contract'] = expected_target(spec, details)
    details['json_runtime_receipt'] = {**require_json_runtime_receipt(MARKER), 'log_checksum': 'a' * 64}
    checks = [dict(id=key, status='PASS', checksum='a' * 64, summary='Synthetic check only') for key in REQUIRED_CHECKS]
    next(c for c in checks if c['id'] == 'static_validation')['checksum'] = compiled['hpl_checksum']
    semantics = dict(requirement=run['input_snapshot']['requirement_text'],
        conditions=run['input_snapshot']['target_config']['requirements_v1'], specification=spec,
        execution_details=details, nodes=[dict(id=n.findtext('name'), component=n.findtext('type'))
        for n in ET.fromstring(compiled['hpl']).findall('transform')])
    return run, compiled, auth, checks, semantics


def review(context):
    return {**{k: context[k] for k in ('run_id', 'context_checksum', 'specification_checksum')},
            'version': 1, 'status': 'PASS', 'summary': 'Synthetic response only',
            'evidence_ids': [*REQUIRED_CHECKS, 'semantic_design', 'node.source'], 'issues': []}


def test_json_context_v15_is_canonical_and_advisory(fixture):
    run, compiled, auth, checks, semantics = fixture
    context = build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)
    assert context['version'] == 15
    assert build_qa_context(context['run_id'], context['specification_checksum'], context['evidence'], context['semantics']) == context
    details = context['semantics']['execution_details']
    assert details['json_reader']['normalization'] == 'UTF8_BOM_REMOVED'
    assert details['json_structure_validation']['records_expected'] == 6
    assert not details['json_structure_validation']['type_conversion_verified']
    assert details['runtime_options']['version'] == 3
    assert len(details['source_formats']['sources']) == 1
    assert all(key not in str(context) for key in ('upload_id', 'sample_rows', 'file_path', 'source.csv'))
    accepted = validate_qa_review(review(context), context)
    assert accepted['advisory_only'] and not accepted['qa_approved'] and not accepted['release_ready']
    assert qa_material(context)['prompt_version'] == 12
    assert 'native JSON' in qa_material(context)['prompt']


@pytest.mark.parametrize('changed', [False, True])
def test_json_confirmed_transformation_intent_maps_through_native_fields(fixture, changed):
    from test_transformation_contract import intent
    run, compiled, auth, checks, semantics = fixture
    semantics['transformation_intent'] = intent()
    if changed: semantics['transformation_intent']['filters'][0]['operator'] = 'GE'
    if changed:
        with pytest.raises(ValueError, match='QA_TRANSFORMATION_INTENT_MISMATCH'):
            build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)
    else:
        assert build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)['version'] == 15


@pytest.mark.parametrize('change', ['contract', 'profile', 'reader', 'validation', 'types', 'conversion', 'fields',
    'count', 'bool_count', 'format', 'options', 'jsonpath', 'projection', 'target', 'receipt', 'receipt_log',
    'receipt_version', 'receipt_approved', 'missing_receipt', 'missing_formats', 'missing_runtime', 'missing_target'])
def test_changed_or_missing_json_qa_evidence_cannot_validate(fixture, change):
    run, compiled, auth, checks, semantics = fixture
    d = semantics['execution_details']
    if change == 'contract': d['json_input_contract']['root_shape'] = 'OBJECT'
    elif change == 'profile': d['json_source']['profile_checksum'] = 'f' * 64
    elif change == 'reader': d['json_reader']['reader_checksum'] = 'f' * 64
    elif change == 'validation': d['json_structure_validation']['complete'] = False
    elif change == 'types': d['json_structure_validation']['column_types_checked'] = False
    elif change == 'conversion': d['json_structure_validation']['type_conversion_verified'] = True
    elif change == 'fields': d['json_structure_validation']['field_names_checksum'] = 'f' * 64
    elif change in ('count', 'bool_count'): d['json_structure_validation']['records_expected'] = 0 if change == 'count' else True
    elif change == 'format': d['source_format'] = 'CSV'
    elif change == 'options': d['runtime_options']['sources'][0]['options']['readurl'] = 'Y'
    elif change == 'jsonpath': d['runtime_options']['sources'][0]['fields'][0]['path'] = '$[*]'
    elif change == 'projection': d['compiler_plan']['stages'][2]['columns'].append('json_source_file')
    elif change == 'target': d['target_contract']['checksum'] = 'f' * 64
    elif change == 'receipt': d['json_runtime_receipt']['HOP_JSON_INPUT_INCLUDE_NULLS'] = 'N'
    elif change == 'receipt_log': d['json_runtime_receipt']['log_checksum'] = 'f' * 64
    elif change == 'receipt_version': d['json_runtime_receipt']['version'] = True
    elif change == 'receipt_approved': d['json_runtime_receipt']['qa_passed'] = 0
    else: d.pop({'missing_receipt': 'json_runtime_receipt', 'missing_formats': 'source_formats',
                 'missing_runtime': 'runtime_options', 'missing_target': 'target_contract'}[change])
    with pytest.raises(ValueError): build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)


@pytest.mark.parametrize('failure', [False, True])
def test_json_prompt_trace_and_deterministic_failures(fixture, failure):
    run, compiled, auth, checks, semantics = fixture
    if failure: next(c for c in checks if c['id'] == 'result_comparison')['status'] = 'FAIL'
    context = build_qa_context(run['run_id'], compiled['specification_checksum'], checks, semantics)
    run.update(state='NEEDS_REVIEW', write_started=True, matches_current=True, lease_token=None, outcome_code='HOP_EXECUTED_QA_REQUIRED')
    profile = dict(enabled=True, provider_type='LITELLM_BEDROCK', region='us-east-1', model_routes={'qa_review': 'bedrock/synthetic-qa'})
    run['settings_snapshot']['model_routes'] = profile['model_routes'].copy()
    calls = []
    def complete(**kwargs):
        assert json.loads(kwargs['messages'][1]['content'])['context'] == context
        assert kwargs['messages'][0]['content'] == qa_material(context)['prompt']
        calls.append(kwargs['model'])
        return NS(choices=[NS(message=NS(content=json.dumps(review(context))))], usage=NS(prompt_tokens=3, completion_tokens=4, total_tokens=7))
    if failure:
        with pytest.raises(QAInvocationError, match='QA_OUTPUT_CONTRACT_INVALID'):
            complete_qa_review(run, profile, context, completion=complete)
    else:
        accepted, trace = complete_qa_review(run, profile, context, completion=complete)
        assert trace['prompt_version'] == 12
        assert trace['prompt_checksum'] == qa_material(context)['prompt_checksum']
        assert not accepted['qa_approved'] and not accepted['release_ready']
    assert len(calls) == 1
