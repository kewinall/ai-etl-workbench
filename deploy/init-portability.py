"""Initialize an isolated disposable test secret, never print or replace it."""
import os
import secrets
from pathlib import Path

root = Path('/run/portability-secrets')
root.mkdir(exist_ok=True)
os.chmod(root, 0o755)
path = root / 'password'
if path.is_symlink():
    raise SystemExit('UNSAFE_SECRET_PATH')
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
except FileExistsError:
    if not path.is_file() or path.stat().st_size != 64:
        raise SystemExit('EXISTING_SECRET_INVALID')
else:
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(secrets.token_hex(32))
        stream.flush()
        os.fsync(stream.fileno())
print('PORTABILITY_SECRET_READY')
