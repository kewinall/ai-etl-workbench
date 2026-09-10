from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
HOP_ROOT = (ROOT / "hop-project").resolve()
load_dotenv(ROOT / ".env")


def referenced_jobs(path: Path) -> list[Path]:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return []
    found: list[Path] = []
    for node in root.iter():
        value = (node.text or "").strip()
        if value.lower().endswith((".hpl", ".hwf")):
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            candidate = candidate.resolve()
            if candidate.is_file() and HOP_ROOT in candidate.parents and candidate != path:
                found.append(candidate)
    return list(dict.fromkeys(found))


def main() -> None:
    added = 0
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "select artifact_id,task_id,version,file_path,is_current from platform.hop_artifact "
            "where parent_artifact_id is null order by created_at"
        ).fetchall()
        for artifact_id, task_id, version, file_path, is_current in rows:
            primary = Path(file_path).resolve()
            for related in referenced_jobs(primary):
                checksum = hashlib.sha256(related.read_bytes()).hexdigest()
                kind = "HWF" if related.suffix.lower() == ".hwf" else "HPL"
                result = conn.execute(
                    "insert into platform.hop_artifact(artifact_id,task_id,artifact_type,version,parent_artifact_id,file_path,checksum,file_size,is_current) "
                    "values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(task_id,file_path,version) do nothing returning artifact_id",
                    (uuid.uuid4(), task_id, kind, version, artifact_id, str(related), checksum, related.stat().st_size, is_current),
                ).fetchone()
                added += int(result is not None)
    print(f"registered {added} related HPL/HWF artifacts")


if __name__ == "__main__":
    main()
