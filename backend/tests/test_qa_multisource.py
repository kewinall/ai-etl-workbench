from copy import deepcopy
from hashlib import sha256
from xml.etree import ElementTree as ET
import pytest
from app import qa_execution_details as module
from app.hpl_compiler import compile_hpl
from app.qa_contract import build_qa_context, validate_qa_review, REQUIRED_CHECKS
from app.source_binding import execution_sources
from test_join_semantics import join_design


def fixture(monkeypatch):
    spec, run, naming = join_design()
    data = ['客戶編號,名稱\nA,left-private\nB,unmatched\n'.encode(),
            '客戶編號|名稱\nA|right-private\n'.encode()]
    config = run['input_snapshot']['source_config']
    for i,source in enumerate(config['sources']):
        source.update(upload_id=str(i), checksum=sha256(data[i]).hexdigest(), size=len(data[i]))
    monkeypatch.setattr(module, 'read_verified_upload', lambda identity,*args: data[int(identity)])
    compiled = compile_hpl(spec, run, naming)
    auth = dict(hpl_checksum=compiled['hpl_checksum'], **execution_sources(config, 2))
    return spec, run, compiled, auth


def context_fixture(monkeypatch):
    spec,run,compiled,auth = fixture(monkeypatch)
    checks = [dict(id=name, status='PASS', checksum='a'*64, summary='Synthetic check') for name in REQUIRED_CHECKS]
    next(c for c in checks if c['id'] == 'static_validation')['checksum'] = compiled['hpl_checksum']
    semantics = dict(requirement=run['input_snapshot']['requirement_text'],
        conditions=run['input_snapshot']['target_config']['requirements_v1'],
        join_conditions=run['input_snapshot']['target_config']['join_contract_v1'], specification=spec,
        execution_details=module.execution_details(run,compiled,auth),
        nodes=[dict(id=n.findtext('name'),component=n.findtext('type')) for n in ET.fromstring(compiled['hpl']).findall('transform')])
    return run,compiled,checks,semantics


def test_both_sources_rechecked_without_rows_or_replay(monkeypatch):
    _,run,compiled,auth = fixture(monkeypatch)
    details = module.execution_details(run,compiled,auth)
    assert details['source_checksums'] == auth['source_checksums']
    assert [details['csv_structure_validations'][ref]['records_checked'] for ref in ('source.0','source.1')] == [2,1]
    assert 'left-private' not in str(details) and 'right-private' not in str(details)


@pytest.mark.parametrize('ref', ['source.0','source.1'])
def test_changed_source_binding_rejected_before_read(monkeypatch, ref):
    _,run,compiled,auth = fixture(monkeypatch)
    auth['source_checksums'][ref] = '0'*64
    def forbidden(*args): raise AssertionError('must not read unbound source')
    monkeypatch.setattr(module, 'read_verified_upload', forbidden)
    with pytest.raises(ValueError,match='BINDING_CHANGED'): module.execution_details(run,compiled,auth)


def test_v4_context_requires_semantic_evidence_but_never_grants_release(monkeypatch):
    run,compiled,checks,semantics = context_fixture(monkeypatch)
    ctx = build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    assert ctx['version'] == 4
    review = {key:ctx[key] for key in ('run_id','context_checksum','specification_checksum')}
    review.update(version=1,status='PASS',summary='Synthetic review',
        evidence_ids=[*REQUIRED_CHECKS,'semantic_design','node.join_customers'],issues=[])
    result = validate_qa_review(review,ctx)
    assert result['advisory_only'] and not result['release_ready']
    assert build_qa_context(ctx['run_id'],ctx['specification_checksum'],ctx['evidence'],ctx['semantics']) == ctx


@pytest.mark.parametrize('change', ['join', 'missing_source', 'swapped_source', 'contract', 'incomplete', 'aggregate'])
def test_v4_context_rejects_semantic_or_source_evidence_change(monkeypatch, change):
    run,compiled,checks,semantics = context_fixture(monkeypatch)
    semantics = deepcopy(semantics); details = semantics['execution_details']
    if change == 'join': semantics['join_conditions']['joins'][0]['join_type'] = 'INNER'
    if change == 'missing_source': details['csv_structure_validations'].pop('source.1')
    if change == 'swapped_source': details['csv_structure_validations']['source.1'] = details['csv_structure_validations']['source.0']
    if change == 'contract': details['csv_input_contracts']['source.1']['delimiter'] = ';'
    if change == 'incomplete': details['csv_structure_validations']['source.1']['complete'] = False
    if change == 'aggregate': details['source_checksum'] = '0'*64
    with pytest.raises(ValueError): build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)


def test_gateway_receives_complete_v4_context_and_cannot_override_failure(monkeypatch):
    import json
    from types import SimpleNamespace as NS
    from app.qa_gateway import complete_qa_review, QAInvocationError
    run,compiled,checks,semantics = context_fixture(monkeypatch)
    next(c for c in checks if c['id'] == 'result_comparison')['status'] = 'FAIL'
    ctx = build_qa_context(run['run_id'],compiled['specification_checksum'],checks,semantics)
    run.update(state='NEEDS_REVIEW',write_started=True,matches_current=True,lease_token=None,
               outcome_code='HOP_EXECUTED_QA_REQUIRED')
    profile = dict(enabled=True,provider_type='LITELLM_BEDROCK',region='us-east-1',
                   model_routes={'qa_review':'bedrock/synthetic-qa'})
    run['settings_snapshot']['model_routes'] = profile['model_routes'].copy()
    review = {key:ctx[key] for key in ('run_id','context_checksum','specification_checksum')}
    review.update(version=1,status='PASS',summary='Synthetic unsupported PASS',
                  evidence_ids=[*REQUIRED_CHECKS,'semantic_design'],issues=[])
    calls = []
    def response(**kwargs):
        payload = json.loads(kwargs['messages'][1]['content'])
        assert payload['context'] == ctx
        calls.append(kwargs['model'])
        return NS(choices=[NS(message=NS(content=json.dumps(review)))],
                  usage=NS(prompt_tokens=3,completion_tokens=4,total_tokens=7))
    with pytest.raises(QAInvocationError,match='QA_OUTPUT_CONTRACT_INVALID'):
        complete_qa_review(run,profile,ctx,completion=response)
    assert calls == ['bedrock/synthetic-qa']
