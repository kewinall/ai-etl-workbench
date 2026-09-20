"""Private preparation only; caller must enforce Run approval and write gates."""
from contextlib import contextmanager
from hashlib import sha256
import json
import re
from .hop_metadata import vertica_metadata_json


@contextmanager
def connection_runtime(repo, snapshot, expected_checksum):
    if not isinstance(snapshot, dict) or snapshot.get('version') != 1:
        raise ValueError('INVALID_SETTINGS_SNAPSHOT')
    content = {key: value for key, value in snapshot.items() if key != 'checksum'}
    checksum = sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if checksum != expected_checksum or snapshot.get('checksum') != checksum:
        raise ValueError('SETTINGS_SNAPSHOT_CHANGED')
    identity = snapshot.get('connection_id')
    connection = snapshot.get('connection')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_-]{2,80}', identity) or not isinstance(connection, dict) or connection.get('connection_id') != identity:
        raise ValueError('CONNECTION_ID_MISMATCH')
    metadata = vertica_metadata_json(connection)
    version = (snapshot.get('credential_versions') or {}).get('connection')
    secret = repo.read_secret_at_version('connection:' + identity, version)
    if not isinstance(secret, str) or not secret or '\x00' in secret:
        raise ValueError('CONNECTION_SECRET_UNAVAILABLE')
    # Never put this mapping into API responses, events, logs or release artifacts.
    environment = {'WORKBENCH_VERTICA_PASSWORD': secret}
    try:
        yield {'metadata': metadata, 'metadata_checksum': sha256(metadata.encode()).hexdigest(),
               'environment': environment}
    finally:
        environment.clear()
        # Python strings cannot guarantee secure memory erasure.
        secret = None
