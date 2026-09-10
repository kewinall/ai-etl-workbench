"""Verify no-file Stage modes create readable Task-scoped files on Vertica."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import vertica_python
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.execution import build_stage_hwf, static_validate
from app.sample_data import materialize_stage_server_sample

load_dotenv()


def connect():
    return vertica_python.connect(
        host=os.getenv("VERTICA_HOST", "127.0.0.1"),
        port=int(os.getenv("VERTICA_PORT", "5433")),
        database=os.getenv("VERTICA_DATABASE", "VMart"),
        user=os.getenv("VERTICA_USER", "dbadmin"),
        password=os.getenv("VERTICA_PASSWORD", ""),
        tlsmode=os.getenv("VERTICA_TLSMODE", "disable"),
        autocommit=True,
    )


def run_mode(mode: str):
    fields = [
        {"name": "record_id", "type": "INT"},
        {"name": "region", "type": "VARCHAR(20)"},
        {"name": "amount", "type": "NUMERIC(12,2)"},
    ]
    task_id = f"SERVER-SAMPLE-{mode}-E2E"
    table = f"server_sample_{mode.lower()}_e2e"
    target = materialize_stage_server_sample(
        task_id,
        {
            "stage_mode": mode,
            "format": "JSON" if mode == "FLEX" else "CSV",
            "data_directory": f"/data/ai_agents_v2_{mode.lower()}_20260820_v4",
            "reject_path": "/data/ai_agents_v2_reject",
            "exception_path": "/data/ai_agents_v2_exception",
            "schema": "public",
            "table": table,
            "delimiter": ",",
            "quote": '"',
            "header": True,
        },
        {"type": "CSV", "has_actual_data": False, "fields": fields},
    )
    artifact = build_stage_hwf(
        {
            "id": task_id,
            "category": "STAGE",
            "source": "CSV",
            "source_config": {"sources": [{"fields": fields}]},
            "target_config": target,
        },
        [item["name"] for item in fields],
    )
    assert static_validate(artifact)["valid"]
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS public."{table}"')
        for statement in [part.strip() for part in artifact["sql"].split(";") if part.strip()]:
            cursor.execute(statement)
        cursor.execute(f'SELECT COUNT(*) FROM public."{table}"')
        count = cursor.fetchone()[0]
    return {"mode": mode, "data_path": target["data_path"], "rows": count, "artifact": artifact["path"]}


if __name__ == "__main__":
    print(json.dumps([run_mode("EXTERNAL"), run_mode("FLEX")], ensure_ascii=False, indent=2))
