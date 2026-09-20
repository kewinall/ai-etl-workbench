from unittest.mock import Mock
from hashlib import sha256
import json
import pytest
from app.release_secret_screen import run_forbidden_values


def setup():
    s=dict(connection={'host':'private-host','database':'private-db','user':'operator'},
        ai_profile_id='ai',ai_profile_version='v1',connection_id='db',credential_versions={'connection':'c1','ai':'a1'})
    s['checksum']=sha256(json.dumps(s,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    repo=Mock();repo.ai_profile.return_value={'updated_at':'v1','secret_ref':'ai-key'}
    repo.read_secret_at_version.side_effect=['db-secret','ai-secret']
    return repo,s


def test_pinned_values_cleared_after_scope():
    repo,s=setup()
    with run_forbidden_values(repo,s) as values:assert 'db-secret' in values and 'ai-secret' in values
    assert values==[]
    assert repo.read_secret_at_version.call_args_list[0].args==('connection:db','c1')
    assert repo.read_secret_at_version.call_args_list[1].args==('ai-key','a1')


def test_changed_profile_or_credential_does_not_fallback():
    repo,s=setup();repo.ai_profile.return_value['updated_at']='v2'
    with pytest.raises(ValueError,match='RELEASE_AI_PROFILE_CHANGED'):
        with run_forbidden_values(repo,s):pass
    repo.read_secret_at_version.assert_not_called()
    repo,s=setup();repo.read_secret_at_version.side_effect=ValueError('CREDENTIAL_VERSION_CHANGED')
    with pytest.raises(ValueError,match='CREDENTIAL_VERSION_CHANGED'):
        with run_forbidden_values(repo,s):pass
