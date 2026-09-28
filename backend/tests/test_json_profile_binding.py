from copy import deepcopy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import task_uploads, upload_integrity
from app.json_source_profile import confirmed_json_profile, verify_json_source, create_json_profile_router
from app.json_contract_binding import validated_json_contract, json_contract_issues, json_evidence
from app.source_preflight import source_preflight
from test_json_input_contract import policy


CONTENT = b'\xef\xbb\xbf[{"id":"001","amount":12.34},{"id":"002"},{}]'


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'ROOT', tmp_path)
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path / 'uploads')
    upload = task_uploads.save_and_profile('synthetic.json', CONTENT)
    profile = confirmed_json_profile(upload['upload_id'], upload['checksum'], upload['size'])
    return {**upload, **profile, 'type': 'JSON', 'has_actual_data': True}


def test_bound_full_profile_and_preflight(source):
    config = {'sources': [source], 'json_input_contract_v1': policy()}
    assert verify_json_source(source)['row_count'] == 3
    assert validated_json_contract(config)['contract'] == policy()
    assert not json_contract_issues({'source_type': 'JSON', 'source_config': config})
    evidence, issues = source_preflight({'source_config': config})
    assert not issues
    assert evidence[0]['json']['records_expected'] == 3
    assert evidence[0]['json']['reader_content_checksum'] != source['checksum']
    assert not evidence[0]['execution_authorized']
    assert not evidence[0]['json']['type_conversion_verified']
    assert 'sample_rows' not in str(json_evidence(config))
    assert 'upload_id' not in str(json_evidence(config))


@pytest.mark.parametrize('key,value', [('root_shape', 'OBJECT'), ('fields', []),
    ('checksum', '0' * 64), ('size', True), ('json_profile_binding_v1', None)])
def test_changed_source_cannot_reuse_binding(source, key, value):
    source[key] = value
    with pytest.raises(ValueError):
        verify_json_source(source)
    with pytest.raises(ValueError):
        validated_json_contract({'sources': [source], 'json_input_contract_v1': policy()})


@pytest.mark.parametrize('key,value', [('version', True), ('profile_version', 1.0),
                                     ('row_count', True), ('scope', 'EXECUTION_APPROVED')])
def test_binding_envelope_is_exact(source, key, value):
    source['json_profile_binding_v1'][key] = value
    with pytest.raises(ValueError):
        verify_json_source(source)
    with pytest.raises(ValueError):
        validated_json_contract({'sources': [source], 'json_input_contract_v1': policy()})


def test_policy_missing_and_conflicting_forms(source):
    config = {'sources': [source]}
    assert json_contract_issues({'source_config': config})[0]['issue_type'] == 'MISSING'
    config['json_input_contract_v1'] = policy()
    for key in ('csv_input_contract_v1', 'csv_input_contracts_v1', 'excel_input_contract_v1'):
        assert json_contract_issues({'source_config': {**config, key: None}})[0]['issue_type'] == 'CONFLICT'
    config['sources'].append(deepcopy(source))
    assert json_contract_issues({'source_config': config})[0]['issue_type'] == 'CONFLICT'


def test_endpoint_rejects_paths_and_stale_bytes(source):
    app = FastAPI()
    app.include_router(create_json_profile_router())
    api = TestClient(app)
    url = f"/api/task-sources/{source['upload_id']}/json-profile"
    body = {'checksum': source['checksum'], 'size': source['size']}
    assert api.post(url, json=body).status_code == 200
    assert api.post(url, json={**body, 'path': '/tmp/arbitrary.json'}).status_code == 422
    assert api.post(url, json={**body, 'size': str(source['size'])}).status_code == 422
    assert api.post(url, json={**body, 'checksum': '0' * 64}).status_code == 422
    assert api.post('/api/task-sources/not-an-id/json-profile', json=body).status_code == 422


def test_verified_snapshot_is_not_reopened(source, monkeypatch):
    def forbidden(*args):
        raise AssertionError('must not reopen verified bytes')
    monkeypatch.setattr(upload_integrity, 'read_verified_upload', forbidden)
    assert verify_json_source(source, content=CONTENT)['row_count'] == 3
    with pytest.raises(ValueError, match='UPLOAD_CONTENT_CHANGED'):
        verify_json_source(source, content=CONTENT + b' ')
