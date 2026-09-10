from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


root = Path(__file__).resolve().parents[1]
env = load_env(root / ".env")
os.environ.update(env)
url = urlparse(env.get("DATABASE_URL", ""))

print(f"APP_MODE={env.get('APP_MODE', '')}")
print(f"PG_ENDPOINT={url.hostname}:{url.port}{url.path}")
print(f"PG_CREDENTIALS_SET={bool(url.username and url.password)}")
print(
    "VERTICA_ENDPOINT="
    f"{env.get('VERTICA_HOST', '')}:{env.get('VERTICA_PORT', '')}/"
    f"{env.get('VERTICA_DATABASE', '')}"
)
print(
    "VERTICA_CREDENTIALS_SET="
    f"{bool(env.get('VERTICA_USER') and env.get('VERTICA_PASSWORD'))}"
)
print(f"HOP_RUN_PATH={env.get('HOP_RUN_PATH', '')}")
print(f"ANALYZER_SCAN_ROOT={env.get('ANALYZER_SCAN_ROOT', '')}")

for relative in ("backend", "frontend/src", "database", "hop-project", "scan", "config"):
    files = [path for path in (root / relative).rglob("*") if path.is_file()]
    print(f"PATH={relative} FILES={len(files)} BYTES={sum(path.stat().st_size for path in files)}")

try:
    import psycopg

    with psycopg.connect(env["DATABASE_URL"], connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
            )
            print(f"POSTGRES_TABLES={cursor.fetchone()[0]}")
            cursor.execute("SELECT pg_database_size(current_database())")
            print(f"POSTGRES_BYTES={cursor.fetchone()[0]}")
except Exception as exc:
    print(f"POSTGRES_CHECK=ERROR:{type(exc).__name__}:{exc}")

try:
    import vertica_python

    with vertica_python.connect(
        host=env.get("VERTICA_HOST", "127.0.0.1"),
        port=int(env.get("VERTICA_PORT", "5433")),
        user=env.get("VERTICA_USER", "dbadmin"),
        password=env.get("VERTICA_PASSWORD", ""),
        database=env.get("VERTICA_DATABASE", "VMart"),
        tlsmode=env.get("VERTICA_TLSMODE", "disable"),
        connection_timeout=5,
    ) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT count(*) FROM v_catalog.tables "
            "WHERE table_schema NOT IN ('v_catalog', 'v_monitor')"
        )
        print(f"VERTICA_TABLES={cursor.fetchone()[0]}")
        cursor.execute("SELECT version()")
        print(f"VERTICA_VERSION={cursor.fetchone()[0]}")
except Exception as exc:
    print(f"VERTICA_CHECK=ERROR:{type(exc).__name__}:{exc}")
