import os

import vertica_python
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
cfg = {
    "host": os.getenv("VERTICA_HOST"),
    "port": int(os.getenv("VERTICA_PORT", "5433")),
    "user": os.getenv("VERTICA_USER"),
    "password": os.getenv("VERTICA_PASSWORD"),
    "database": os.getenv("VERTICA_DATABASE"),
    "tlsmode": os.getenv("VERTICA_TLSMODE", "disable"),
}
with vertica_python.connect(**cfg) as conn:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM columns WHERE table_schema=%s AND table_name=%s", ("public", "customer_master"))
    if cur.fetchone()[0]:
        raise SystemExit("Refusing to modify existing public.customer_master")
    cur.execute("CREATE TABLE public.customer_master (customer_id INT, customer_name VARCHAR(100), email VARCHAR(200), status VARCHAR(20))")
    for index in range(1, 11):
        cur.execute(
            "INSERT INTO public.customer_master VALUES (%s,%s,%s,%s)",
            (index, f"Customer {index}", f"customer{index}@example.test", "ACTIVE" if index % 2 else "INACTIVE"),
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM public.customer_master")
    print(f"customer_master rows={cur.fetchone()[0]}")
