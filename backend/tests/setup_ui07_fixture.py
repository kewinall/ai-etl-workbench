import os

import vertica_python
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
cfg = {
    "host": os.getenv("VERTICA_HOST"), "port": int(os.getenv("VERTICA_PORT", "5433")),
    "user": os.getenv("VERTICA_USER"), "password": os.getenv("VERTICA_PASSWORD"),
    "database": os.getenv("VERTICA_DATABASE"), "tlsmode": os.getenv("VERTICA_TLSMODE", "disable"),
}
tables = ("orders", "customers", "products")
with vertica_python.connect(**cfg) as conn:
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM tables WHERE table_schema=%s AND table_name IN (%s,%s,%s)", ("public", *tables))
    existing = [row[0] for row in cur.fetchall()]
    if existing:
        raise SystemExit(f"Refusing to modify existing UI07 tables: {existing}")
    cur.execute("CREATE TABLE public.customers (customer_id INT, customer_name VARCHAR(100), region VARCHAR(20))")
    cur.execute("CREATE TABLE public.products (product_id INT, product_name VARCHAR(100), category VARCHAR(50))")
    cur.execute("CREATE TABLE public.orders (order_id INT, customer_id INT, product_id INT, order_date DATE, quantity INT, amount NUMERIC(18,2))")
    for index in range(1, 11):
        cur.execute("INSERT INTO public.customers VALUES (%s,%s,%s)", (index, f"Customer {index}", ("North", "South", "West")[index % 3]))
        cur.execute("INSERT INTO public.products VALUES (%s,%s,%s)", (index, f"Product {index}", ("Hardware", "Software", "Service")[index % 3]))
        cur.execute("INSERT INTO public.orders VALUES (%s,%s,%s,%s,%s,%s)", (index, index, index, f"2026-01-{index:02d}", index, index * 100))
    conn.commit()
    print("UI07 fixture rows: orders=10 customers=10 products=10")
