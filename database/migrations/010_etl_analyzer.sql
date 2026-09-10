BEGIN;

CREATE TABLE IF NOT EXISTS platform.etl_analysis (
  analysis_id uuid PRIMARY KEY,
  source_name text NOT NULL,
  source_type text NOT NULL CHECK (source_type IN ('KTR','KJB','HPL','HWF')),
  source_relative_path text NOT NULL,
  source_checksum text NOT NULL,
  source_size bigint NOT NULL,
  source_content text NOT NULL,
  status text NOT NULL CHECK (status IN ('SUCCEEDED','FAILED')),
  process_name text,
  process_type text,
  platform_type text,
  node_count integer NOT NULL DEFAULT 0,
  edge_count integer NOT NULL DEFAULT 0,
  source_count integer NOT NULL DEFAULT 0,
  target_count integer NOT NULL DEFAULT 0,
  logic_count integer NOT NULL DEFAULT 0,
  canonical_model jsonb NOT NULL,
  summary_text text,
  warning_detail jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS etl_analysis_created_at_idx
  ON platform.etl_analysis(created_at DESC);
CREATE INDEX IF NOT EXISTS etl_analysis_checksum_idx
  ON platform.etl_analysis(source_checksum);

INSERT INTO platform.system_setting(setting_key, setting_value)
VALUES (
  'etl_analyzer',
  '{"supported_extensions":[".ktr",".kjb",".hpl",".hwf"],"max_source_bytes":5242880,"persist_raw_xml":"redacted","ai_summary":"optional"}'::jsonb
)
ON CONFLICT (setting_key) DO UPDATE
SET setting_value = EXCLUDED.setting_value, updated_at = now();

COMMIT;
