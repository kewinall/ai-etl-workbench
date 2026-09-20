from copy import deepcopy
import pytest
from app.csv_contract import CsvInputContractV1, csv_contract_issues, csv_evidence, revise_csv_contract
from app.control_worker import check_requirements
from app.sa_contract import build_sa_context


CONTRACT = {'version': 1, 'encoding': 'UTF-8', 'delimiter': ',', 'header': True, 'extra_columns': 'REJECT'}


def source():
    return {'sources': [{'type': 'CSV', 'alias': 'input', 'has_actual_data': False, 'fields': [{'name': 'id', 'type': 'BIGINT'}]}]}


@pytest.mark.parametrize('field', ['encoding', 'delimiter', 'header', 'extra_columns'])
def test_no_default_for_required_semantics(field):
    value = {k: v for k, v in CONTRACT.items() if k != field}
    with pytest.raises(ValueError):
        CsvInputContractV1.model_validate(value)


@pytest.mark.parametrize('changes', [{'header': 'false'}, {'header': 1}, {'delimiter': '||'}, {'encoding': 'auto'}, {'extra_columns': 'AUTO'}, {'path': '/private/file'}, {'version': 2}])
def test_no_coercion_inference_or_path(changes):
    with pytest.raises(ValueError):
        CsvInputContractV1.model_validate({**CONTRACT, **changes})


def test_csv_contract_blocks_before_model_and_preserves_original():
    snapshot = {'source_type': 'CSV', 'source_config': source(), 'requirement_text': 'Load explicitly defined CSV', 'target_config': {'schema': 'ai_sample', 'table': 'target', 'requirements_v1': {'write_mode': 'APPEND', 'date_scope': 'ALL'}}}
    assert check_requirements(snapshot)['status'] == 'NEEDS_INPUT'
    before = deepcopy(snapshot)
    updated = revise_csv_contract(snapshot['source_config'], CONTRACT)
    assert snapshot == before
    assert check_requirements({**snapshot, 'source_config': updated})['status'] == 'CHECKED'
    updated['csv_input_contract_v1']['header'] = 'false'
    assert csv_contract_issues({**snapshot, 'source_config': updated})[0]['issue_type'] == 'UNSUPPORTED'


def test_actual_file_metadata_preserved_but_never_sent_to_sa():
    config = source()
    config['sources'][0].update(has_actual_data=True, path='/private/file.csv', password='private-password', samples=[{'id': 'private-data'}])
    before = deepcopy(config)
    updated = revise_csv_contract(config, {**CONTRACT, 'header': False, 'delimiter': '\t', 'extra_columns': 'IGNORE'})
    assert config == before
    assert updated['sources'] == config['sources']
    evidence = csv_evidence(updated)
    assert evidence['header'] is False
    assert evidence['delimiter'] == '\t'
    assert evidence['acquisition'] == 'UPLOADED_CSV'
    assert 'private' not in str(evidence)
    run = {'run_id': 'run', 'input_checksum': 'a'*64, 'settings_snapshot': {'checksum': 'b'*64}, 'input_snapshot': {'source_config': updated}}
    context = build_sa_context(run)
    assert context['version'] == 2
    assert 'private' not in str(context)
    assert any(item['id'] == 'source.0.csv_input' for item in context['evidence'])
    run['input_snapshot']['source_config']['csv_input_contract_v1']['header'] = True
    assert build_sa_context(run)['context_checksum'] != context['context_checksum']


@pytest.mark.parametrize('sources', [[], [{'type': 'EXCEL', 'has_actual_data': False}], [{'type': 'CSV'}], source()['sources'] * 2])
def test_unsupported_sources_not_mutated(sources):
    config = {'sources': sources}
    with pytest.raises(ValueError, match='CSV_CONTRACT_EDIT_NOT_SUPPORTED'):
        revise_csv_contract(config, CONTRACT)
    assert revise_csv_contract(config, None) == config
