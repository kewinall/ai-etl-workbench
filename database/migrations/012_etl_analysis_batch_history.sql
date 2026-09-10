BEGIN;
CREATE TABLE IF NOT EXISTS platform.etl_analysis_batch (
  batch_id uuid PRIMARY KEY,
  requested_count integer NOT NULL,
  ai_provider text,
  status text NOT NULL,
  succeeded_count integer NOT NULL DEFAULT 0,
  failed_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS platform.etl_analysis_batch_item (
  batch_item_id uuid PRIMARY KEY,
  batch_id uuid NOT NULL REFERENCES platform.etl_analysis_batch(batch_id) ON DELETE CASCADE,
  source_relative_path text NOT NULL,
  status text NOT NULL,
  analysis_id uuid REFERENCES platform.etl_analysis(analysis_id),
  error_code text,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS etl_batch_item_batch_idx ON platform.etl_analysis_batch_item(batch_id);
COMMIT;
