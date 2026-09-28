from datetime import date, datetime
from decimal import Decimal
import hashlib

import pytest

from app.field_inference import infer_field_type
from app.platform_harness import inferred_vertica_type
from app import task_uploads, source_profiler


@pytest.mark.parametrize('values,expected', [
    ([], 'VARCHAR(255)'),
    ([None, ''], 'VARCHAR(255)'),
    (['00123', '00001'], 'VARCHAR(32)'),
    (['-001', '+002'], 'VARCHAR(32)'),
    ([' 1', '2'], 'VARCHAR(32)'),
    (['0', '1'], 'BIGINT'),
    ([True, False], 'BOOLEAN'),
    (['true', 'FALSE'], 'BOOLEAN'),
    ([True, 1], 'VARCHAR(32)'),
    (['9223372036854775807'], 'BIGINT'),
    (['9223372036854775808'], 'DECIMAL(19,0)'),
    (['-9223372036854775808'], 'DECIMAL(19,0)'),
    (['12.50'], 'DECIMAL(18,4)'),
    (['0.123456789012345678'], 'DECIMAL(19,18)'),
    (['12345678901234567890.123456'], 'DECIMAL(26,6)'),
    ([Decimal('1.123456')], 'DECIMAL(18,6)'),
    ([Decimal('0.000000000000000001')], 'DECIMAL(19,18)'),
    (['1' * 39], 'VARCHAR(39)'),
    (['0.' + '1' * 19], 'VARCHAR(32)'),
    (['NaN', 'Infinity'], 'VARCHAR(32)'),
    (['2026-02-30'], 'VARCHAR(32)'),
    ([date(2026, 1, 1)], 'DATE'),
    ([datetime(2026, 1, 1, 12, 30, 1, 123456)], 'TIMESTAMP'),
    (['中文' * 10], 'VARCHAR(60)'),
    (['x' * 5000], 'VARCHAR(5000)'),
])
def test_shared_loss_averse_suggestions(values, expected):
    assert infer_field_type(values) == expected
    assert task_uploads._field_type(values) == expected
    assert inferred_vertica_type(values) == expected.replace('DECIMAL(', 'NUMERIC(')


@pytest.mark.parametrize('value', [{'nested': 1}, [1, 2], 'x' * 65001], ids=['object', 'array', 'oversize-text'])
def test_unsupported_values_are_not_silently_narrowed(value):
    with pytest.raises(ValueError):
        infer_field_type([value])


def test_explicit_declared_type_remains_authoritative():
    assert inferred_vertica_type(['001'], 'VARCHAR(40)') == 'VARCHAR(40)'


def test_json_precision_survives_upload_and_naming_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(task_uploads, 'UPLOAD_ROOT', tmp_path)
    content = b'[{"id":"001","amount":12345678901234567890.123456}]'
    result = task_uploads.save_and_profile('source.json', content)
    assert result['fields'] == [{'name': 'id', 'type': 'VARCHAR(32)'},
                                {'name': 'amount', 'type': 'DECIMAL(26,6)'}]
    assert result['sample_rows'][0]['amount'] == '12345678901234567890.123456'
    assert result['checksum'] == hashlib.sha256(content).hexdigest()
    profile = source_profiler.profile_task({'source': 'JSON', 'source_config': result})
    assert profile['sources'][0]['fields'] == [{'name': 'id', 'type': 'VARCHAR(32)'},
                                             {'name': 'amount', 'type': 'NUMERIC(26,6)'}]
    assert profile['fingerprint']
