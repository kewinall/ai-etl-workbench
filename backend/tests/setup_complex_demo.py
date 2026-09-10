import os
import vertica_python
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
cfg = {"host": os.getenv("VERTICA_HOST", "127.0.0.1"), "port": int(os.getenv("VERTICA_PORT", "5433")),
       "user": os.getenv("VERTICA_USER", "dbadmin"), "password": os.getenv("VERTICA_PASSWORD", ""),
       "database": os.getenv("VERTICA_DATABASE", "VMart"), "tlsmode": os.getenv("VERTICA_TLSMODE", "disable")}
with vertica_python.connect(**cfg) as conn:
    cur = conn.cursor()
    for statement in (
        "CREATE TABLE IF NOT EXISTS public.etl_demo_orders_0813 (order_id INT, customer_id INT, product_id INT, order_date DATE, quantity INT, unit_price NUMERIC(18,2))",
        "CREATE TABLE IF NOT EXISTS public.etl_demo_customers_0813 (customer_id INT, customer_name VARCHAR(100), region VARCHAR(20))",
        "CREATE TABLE IF NOT EXISTS public.etl_demo_products_0813 (product_id INT, category VARCHAR(50))",
        "CREATE TABLE IF NOT EXISTS public.etl_demo_complex_result_0813 (region VARCHAR(20), category VARCHAR(50), order_date DATE, daily_amount NUMERIC(18,2), moving_avg_3d NUMERIC(18,2))",
        "INSERT INTO public.etl_demo_customers_0813 SELECT 81001,'Alpha','North' WHERE NOT EXISTS (SELECT 1 FROM public.etl_demo_customers_0813 WHERE customer_id=81001)",
        "INSERT INTO public.etl_demo_customers_0813 SELECT 81002,'Beta','South' WHERE NOT EXISTS (SELECT 1 FROM public.etl_demo_customers_0813 WHERE customer_id=81002)",
        "INSERT INTO public.etl_demo_products_0813 SELECT 82001,'Hardware' WHERE NOT EXISTS (SELECT 1 FROM public.etl_demo_products_0813 WHERE product_id=82001)",
        "INSERT INTO public.etl_demo_products_0813 SELECT 82002,'Software' WHERE NOT EXISTS (SELECT 1 FROM public.etl_demo_products_0813 WHERE product_id=82002)",
    ): cur.execute(statement)
    orders = [(83001,81001,82001,'2026-08-01',2,100),(83002,81001,82001,'2026-08-02',1,150),(83003,81001,82002,'2026-08-03',2,300),(83004,81002,82002,'2026-08-01',1,500),(83005,81002,82002,'2026-08-02',3,200),(83006,81002,82001,'2026-08-03',4,80)]
    for order_id, customer_id, product_id, date, quantity, price in orders:
        cur.execute(f"INSERT INTO public.etl_demo_orders_0813 SELECT {order_id},{customer_id},{product_id},DATE '{date}',{quantity},{price} WHERE NOT EXISTS (SELECT 1 FROM public.etl_demo_orders_0813 WHERE order_id={order_id})")
    cur.execute("COMMIT")
    cur.execute("SELECT table_name,column_name,data_type FROM columns WHERE table_schema='public' AND table_name IN ('etl_demo_orders_0813','etl_demo_customers_0813','etl_demo_products_0813') ORDER BY table_name,ordinal_position")
    for metadata_row in cur.fetchall(): print(" | ".join(str(value) for value in metadata_row))
print("three Vertica sources and target ready")
