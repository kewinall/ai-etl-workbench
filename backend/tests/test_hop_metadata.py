import json
from app.hop_metadata import local_metadata,local_metadata_json


def test_local_export_is_deterministic_and_has_no_connections():
    value=local_metadata()
    assert set(value)=={'pipeline-run-configuration'}
    config=value['pipeline-run-configuration'][0]
    assert config['name']=='local'
    assert config['engineRunConfiguration']['Local']['gather_metrics'] is True
    assert local_metadata_json()==local_metadata_json()
    assert json.loads(local_metadata_json())==value


def test_callers_cannot_mutate_future_defaults():
    first=local_metadata()
    first['pipeline-run-configuration'][0]['name']='wrong'
    assert local_metadata()['pipeline-run-configuration'][0]['name']=='local'
