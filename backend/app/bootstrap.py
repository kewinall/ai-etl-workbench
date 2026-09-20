"""Container bootstrap, independent of the legacy host .env."""
from __future__ import annotations
import base64
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import quote


def configure_environment() -> None:
    password_file = os.getenv("DATABASE_PASSWORD_FILE")
    if password_file:
        password = Path(password_file).read_text().strip()
        if not password:
            raise ValueError("Database password file is empty")
        os.environ["DATABASE_URL"] = (
            f"postgresql://{quote(os.getenv('DATABASE_USER', 'workbench'), safe='')}:"
            f"{quote(password, safe='')}@{os.getenv('DATABASE_HOST', 'postgres')}:"
            f"{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_NAME', 'workbench')}"
        )
    key_file = os.getenv("PLATFORM_SETTINGS_ENCRYPTION_KEY_FILE")
    if key_file:
        os.environ["PLATFORM_SETTINGS_ENCRYPTION_KEY"] = Path(key_file).read_text().strip()


def initialize_volumes() -> None:
    root = Path("/run/workbench-secrets")
    root.mkdir(parents=True, exist_ok=True)
    for name, value in {
        "postgres_password": secrets.token_urlsafe(32),
        "settings_key": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    }.items():
        path = root / name
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if not path.read_text().strip():
                raise ValueError(f"Existing secret file is empty: {name}")
        else:
            with os.fdopen(fd, "w") as stream:
                stream.write(value)
        os.chown(path, 10001, 10001)
        os.chmod(path, 0o600)
    for name in ("runtime-temp", "hop-project", "outputs"):
        path = Path("/app") / name
        path.mkdir(parents=True, exist_ok=True)
        os.chown(path, 10001, 10001)


if __name__ == "__main__":
    if sys.argv[1:] == ["init-secrets"]:
        initialize_volumes()
    else:
        configure_environment()
        if not sys.argv[1:]:
            raise SystemExit("An explicit command is required")
        os.execvp(sys.argv[1], sys.argv[1:])
