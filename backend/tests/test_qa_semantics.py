from copy import deepcopy
import pytest
from app.qa_contract import build_qa_context, validate_qa_review, REQUIRED_CHECKS
from app.sa_contract import digest
from test_etl_specification import design


def sample():
    spec, run, _ = design()
    checks=[dict(id=name,status='PASS',checksum='a'*64,summary='Synthetic deterministic evidence') for name in REQUIRED_CHECKS]
    semantics=dict(requirement=run['input_snapshot']['requirement_text'],
        conditions=run['input_snapshot']['target_config']['requirements_v1'], specification=spec,
        nodes=[dict(id='source',component='CSVInput'),dict(id='aggregate',component='GroupBy')])
    context=build_qa_context(run['run_id'],digest(spec),checks,semantics)
    review={key:context[key] for key in ('run_id','specification_checksum','context_checksum')}
    review.update(version=1,status='PASS',summary='Synthetic review',evidence_ids=[*REQUIRED_CHECKS,'semantic_design'],issues=[])
    return context, review


def test_semantic_context_binds_original_requirement_design_and_nodes():
    context,review=sample()
    assert context['version']==2 and context['semantics']['specification']['filters']
    assert not validate_qa_review(review,context)['qa_approved']
    review['evidence_ids'].remove('semantic_design')
    with pytest.raises(ValueError,match='COMPLETE_EVIDENCE'): validate_qa_review(review,context)


def test_semantic_findings_can_cite_real_nodes_but_not_invented_nodes():
    context,review=sample()
    review.update(status='NEEDS_REVIEW',issues=[{'message':'Need confirmation of grouping','evidence_ids':['semantic_design','node.aggregate']}])
    assert validate_qa_review(review,context)['status']=='NEEDS_REVIEW'
    review['issues'][0]['evidence_ids']=['node.invented']
    with pytest.raises(ValueError,match='UNKNOWN_EVIDENCE'): validate_qa_review(review,context)


@pytest.mark.parametrize('field',['requirement','specification','nodes'])
def test_semantic_tampering_invalidates_checksum(field):
    context,review=sample(); changed=deepcopy(context)
    changed['semantics'][field]='modified'
    with pytest.raises(ValueError,match='CONTEXT_CHANGED'):validate_qa_review(review,changed)


def test_recomputed_context_still_rejects_wrong_specification_binding():
    context,_=sample(); context['semantics']['specification']['target_table']='other'
    with pytest.raises(ValueError,match='SEMANTIC_SPECIFICATION_CHANGED'):
        build_qa_context(context['run_id'],context['specification_checksum'],context['evidence'],context['semantics'])
