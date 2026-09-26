from copy import deepcopy
from uuid import uuid4
from unittest.mock import Mock
import pytest
from app.developer_contract import build_context, validate_proposal, DeveloperProposalV1
from app.developer_gateway import developer_material, complete_developer, PROMPT, PROMPT_VERSION
from app.sa_contract import digest
from test_join_semantics import join_design
from test_developer_contract import fixture
from test_developer_gateway import native


def multi_fixture():
    spec, run, naming = join_design()
    context = build_context(run, naming, {'approval_id': uuid4(), 'binding_checksum': 'c'*64},
                            {'status': 'READY_FOR_REVIEW'})
    return {'version': 2, 'context_checksum': context['context_checksum'], 'summary': 'Join design',
            'evidence_ids': ['requirement', 'join.conditions', 'sources.csv_inputs'],
            'specification': spec}, {'context': context, 'run': run, 'naming': naming}


def test_single_source_material_preserves_existing_prompt_and_schema():
    _, captured = fixture()
    material = developer_material(captured['context'])
    assert material == dict(prompt=PROMPT, prompt_version=PROMPT_VERSION,
        prompt_checksum=digest(PROMPT), schema=DeveloperProposalV1.model_json_schema(),
        schema_checksum=digest(DeveloperProposalV1.model_json_schema()))


def test_two_source_proposal_remains_advice_and_has_distinct_material():
    proposal, captured = multi_fixture()
    result = validate_proposal(proposal, captured)
    assert result['status'] == 'VALIDATED_NOT_APPROVED' and not result['execution_authorized']
    material = developer_material(captured['context'])
    assert material['prompt_version'] == 3 and material['prompt_checksum'] != digest(PROMPT)
    assert material['schema']['properties']['version']['const'] == 2
    assert material['schema']['properties']['specification']['$ref'].endswith('/EtlSpecificationV2')
    assert 'EtlSpecificationV1' not in material['prompt']


@pytest.mark.parametrize('change', ['version', 'spec_version', 'join', 'citation', 'context', 'extra_source'])
def test_invalid_two_source_handoffs_cannot_be_accepted(change):
    proposal, captured = multi_fixture()
    if change == 'version': proposal['version'] = 1
    if change == 'spec_version': proposal['specification']['version'] = 1
    if change == 'join': proposal['specification']['joins'][0]['join_type'] = 'INNER'
    if change == 'citation': proposal['evidence_ids'] = ['requirement']
    if change == 'context':
        captured['context']['version'] = 1
        captured['context']['context_checksum'] = digest({k:v for k,v in captured['context'].items() if k != 'context_checksum'})
        proposal['context_checksum'] = captured['context']['context_checksum']
    if change == 'extra_source':
        captured['run']['input_snapshot']['source_config']['sources'].append(
            deepcopy(captured['run']['input_snapshot']['source_config']['sources'][0]))
    with pytest.raises(ValueError): validate_proposal(proposal, captured)


def test_gateway_uses_v2_schema_prompt_and_exact_model_once():
    proposal, captured = multi_fixture()
    captured['run']['settings_snapshot']['model_routes'] = {'etl_specification': 'copilot/test-model'}
    profile = {'enabled': True, 'provider_type': 'LOCAL_COPILOT',
               'model_routes': {'etl_specification': 'test-model'}}
    call = Mock(side_effect=native(proposal))
    result, trace = complete_developer(captured, profile, native_completion=call, before_call=Mock())
    material = developer_material(captured['context'])
    assert call.call_count == 1 and result == proposal
    payload = call.call_args.args[0]
    assert payload['schema'] == material['schema'] and payload['prompt'] == material['prompt']
    assert trace['prompt_version'] == 3 and trace['schema_checksum'] == material['schema_checksum']
    assert not trace['execution_authorized'] and not trace['release_ready']


@pytest.mark.parametrize('version', [True, 2.0, '2'])
def test_v2_proposal_version_is_not_coerced(version):
    proposal, captured = multi_fixture()
    proposal['version'] = version
    with pytest.raises(ValueError): validate_proposal(proposal, captured)
