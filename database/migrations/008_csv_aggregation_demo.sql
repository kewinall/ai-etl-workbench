INSERT INTO platform.system_setting(setting_key,setting_value) VALUES
('demo.csv.sales_aggregation', jsonb_build_object(
  'filename','demo-sales-aggregation.csv',
  'content', E'sale_id,category,quantity,unit_price\n7001,Hardware,2,100.00\n7002,Software,2,300.00\n7003,Service,5,80.00\n7004,Hardware,1,250.00\n7005,Software,3,120.00\n7006,Service,2,200.00\n7007,Hardware,4,50.00\n7008,Software,1,500.00\n7009,Service,1,150.00\n7010,Service,4,90.00\n'
)) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=now();

CREATE SCHEMA IF NOT EXISTS poc_target;
CREATE TABLE IF NOT EXISTS poc_target.csv_category_summary_codex (
  category text PRIMARY KEY,
  total_quantity bigint NOT NULL,
  total_sales numeric(14,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS poc_target.csv_category_summary_copilot
  (LIKE poc_target.csv_category_summary_codex INCLUDING ALL);
