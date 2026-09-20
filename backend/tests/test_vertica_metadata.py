import json
import pytest
from app.hop_metadata import vertica_metadata_json


def connection():
    return dict(type='VERTICA', host='synthetic.invalid', database='synthetic', user='synthetic', port=5433, tlsmode='disable')


def test_private_metadata_uses_password_reference_and_explicit_tls():
    value = connection()
    result = json.loads(vertica_metadata_json(value))
    db = result['rdbms'][0]['rdbms']['VERTICA5']
    assert db['password'] == '${WORKBENCH_VERTICA_PASSWORD}'
    assert db['attributes']['EXTRA_OPTION_VERTICA5.TLSmode'] == 'disable'
    assert result['rdbms'][0]['name'] == 'etl_target'
    assert value == connection()


@pytest.mark.parametrize('field,value', [('host','${OTHER_HOST}'),('database','db?option=x'),('password','secret'),('port',True),('tlsmode',None),('tlsmode','prefer')])
def test_reject_implicit_or_unsafe_connection(field, value):
    config = connection();config[field] = value
    with pytest.raises(ValueError): vertica_metadata_json(config)
