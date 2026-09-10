BEGIN;

ALTER TABLE platform.task DROP CONSTRAINT IF EXISTS task_target_type_check;
ALTER TABLE platform.task
  ADD CONSTRAINT task_target_type_check
  CHECK (target_type IN ('POSTGRESQL', 'VERTICA'));

INSERT INTO platform.system_setting(setting_key, setting_value)
VALUES ('supported_target_databases', '["POSTGRESQL", "VERTICA"]'::jsonb)
ON CONFLICT (setting_key) DO UPDATE
SET setting_value = EXCLUDED.setting_value, updated_at = now();

COMMIT;
