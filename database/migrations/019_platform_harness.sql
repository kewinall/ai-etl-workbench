BEGIN;

CREATE TABLE IF NOT EXISTS platform.operator_profile (
  operator_id uuid PRIMARY KEY, display_name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO platform.operator_profile(operator_id,display_name)
SELECT '00000000-0000-0000-0000-000000000001','Local Operator'
WHERE NOT EXISTS (SELECT 1 FROM platform.operator_profile);

CREATE TABLE IF NOT EXISTS platform.project (
  project_id uuid PRIMARY KEY, project_name text NOT NULL UNIQUE, description text NOT NULL DEFAULT '',
  default_ai_profile text NOT NULL DEFAULT 'nova-default', default_connection text NOT NULL DEFAULT 'vertica-default',
  naming_rules jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.project_member (
  project_id uuid NOT NULL REFERENCES platform.project(project_id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id), role text NOT NULL DEFAULT 'OWNER',
  PRIMARY KEY(project_id,operator_id)
);
INSERT INTO platform.project(project_id,project_name,description)
SELECT '00000000-0000-0000-0000-000000000010','Default Project','由既有 v2 Task 移轉的預設專案'
WHERE NOT EXISTS (SELECT 1 FROM platform.project);
INSERT INTO platform.project_member(project_id,operator_id)
SELECT '00000000-0000-0000-0000-000000000010','00000000-0000-0000-0000-000000000001'
WHERE NOT EXISTS (SELECT 1 FROM platform.project_member);
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS project_id uuid REFERENCES platform.project(project_id);
UPDATE platform.task SET project_id='00000000-0000-0000-0000-000000000010' WHERE project_id IS NULL;
ALTER TABLE platform.task ALTER COLUMN project_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS platform.requirement_issue (
  issue_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
  revision integer NOT NULL, issue_type text NOT NULL CHECK(issue_type IN ('MISSING','AMBIGUOUS','CONFLICT','UNSAFE','UNSUPPORTED')),
  field_path text NOT NULL, message text NOT NULL, suggestion jsonb NOT NULL DEFAULT '{}'::jsonb,
  resolved boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.naming_contract (
  contract_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
  version integer NOT NULL, status text NOT NULL CHECK(status IN ('DRAFT','CONFIRMED')),
  contract_json jsonb NOT NULL, checksum text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), confirmed_at timestamptz,
  UNIQUE(task_id,version)
);
CREATE TABLE IF NOT EXISTS platform.naming_contract_column (
  contract_id uuid NOT NULL REFERENCES platform.naming_contract(contract_id) ON DELETE CASCADE,
  ordinal integer NOT NULL, source_name text NOT NULL, english_name text NOT NULL, vertica_type text NOT NULL,
  confidence numeric(4,3) NOT NULL, reason text NOT NULL, PRIMARY KEY(contract_id,ordinal), UNIQUE(contract_id,english_name)
);
CREATE TABLE IF NOT EXISTS platform.sample_table_definition (
  definition_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
  schema_name text NOT NULL, table_name text NOT NULL, fields jsonb NOT NULL, sample_rows jsonb NOT NULL, ddl text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.platform_sample_table (
  project_id uuid NOT NULL REFERENCES platform.project(project_id), schema_name text NOT NULL, table_name text NOT NULL,
  task_id text NOT NULL REFERENCES platform.task(task_id), ddl_checksum text NOT NULL, row_count integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), rebuilt_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(project_id,schema_name,table_name)
);
CREATE TABLE IF NOT EXISTS platform.ai_provider_profile (
  profile_id text PRIMARY KEY, display_name text NOT NULL, provider_type text NOT NULL,
  endpoint text, region text, model_routes jsonb NOT NULL, enabled boolean NOT NULL DEFAULT true, secret_ref text, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.secret_vault_entry (
  secret_ref text PRIMARY KEY, cipher_text bytea NOT NULL, nonce bytea NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.prompt_definition (
  prompt_id text PRIMARY KEY, role text NOT NULL, active_version integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.prompt_version (
  prompt_id text NOT NULL REFERENCES platform.prompt_definition(prompt_id) ON DELETE CASCADE,
  version integer NOT NULL, template text NOT NULL, checksum text NOT NULL, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(prompt_id,version)
);
CREATE TABLE IF NOT EXISTS platform.agent_invocation (
  invocation_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
  role text NOT NULL, provider text NOT NULL, model text NOT NULL, prompt_version integer, context_checksum text NOT NULL,
  input_json jsonb NOT NULL, output_json jsonb, status text NOT NULL, duration_ms bigint, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS platform.tool_invocation (
  tool_invocation_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
  tool_name text NOT NULL, input_checksum text NOT NULL, status text NOT NULL, detail jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO platform.ai_provider_profile(profile_id,display_name,provider_type,model_routes)
VALUES ('nova-default','Amazon Nova (LiteLLM)','LITELLM_BEDROCK','{"requirement_gate":"bedrock/amazon.nova-micro-v1:0","file_understanding":"bedrock/amazon.nova-lite-v1:0","etl_specification":"bedrock/amazon.nova-pro-v1:0"}'::jsonb)
ON CONFLICT(profile_id) DO NOTHING;
INSERT INTO platform.system_setting(setting_key,setting_value) VALUES
 ('ai_provider_model_strategy','{"default_profile":"nova-default","routes":{"requirement_gate":"nova-micro","file_understanding":"nova-lite","etl_specification":"nova-pro"}}'::jsonb),
 ('data_connections_targets','{"platform":"postgresql-default","etl_qa":"vertica-default"}'::jsonb),
 ('execution_tool_paths','{}'::jsonb),
 ('data_governance_naming_rules','{"sample_schema":"ai_sample","english_identifier":"snake_case"}'::jsonb),
 ('validation_release_policy','{"sample_rows":10,"require_naming_contract":true}'::jsonb),
 ('security_secret_vault','{"encryption":"AES-256-GCM","key_source":"PLATFORM_SETTINGS_ENCRYPTION_KEY"}'::jsonb)
ON CONFLICT(setting_key) DO NOTHING;
COMMIT;
