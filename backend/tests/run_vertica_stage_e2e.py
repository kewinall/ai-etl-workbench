"""Real Vertica Stage-path verification for the development environment."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import vertica_python
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.execution import build_stage_hwf, static_validate


load_dotenv()

EXTERNAL_DIR = "/data/ai_agents_v2_external_20260820_v4"
FLEX_DIR = "/data/ai_agents_v2_flex_20260820_v4"


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


def main() -> None:
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute("DROP TABLE IF EXISTS public.stage_external_orders_platform_e2e")
        cursor.execute("DROP TABLE IF EXISTS public.stage_flex_events_platform_e2e")

        cursor.execute(
            f"""EXPORT TO DELIMITED(
                directory='{EXTERNAL_DIR}', filename='orders.csv', delimiter=',',
                enclosedBy='"', addHeader='true')
                AS SELECT 1001::INT AS order_id, 'North'::VARCHAR(20) AS region, 125.50::NUMERIC(12,2) AS amount
                UNION ALL SELECT 1002, 'South', 240.00
                UNION ALL SELECT 1003, 'North', 315.25"""
        )
        external_exported = cursor.fetchone()[0]

        external_artifact = build_stage_hwf(
            {
                "id": "VERTICA-STAGE-EXTERNAL-E2E",
                "category": "STAGE",
                "source": "CSV",
                "source_config": {"sources": [{"fields": [
                    {"name": "order_id", "type": "INT"},
                    {"name": "region", "type": "VARCHAR(20)"},
                    {"name": "amount", "type": "NUMERIC(12,2)"},
                ]}]},
                "target_config": {
                    "schema": "public", "table": "stage_external_orders_platform_e2e",
                    "stage_mode": "EXTERNAL", "data_path": f"{EXTERNAL_DIR}/*.csv",
                    "reject_path": "/data/ai_agents_v2_reject/",
                    "exception_path": "/data/ai_agents_v2_exception/",
                    "delimiter": ",", "quote": '"', "header": True,
                },
            },
            ["order_id", "region", "amount"],
        )
        assert static_validate(external_artifact)["valid"]
        cursor.execute(external_artifact["sql"])
        cursor.execute(
            "SELECT order_id, region, amount::VARCHAR FROM public.stage_external_orders_platform_e2e ORDER BY order_id"
        )
        external_rows = cursor.fetchall()

        cursor.execute(
            f"""EXPORT TO JSON(directory='{FLEX_DIR}', filename='events.json')
                AS SELECT 2001::INT AS event_id, 'LOGIN'::VARCHAR(20) AS event_type, 'web'::VARCHAR(20) AS channel
                UNION ALL SELECT 2002, 'PURCHASE', 'mobile'
                UNION ALL SELECT 2003, 'LOGOUT', 'web'"""
        )
        flex_exported = cursor.fetchone()[0]
        flex_artifact = build_stage_hwf(
            {
                "id": "VERTICA-STAGE-FLEX-E2E",
                "category": "STAGE",
                "source": "CSV",
                "source_config": {"sources": [{"fields": [
                    {"name": "event_id", "type": "INT"},
                    {"name": "event_type", "type": "VARCHAR(20)"},
                    {"name": "channel", "type": "VARCHAR(20)"},
                ]}]},
                "target_config": {
                    "schema": "public", "table": "stage_flex_events_platform_e2e",
                    "stage_mode": "FLEX", "format": "JSON",
                    "data_path": f"{FLEX_DIR}/*.json",
                    "reject_path": "/data/ai_agents_v2_reject/",
                    "exception_path": "/data/ai_agents_v2_exception/",
                },
            },
            ["event_id", "event_type", "channel"],
        )
        assert static_validate(flex_artifact)["valid"]
        statements = [statement.strip() for statement in flex_artifact["sql"].split(";") if statement.strip()]
        for statement in statements:
            cursor.execute(statement)
        flex_loaded = cursor.fetchone()[0]
        cursor.execute(
            "SELECT event_id::INT, event_type::VARCHAR, channel::VARCHAR "
            "FROM public.stage_flex_events_platform_e2e ORDER BY event_id::INT"
        )
        flex_rows = cursor.fetchall()

        result = {
            "external": {
                "server_path": f"{EXTERNAL_DIR}/*.csv",
                "exported": external_exported,
                "artifact": external_artifact["path"],
                "rows": external_rows,
            },
            "flex": {
                "server_path": f"{FLEX_DIR}/*.json",
                "exported": flex_exported,
                "loaded": flex_loaded,
                "artifact": flex_artifact["path"],
                "rows": flex_rows,
            },
        }
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
