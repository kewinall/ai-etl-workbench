"""Checksummed migrations. Untracked existing databases fail closed."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import psycopg
from .bootstrap import configure_environment


def migration_body(text: str) -> str:
    # The runner owns transactions so the ledger and schema commit together.
    text = re.sub(r"\A\s*BEGIN\s*;", "", text, flags=re.I)
    text = re.sub(r"COMMIT\s*;\s*\Z", "", text, flags=re.I)
    if re.search(r"^\s*(BEGIN|COMMIT|ROLLBACK)\s*;", text, flags=re.I | re.M):
        raise ValueError("Embedded transaction boundaries are not supported")
    return text


def migration_fingerprints(raw: bytes) -> tuple[str, set[str]]:
    # Git checkouts may change CRLF/LF without changing SQL. Accept only those
    # exact newline/BOM equivalents, never whitespace or semantic rewrites.
    text = raw.decode('utf-8-sig').replace('\r\n', '\n')
    canonical = hashlib.sha256(text.encode('utf-8')).hexdigest()
    variants = {hashlib.sha256(raw).hexdigest(), canonical}
    for value in (text, text.replace('\n', '\r\n')):
        variants.add(hashlib.sha256(value.encode('utf-8')).hexdigest())
        variants.add(hashlib.sha256(value.encode('utf-8-sig')).hexdigest())
    return canonical, variants


def migrate(url: str, directory: Path) -> list[str]:
    paths = sorted(directory.glob("*.sql"))
    if not paths:
        raise ValueError("No migration files found")
    applied = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(784202601)")
        try:
            ledger = conn.execute("SELECT to_regclass('platform.schema_migration')").fetchone()[0]
            existing = conn.execute("SELECT to_regclass('platform.task')").fetchone()[0]
            if existing and not ledger:
                raise ValueError("Untracked existing database: backup and reviewed baseline adoption required")
            with conn.transaction():
                conn.execute("CREATE SCHEMA IF NOT EXISTS platform")
                conn.execute("CREATE TABLE IF NOT EXISTS platform.schema_migration (name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
            recorded = dict(conn.execute("SELECT name, checksum FROM platform.schema_migration").fetchall())
            if set(recorded) - {p.name for p in paths}:
                raise ValueError("Applied migration files are missing from this version")
            for path in paths:
                digest, equivalent = migration_fingerprints(path.read_bytes())
                if path.name in recorded:
                    if recorded[path.name] not in equivalent:
                        raise ValueError(f"Migration checksum mismatch: {path.name}")
                    continue
                if recorded and path.name < max(recorded):
                    raise ValueError(f"Out-of-order migration: {path.name}")
                with conn.transaction():
                    conn.execute(migration_body(path.read_text(encoding="utf-8-sig")))
                    conn.execute("INSERT INTO platform.schema_migration(name, checksum) VALUES (%s, %s)", (path.name, digest))
                applied.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(784202601)")
    return applied


if __name__ == "__main__":
    import os
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[2] / "database" / "migrations")
    args = parser.parse_args()
    configure_environment()
    try:
        result = migrate(os.environ["DATABASE_URL"], args.directory)
    except (ValueError, psycopg.Error) as exc:
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        raise SystemExit(f"Migration blocked: {message}") from None
    print(f"Applied {len(result)} migrations")
