import os

import vertica_python
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
cfg = {
    "host": os.getenv("VERTICA_HOST"), "port": int(os.getenv("VERTICA_PORT", "5433")),
    "user": os.getenv("VERTICA_USER"), "password": os.getenv("VERTICA_PASSWORD"),
    "database": os.getenv("VERTICA_DATABASE"), "tlsmode": os.getenv("VERTICA_TLSMODE", "disable"),
}
targets = [
    ("UI01", "etl_stage", "ui_stage_csv_upload"), ("UI02", "etl_stage", "ui_stage_generated"),
    ("UI03", "etl_ext", "ui_sales_external"), ("UI04", "etl_flex", "ui_event_flex"),
    ("UI05", "ods", "ui_customer_master"), ("UI06", "public", "ui_ods_generated"),
    ("UI07", "dm", "ui_sales_summary"), ("UI08", "public", "ui_stage_excel"),
    ("UI10", "public", "ui_flex_json_fixed"),
]
with vertica_python.connect(**cfg) as conn:
    cur = conn.cursor()
    for case, schema, table in targets:
        cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        print(f"{case} {schema}.{table} rows={cur.fetchone()[0]}")
