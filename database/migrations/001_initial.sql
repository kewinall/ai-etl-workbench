BEGIN;
CREATE SCHEMA IF NOT EXISTS platform;
CREATE SCHEMA IF NOT EXISTS poc_validation;

CREATE TABLE IF NOT EXISTS platform.task (
  task_id text PRIMARY KEY, task_name text NOT NULL, task_type text NOT NULL,
  requirement_text text NOT NULL, status text NOT NULL, current_step text,
  source_type text NOT NULL CHECK (source_type IN ('CSV','POSTGRESQL_TABLE')),
  target_type text NOT NULL DEFAULT 'POSTGRESQL' CHECK (target_type='POSTGRESQL'),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.source_definition (
  source_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id),
  connection_id uuid, source_type text NOT NULL, source_config jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.source_profile (
  profile_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id), source_id uuid REFERENCES platform.source_definition(source_id),
  profile_version int NOT NULL, profile_result jsonb NOT NULL, sample_data jsonb, warning_detail jsonb, error_detail jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(task_id,profile_version)
);
CREATE TABLE IF NOT EXISTS platform.specification (
  specification_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id), version int NOT NULL,
  spec_yaml text, spec_markdown text, spec_json jsonb NOT NULL, validation_status text, created_by_agent_run_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(), is_current boolean NOT NULL DEFAULT true, UNIQUE(task_id,version)
);
CREATE TABLE IF NOT EXISTS platform.agent_run (
  agent_run_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id), agent_type text NOT NULL,
  provider text NOT NULL, model text, status text NOT NULL, input_prompt text, structured_input jsonb,
  raw_output text, structured_output jsonb, started_at timestamptz, ended_at timestamptz, duration_ms bigint,
  retry_count int NOT NULL DEFAULT 0, error_detail jsonb
);
ALTER TABLE platform.specification DROP CONSTRAINT IF EXISTS specification_agent_fk;
ALTER TABLE platform.specification ADD CONSTRAINT specification_agent_fk FOREIGN KEY(created_by_agent_run_id) REFERENCES platform.agent_run(agent_run_id);
CREATE TABLE IF NOT EXISTS platform.agent_handoff (
  handoff_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id), from_agent_run_id uuid REFERENCES platform.agent_run(agent_run_id),
  to_agent_type text NOT NULL, contract jsonb NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.hop_artifact (
  artifact_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id), artifact_type text NOT NULL CHECK(artifact_type IN ('HPL','HWF')),
  version int NOT NULL, parent_artifact_id uuid REFERENCES platform.hop_artifact(artifact_id), file_path text NOT NULL,
  checksum text NOT NULL, file_size bigint NOT NULL, created_by_agent_run_id uuid REFERENCES platform.agent_run(agent_run_id),
  created_at timestamptz NOT NULL DEFAULT now(), is_current boolean NOT NULL DEFAULT true, UNIQUE(task_id,artifact_type,version)
);
CREATE TABLE IF NOT EXISTS platform.validation_run (
  validation_run_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id),
  validation_type text NOT NULL CHECK(validation_type IN ('STATIC','SEMANTIC','EXECUTION','POST_WRITE_COUNT')),
  status text NOT NULL, validation_result jsonb NOT NULL, report_text text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.hop_run (
  hop_run_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id), hpl_artifact_id uuid REFERENCES platform.hop_artifact(artifact_id),
  hwf_artifact_id uuid REFERENCES platform.hop_artifact(artifact_id), status text NOT NULL, command_line text, parameters jsonb,
  exit_code int, rows_read bigint, rows_valid bigint, rows_written bigint CHECK(rows_written BETWEEN 0 AND 10), rows_rejected bigint,
  post_write_count bigint, started_at timestamptz, ended_at timestamptz, duration_ms bigint, error_detail jsonb
);
CREATE TABLE IF NOT EXISTS platform.hop_run_log (
  log_id uuid PRIMARY KEY, hop_run_id uuid NOT NULL REFERENCES platform.hop_run(hop_run_id),
  log_type text NOT NULL CHECK(log_type IN ('STDOUT','STDERR','HOP_LOG','RUN_LOG')), sequence_no int NOT NULL,
  log_content text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(hop_run_id,log_type,sequence_no)
);
CREATE TABLE IF NOT EXISTS platform.model_usage (
  usage_id uuid PRIMARY KEY, task_id text REFERENCES platform.task(task_id), agent_run_id uuid REFERENCES platform.agent_run(agent_run_id),
  provider text NOT NULL, model text, input_tokens bigint, output_tokens bigint, total_tokens bigint,
  usage_type text NOT NULL CHECK(usage_type IN ('EXACT','ESTIMATED','UNAVAILABLE')), raw_usage jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.provider_health (
  provider text PRIMARY KEY, installed boolean NOT NULL DEFAULT false, authenticated boolean NOT NULL DEFAULT false,
  support_level text NOT NULL, capability_result jsonb NOT NULL DEFAULT '{}'::jsonb, checked_at timestamptz
);
CREATE TABLE IF NOT EXISTS platform.system_setting (
  setting_key text PRIMARY KEY, setting_value jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO platform.system_setting(setting_key,setting_value) VALUES
 ('validation_policy','{"strategy":"FIRST_10_VALID_ROWS","max_rows":10,"post_write_count":true}'::jsonb),
 ('storage_policy','{"persistent_files":[".hpl",".hwf"],"runtime_temp_cleanup":true}'::jsonb)
ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=now();
COMMIT;
