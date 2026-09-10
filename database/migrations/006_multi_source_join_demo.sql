CREATE SCHEMA IF NOT EXISTS poc_source;
CREATE SCHEMA IF NOT EXISTS poc_target;

CREATE TABLE IF NOT EXISTS poc_source.join_demo_customers (
  customer_id integer PRIMARY KEY,
  customer_name text NOT NULL,
  tier text NOT NULL
);

CREATE TABLE IF NOT EXISTS poc_source.join_demo_order_lines (
  order_id integer PRIMARY KEY,
  customer_id integer NOT NULL,
  quantity integer NOT NULL,
  unit_price numeric(12,2) NOT NULL,
  discount_rate numeric(6,4) NOT NULL
);

INSERT INTO poc_source.join_demo_customers(customer_id,customer_name,tier) VALUES
 (101,'示範客戶甲','GOLD'),(102,'示範客戶乙','SILVER'),(103,'示範客戶丙','BRONZE'),
 (104,'示範客戶丁','GOLD'),(105,'示範客戶戊','SILVER')
ON CONFLICT(customer_id) DO UPDATE SET customer_name=excluded.customer_name,tier=excluded.tier;

INSERT INTO poc_source.join_demo_order_lines(order_id,customer_id,quantity,unit_price,discount_rate) VALUES
 (5001,101,2,1200.00,0.1000),(5002,102,1,850.00,0.0500),(5003,103,5,199.00,0.0000),
 (5004,104,3,450.00,0.1500),(5005,105,4,320.00,0.0800),(5006,101,1,2500.00,0.1000),
 (5007,102,6,150.00,0.0500),(5008,103,2,780.00,0.0000),(5009,104,3,999.00,0.1500),
 (5010,105,10,88.00,0.0800)
ON CONFLICT(order_id) DO UPDATE SET customer_id=excluded.customer_id,quantity=excluded.quantity,unit_price=excluded.unit_price,discount_rate=excluded.discount_rate;

CREATE TABLE IF NOT EXISTS poc_target.join_demo_codex (
  order_id integer PRIMARY KEY,
  customer_id integer NOT NULL,
  customer_name text NOT NULL,
  tier text NOT NULL,
  gross_amount numeric(14,2) NOT NULL,
  discount_amount numeric(14,2) NOT NULL,
  net_amount numeric(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS poc_target.join_demo_copilot
  (LIKE poc_target.join_demo_codex INCLUDING ALL);
