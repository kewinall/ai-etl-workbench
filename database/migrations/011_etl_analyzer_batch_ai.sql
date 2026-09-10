BEGIN;
ALTER TABLE platform.etl_analysis ADD COLUMN IF NOT EXISTS batch_id uuid;
ALTER TABLE platform.etl_analysis ADD COLUMN IF NOT EXISTS ai_summary jsonb;
ALTER TABLE platform.etl_analysis ADD COLUMN IF NOT EXISTS ai_provider text;
ALTER TABLE platform.etl_analysis ADD COLUMN IF NOT EXISTS ai_model text;
ALTER TABLE platform.etl_analysis ADD COLUMN IF NOT EXISTS ai_usage jsonb;
ALTER TABLE platform.etl_analysis ADD COLUMN IF NOT EXISTS column_lineage_count integer NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS etl_analysis_batch_idx ON platform.etl_analysis(batch_id);
COMMIT;
