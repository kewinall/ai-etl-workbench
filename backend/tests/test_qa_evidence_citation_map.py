"""Regression: real QA mistook a documented citation alias for missing evidence."""
from app.qa_gateway import PROMPT, PROMPT_VERSION, complete_qa_review
from app.sa_contract import digest
from test_qa_semantics import sample


def test_native_payload_explains_alias_without_changing_evidence_or_forcing_pass():
    context, review = sample()
    review.update(status='NEEDS_REVIEW', issues=[{
        'message': 'Semantic detail still needs operator review',
        'evidence_ids': ['semantic_design', 'node.aggregate'],
    }])
    model = 'copilot/synthetic-test'
    run = dict(run_id=context['run_id'], state='NEEDS_REVIEW', write_started=True,
        matches_current=True, lease_token=None, outcome_code='HOP_EXECUTED_QA_REQUIRED',
        settings_snapshot={'model_routes': {'qa_review': model}})
    profile = dict(enabled=True, provider_type='LOCAL_COPILOT', model_routes={'qa_review': model})
    calls = []

    def completion(payload, selected_model, *, before_call):
        calls.append(payload)
        assert payload['context'] == context
        assert 'semantic_design is the citation ID for the separate context.semantics object' in payload['prompt']
        assert 'not a sixth entry in context.evidence' in payload['prompt']
        assert 'return NEEDS_REVIEW' in payload['prompt']
        assert len(context['evidence']) == 5
        assert selected_model == model
        return review, dict(provider='LOCAL_COPILOT', model=model,
            **{key:context[key] for key in ('run_id','specification_checksum','context_checksum')},
            prompt_checksum=payload['prompt_checksum'], schema_checksum=payload['schema_checksum'], usage=None)

    result, trace = complete_qa_review(run, profile, context,
        native_completion=completion, before_call=lambda: None)
    assert len(calls) == 1 and PROMPT_VERSION == 4
    assert 'without rerunning ETL' in PROMPT
    assert 'never assume that added detail requires PASS' in PROMPT
    assert trace['prompt_checksum'] == digest(PROMPT)
    assert result['status'] == 'NEEDS_REVIEW'
    assert not result['qa_approved'] and not result['release_ready']
