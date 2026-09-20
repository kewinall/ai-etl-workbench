from hashlib import sha256
import json
import pytest
from app.hop_connection_runtime import connection_runtime


def snapshot():
    data={'version':1,'connection_id':'test-db','credential_versions':{'connection':'v1'},
          'connection':dict(connection_id='test-db',type='VERTICA',host='synthetic.invalid',database='synthetic',user='synthetic',port=5433,tlsmode='disable')}
    data['checksum']=sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return data


class Repo:
    def read_secret_at_version(self, ref, version):
        assert (ref,version)==('connection:test-db','v1')
        return 'synthetic-secret'


def test_runtime_uses_versioned_secret_and_clears_environment():
    data=snapshot()
    with connection_runtime(Repo(), data, data['checksum']) as runtime:
        assert 'synthetic-secret' not in runtime['metadata']
        assert runtime['environment']['WORKBENCH_VERTICA_PASSWORD']=='synthetic-secret'
    assert runtime['environment']=={}


def test_modified_snapshot_rejected_before_secret_read():
    data=snapshot();data['connection']['host']='other.invalid'
    with pytest.raises(ValueError,match='SETTINGS_SNAPSHOT_CHANGED'):
        with connection_runtime(None,data,data['checksum']): pass
