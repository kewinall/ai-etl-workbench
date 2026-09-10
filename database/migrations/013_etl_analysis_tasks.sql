BEGIN;
ALTER TABLE platform.etl_analysis_batch ADD COLUMN IF NOT EXISTS task_name text;
ALTER TABLE platform.etl_analysis_batch ADD COLUMN IF NOT EXISTS source_mode text NOT NULL DEFAULT 'SCAN';
UPDATE platform.etl_analysis_batch SET task_name = 'ETL 分析 ' || left(batch_id::text, 8) WHERE task_name IS NULL;
ALTER TABLE platform.etl_analysis_batch ALTER COLUMN task_name SET NOT NULL;
CREATE INDEX IF NOT EXISTS etl_analysis_batch_created_idx ON platform.etl_analysis_batch(created_at DESC);
COMMIT;
