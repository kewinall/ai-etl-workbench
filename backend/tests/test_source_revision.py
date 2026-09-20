from copy import deepcopy
import pytest
from app.source_revision import revise_source, SourceFieldsV1, editable_source


def source():
    return {'sources': [{'type': 'CSV', 'alias': 'synthetic', 'has_actual_data': False, 'fields': [{'name': 'id', 'type': 'BIGINT', 'description': 'Keep description'}]}]}


def test_only_metadata_changes_and_original_stays_intact():
    value = source()
    old = deepcopy(value)
    result = revise_source(value, {'fields': [{'name': 'id', 'type': 'INTEGER'}, {'name': '日期', 'type': 'DATE'}]})
    assert value == old
    assert result['sources'][0]['alias'] == 'synthetic'
    assert result['sources'][0]['fields'][0]['description'] == 'Keep description'
    assert len(result['sources'][0]['fields']) == 2


@pytest.mark.parametrize('fields', [[], [{'name': 'id', 'type': 'SQL'}], [{'name': 'id', 'type': 'DATE'}, {'name': 'ID', 'type': 'DATE'}], [{'name': ' ', 'type': 'DATE'}]])
def test_invalid_fields_rejected(fields):
    with pytest.raises(ValueError):
        SourceFieldsV1.model_validate({'fields': fields})


@pytest.mark.parametrize('key,value', [('has_actual_data', True), ('file_path', '/existing.csv'), ('sample_rows', [{'id': 1}]), ('unknown_data', 'opaque')])
def test_actual_or_unrecognized_source_cannot_be_edited(key, value):
    config = source()
    config['sources'][0][key] = value
    assert not editable_source(config)
    with pytest.raises(ValueError):
        revise_source(config, {'fields': [{'name': 'id', 'type': 'DATE'}]})
    assert revise_source(config, None) == config


def test_multiple_sources_cannot_be_edited():
    config = source()
    config['sources'] *= 2
    assert not editable_source(config)
