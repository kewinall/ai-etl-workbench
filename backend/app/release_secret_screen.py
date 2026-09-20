"""Run-scoped vault values, transient only. Not a scan of unrelated accounts."""
from contextlib import contextmanager
from hashlib import sha256
import json


@contextmanager
def run_forbidden_values(repo,snapshot):
    expected=sha256(json.dumps({k:v for k,v in snapshot.items() if k!='checksum'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if snapshot.get('checksum')!=expected:raise ValueError('RELEASE_SETTINGS_CHANGED')
    values=[]
    try:
        connection=snapshot['connection']
        values.extend(str(connection[k]) for k in ('host','database','user') if connection.get(k))
        profile=repo.ai_profile(snapshot['ai_profile_id'])
        if not profile or str(profile.get('updated_at'))!=snapshot['ai_profile_version']:
            raise ValueError('RELEASE_AI_PROFILE_CHANGED')
        if profile.get('endpoint'):values.append(profile['endpoint'])
        versions=snapshot['credential_versions']
        refs=[('connection:'+snapshot['connection_id'],versions['connection'])]
        if profile.get('secret_ref'):
            refs.append((profile['secret_ref'],versions['ai']))
        elif versions['ai'] is not None:raise ValueError('RELEASE_AI_PROFILE_CHANGED')
        for ref,version in refs:
            value=repo.read_secret_at_version(ref,version)
            if not isinstance(value,str) or not value:raise ValueError('RELEASE_SECRET_UNAVAILABLE')
            values.append(value)
        yield values
    finally:
        values.clear()  # Python strings cannot guarantee secure memory erasure.
