from copy import deepcopy
from types import SimpleNamespace as NS
from uuid import uuid4
import json
import pytest
from app.sa_contract import build_sa_context, validate_sa_review, digest
from app.sa_gateway import sa_material, complete_sa_review, SAInvocationError
from app.sa_work_queue import authorization_offer
from app.developer_contract import build_context, validate_proposal
from app.developer_gateway import developer_material
from test_json_specification import json_design
from test_sa_gateway import values


def review_for(run):
    context = build_sa_context(run)
    return dict(version=1, run_id=context['run_id'], input_checksum=context['input_checksum'],
        context_checksum=context['context_checksum'], status='READY_FOR_REVIEW', summary='Synthetic review',
        evidence_ids=['requirement', 'source.0.json_input'], issues=[])


def test_json_role_context_and_citations_cannot_be_downgraded():
    spec, run, naming = json_design()
    sa = build_sa_context(run)
    assert sa['version'] == 6 and sa['deterministic_gate']['status'] == 'CHECKED'
    assert 'upload_id' not in str(sa) and 'sample_rows' not in str(sa)
    material = sa_material(sa)
    assert material['prompt_version'] == 8 and 'source.0.json_input' in material['prompt']
    review = review_for(run)
    validate_sa_review(review, sa)
    with pytest.raises(ValueError, match='SA_JSON_INPUT_EVIDENCE_REQUIRED'):
        validate_sa_review({**review, 'evidence_ids': ['requirement']}, sa)
    context = build_context(run, naming, {'approval_id': uuid4(), 'binding_checksum': 'c' * 64}, review)
    assert context['version'] == 5
    developer = developer_material(context)
    assert developer['prompt_version'] == 8
    assert 'EtlSpecificationV5' in developer['prompt'] and 'EtlSpecificationV1' not in developer['prompt']
    assert developer['schema']['properties']['version']['const'] == 5
    payload = dict(version=5, context_checksum=context['context_checksum'], summary='Synthetic design',
        evidence_ids=['requirement', 'source.0.json_input'], specification=spec)
    captured = {'context': context, 'run': run, 'naming': naming}
    assert validate_proposal(payload, captured)['status'] == 'VALIDATED_NOT_APPROVED'
    with pytest.raises(ValueError, match='DEVELOPER_JSON_INPUT_EVIDENCE_REQUIRED'):
        validate_proposal({**payload, 'evidence_ids': ['requirement']}, captured)
    wrong = deepcopy(context); wrong['version'] = 1
    wrong['context_checksum'] = digest({k: v for k, v in wrong.items() if k != 'context_checksum'})
    with pytest.raises(ValueError, match='DEVELOPER_CONTEXT_VERSION_MISMATCH'):
        validate_proposal(payload, {**captured, 'context': wrong})


def setup():
    _, run, _ = json_design()
    template, profile = values()
    run.update({k: template[k] for k in ('state', 'write_started', 'matches_current', 'approval', 'settings_snapshot')})
    run['settings_snapshot']['ai'] = {'provider_type': profile['provider_type']}
    return run, profile


def test_json_gateway_authorization_trace_and_prompt_share_material():
    run, profile = setup()
    context = build_sa_context(run); material = sa_material(context)
    assert authorization_offer(run)['prompt_checksum'] == material['prompt_checksum']
    calls = []
    def completion(**kwargs):
        calls.append(kwargs)
        assert kwargs['messages'][0]['content'] == material['prompt']
        assert json.loads(kwargs['messages'][1]['content'])['context'] == context
        return NS(choices=[NS(message=NS(content=json.dumps(review_for(run))))],
                  usage=NS(prompt_tokens=3, completion_tokens=4, total_tokens=7))
    output, trace = complete_sa_review(run, profile, completion=completion)
    assert len(calls) == 1 and output['status'] == 'READY_FOR_REVIEW'
    assert trace['prompt_version'] == 8 and trace['prompt_checksum'] == material['prompt_checksum']
    assert trace['execution_authorized'] is False


def test_missing_json_contract_stops_before_provider():
    run, profile = setup()
    run['input_snapshot']['source_config'].pop('json_input_contract_v1')
    with pytest.raises(SAInvocationError, match='SA_GATE_BLOCKED'):
        complete_sa_review(run, profile, completion=lambda **kw: pytest.fail('must not call provider'))
