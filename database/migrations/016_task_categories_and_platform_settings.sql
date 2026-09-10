ALTER TABLE platform.task
  ADD COLUMN IF NOT EXISTS task_category text NOT NULL DEFAULT 'STAGE';

ALTER TABLE platform.task DROP CONSTRAINT IF EXISTS task_category_check;
ALTER TABLE platform.task ADD CONSTRAINT task_category_check
  CHECK (task_category IN ('STAGE','ODS','DW_DM'));

INSERT INTO platform.system_setting(setting_key,setting_value) VALUES
 ('feature_flags','{"test_mode_enabled":false}'::jsonb),
 ('upload_policy','{"retention_days":7,"max_file_mb":50,"allowed_extensions":[".csv",".xlsx"]}'::jsonb)
ON CONFLICT(setting_key) DO NOTHING;
