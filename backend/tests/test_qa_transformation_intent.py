from copy import deepcopy
import pytest
from app.qa_contract import build_qa_context, validate_qa_review, REQUIRED_CHECKS
from app.qa_transformation_intent import check_intent
from app import qa_journal
from app.sa_contract import digest
from test_qa_single_source_contract import contexts
from test_qa_multisource import context_fixture
from test_transformation_contract import intent


def enhanced(monkeypatch, multi=False):
    if multi:
        run, compiled, checks, sem = context_fixture(monkeypatch)
        old = build_qa_context(run['run_id'], compiled['specification_checksum'], checks, sem)
        contract = dict(version=1, filters=[], filter_logic='ALL', filter_null_policy='EXCLUDE_UNKNOWN',
                        aggregation=None, output_columns=['source.0.客戶編號','source.0.名稱','source.1.客戶編號','source.1.名稱'])
    else:
        _, old, _, _, _ = contexts(monkeypatch)
        contract = intent()
    sem = deepcopy(old['semantics']); sem['transformation_intent'] = contract
    new = build_qa_context(old['run_id'], old['specification_checksum'], old['evidence'], sem)
    return old, new


@pytest.mark.parametrize('multi', [False, True])
def test_new_context_binds_independent_intent_and_keeps_old_canonical_bytes(monkeypatch, multi):
    old, new = enhanced(monkeypatch, multi)
    assert new['version'] == (10 if multi else 9)
    assert build_qa_context(old['run_id'], old['specification_checksum'], old['evidence'], old['semantics']) == old
    assert build_qa_context(new['run_id'], new['specification_checksum'], new['evidence'], new['semantics']) == new
    # No same-run approval/context migration: intent changes belong to revisions.
    assert not qa_journal.same_execution_enrichment(old, new)
    review = {key: new[key] for key in ('run_id', 'specification_checksum', 'context_checksum')}
    review.update(version=1, status='PASS', summary='Synthetic intent review', evidence_ids=[*REQUIRED_CHECKS, 'semantic_design'], issues=[])
    assert not validate_qa_review(review, new)['qa_approved']


@pytest.mark.parametrize('change', ['operator', 'constant', 'count', 'source', 'projection', 'mapping', 'no_details'])
def test_canonical_rebuild_rejects_wrong_intent_or_mapping(monkeypatch, change):
    _, new = enhanced(monkeypatch)
    sem = deepcopy(new['semantics']); value = sem['transformation_intent']
    if change == 'operator': value['filters'][0]['operator'] = 'GE'
    elif change == 'constant': value['filters'][0]['constant']['value'] = '20.00'
    elif change == 'count': value['aggregation']['metrics'][1].update(function='COUNT_NON_NULL', column='source.0.類別')
    elif change == 'source': value['filters'][0]['column'] = 'source.1.金額'
    elif change == 'projection': value['output_columns'].reverse()
    elif change == 'mapping': sem['execution_details']['compiler_plan']['stages'][0]['fields'][0]['stream_name'] = 'wrong'
    else: sem['execution_details'] = None
    with pytest.raises(ValueError, match='QA_TRANSFORMATION_'):
        build_qa_context(new['run_id'], new['specification_checksum'], new['evidence'], sem)


def test_invented_mapping_and_duplicates_cannot_pass(monkeypatch):
    _, new = enhanced(monkeypatch)
    sem = new['semantics']; plan = deepcopy(sem['execution_details']['compiler_plan'])
    plan['stages'][0]['fields'].append(plan['stages'][0]['fields'][0])
    with pytest.raises(ValueError, match='QA_TRANSFORMATION_MAPPING_INVALID'):
        check_intent(sem['transformation_intent'], sem['specification'], plan)


def test_rehashed_context_cannot_hide_modified_intent(monkeypatch):
    _, context = enhanced(monkeypatch)
    context['semantics']['transformation_intent']['filters'][0]['operator'] = 'GE'
    context['context_checksum'] = digest({key: value for key, value in context.items() if key != 'context_checksum'})
    with pytest.raises(ValueError): validate_qa_review({}, context)
