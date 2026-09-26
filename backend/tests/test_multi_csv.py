from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import pytest
from app import task_uploads
from app.csv_contract import (CsvInputContractsV1, csv_contract_issues, csv_sources_evidence,
    revise_csv_contracts, source_csv_contract, validated_csv_contracts)
from app.source_preflight import source_preflight
from app.source_staging import stage_csv_sources
from app.sa_contract import build_sa_context


COMMA = dict(version=1, encoding='UTF-8', delimiter=',', header=True, extra_columns='REJECT')
PIPE = {**COMMA, 'delimiter': '|'}


def contracts():
    return {'version': 1, 'sources': {'source.0': deepcopy(COMMA), 'source.1': deepcopy(PIPE)}}


def config():
    return {'sources': [{'type': 'CSV', 'has_actual_data': True, 'fields': [{'name': 'id'}, {'name': 'name'}]} for _ in range(2)],
            'csv_input_contracts_v1': contracts()}


@pytest.mark.parametrize('version', [True, 1.0, '1', 2])
def test_multi_version_exact(version):
    with pytest.raises(ValueError):
        CsvInputContractsV1.model_validate({**contracts(), 'version': version})


@pytest.mark.parametrize('ref', ['source.00', 'source.-1', '../source', 'source.0.password', 'SOURCE.0'])
def test_source_refs_not_paths_or_loose_aliases(ref):
    raw = contracts()
    raw['sources'][ref] = raw['sources'].pop('source.1')
    with pytest.raises(ValueError):
        CsvInputContractsV1.model_validate(raw)


def test_exact_coverage_and_no_single_source_fallback():
    value = config()
    assert source_csv_contract(value, 'source.0')['delimiter'] == ','
    assert source_csv_contract(value, 'source.1')['delimiter'] == '|'
    value['csv_input_contracts_v1']['sources']['source.2'] = value['csv_input_contracts_v1']['sources'].pop('source.1')
    with pytest.raises(ValueError, match='COVERAGE_MISMATCH'):
        source_csv_contract(value, 'source.0')
    value = config()
    del value['csv_input_contracts_v1']
    value['csv_input_contract_v1'] = COMMA
    assert csv_contract_issues({'source_config': value})[0]['issue_type'] == 'MISSING'
    with pytest.raises(ValueError):
        source_csv_contract(value, 'source.1')


def test_revision_migrates_explicitly_without_mutating_original():
    value = config()
    del value['csv_input_contracts_v1']
    value['csv_input_contract_v1'] = COMMA
    before = deepcopy(value)
    result = revise_csv_contracts(value, contracts())
    assert value == before
    assert 'csv_input_contract_v1' not in result
    assert validated_csv_contracts(result) == contracts()
    assert csv_contract_issues({'source_config': result}) == []


@pytest.mark.parametrize('change', ['non_csv', 'all_non_csv', 'acquisition_missing', 'both_forms', 'too_few'])
def test_unsupported_layout_fails_closed(change):
    value = config()
    if change == 'non_csv':
        value['sources'][1]['type'] = 'EXCEL'
    elif change == 'all_non_csv':
        for source in value['sources']:
            source['type'] = 'EXCEL'
    elif change == 'acquisition_missing':
        del value['sources'][1]['has_actual_data']
    elif change == 'both_forms':
        value['csv_input_contract_v1'] = COMMA
    else:
        value['sources'].pop()
    with pytest.raises(ValueError):
        validated_csv_contracts(value)
    assert csv_contract_issues({'source_config': value})


def test_semantic_evidence_is_source_bound_without_secrets_and_changes_context():
    value = config()
    value['sources'][0].update(path='/private/file', password='private', samples=['private'])
    raw = {'source_config': value}
    run = {'run_id': 'test', 'input_checksum': 'a'*64, 'settings_snapshot': {'checksum': 'b'*64}, 'input_snapshot': raw}
    before = build_sa_context(run)
    assert 'private' not in str(before)
    evidence = csv_sources_evidence(value)
    assert [s['source_ref'] for s in evidence['sources']] == ['source.0', 'source.1']
    value['csv_input_contracts_v1']['sources']['source.1']['header'] = False
    assert before['context_checksum'] != build_sa_context(run)['context_checksum']
    value['csv_input_contracts_v1']['sources']['source.1']['password'] = 'private'
    assert csv_sources_evidence(value) == {'contract_status': 'INVALID'}


@pytest.fixture
def uploaded(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    left = task_uploads.save_and_profile('orders.csv', b'id,name\n1,A\n2,B\n')
    right = task_uploads.save_and_profile('customers.csv', b'id|name\n1|C\n3|D\n')
    # Profile does not decide this explicit delimiter contract. The field list
    # is the operator-confirmed structure, checked against bytes in preflight.
    right['fields'] = [{'name': 'id', 'type': 'BIGINT'}, {'name': 'name', 'type': 'VARCHAR(32)'}]
    return {'sources': [{**source, 'type': 'CSV', 'has_actual_data': True} for source in (left, right)],
            'csv_input_contracts_v1': contracts()}


def test_preflight_binds_each_uploaded_file_to_its_own_contract(uploaded):
    evidence, issues = source_preflight({'source_config': uploaded})
    assert issues == []
    assert [e['source_ref'] for e in evidence] == ['source.0', 'source.1']
    assert all(e['csv']['complete'] and e['csv']['records_checked'] == 2 for e in evidence)
    assert evidence[0]['csv']['contract_checksum'] != evidence[1]['csv']['contract_checksum']
    wrong = deepcopy(uploaded)
    wrong['csv_input_contracts_v1']['sources']['source.1'] = COMMA
    evidence, issues = source_preflight({'source_config': wrong})
    assert len(issues) == 1 and issues[0]['field_path'] == 'source_config.sources.1'
    assert evidence[0]['status'] == 'UPLOAD_BYTES_VERIFIED'
    assert evidence[1]['status'] == 'CSV_CONTENT_INVALID'


def test_stages_distinct_bytes_without_reopening_source_and_cleans_attempts(uploaded):
    originals = [Path(s['path']) for s in uploaded['sources']]
    with stage_csv_sources(uuid4(), uploaded) as result:
        sources = result['sources']
        assert set(sources) == {'source.0', 'source.1'}
        assert sources['source.0']['directory'] != sources['source.1']['directory']
        assert sources['source.0']['path'].read_bytes() == b'id,name\n1,A\n2,B\n'
        assert sources['source.1']['path'].read_bytes() == b'id|name\n1|C\n3|D\n'
        originals[1].write_bytes(b'id|name\n9|changed\n')
        assert sources['source.1']['path'].read_bytes() == b'id|name\n1|C\n3|D\n'
        directories = [s['directory'] for s in sources.values()]
        assert not result['execution_authorized']
    assert all(not path.exists() for path in directories)
    assert all(path.exists() for path in originals)


def test_second_source_tamper_cleans_first_copy_and_never_yields(uploaded):
    Path(uploaded['sources'][1]['path']).write_bytes(b'id|name\n7|changed\n')
    with pytest.raises(ValueError, match='UPLOAD_CONTENT_CHANGED'):
        with stage_csv_sources(uuid4(), uploaded):
            pytest.fail('Must not yield partial inputs')
    root = task_uploads.ROOT / 'runtime-temp' / 'run-sources'
    assert not list(root.iterdir())
    assert all(Path(s['path']).exists() for s in uploaded['sources'])


def test_executor_exception_cleans_both_copies(uploaded):
    with pytest.raises(RuntimeError):
        with stage_csv_sources(uuid4(), uploaded) as result:
            directories = [s['directory'] for s in result['sources'].values()]
            raise RuntimeError('Synthetic executor error')
    assert all(not path.exists() for path in directories)
