ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS error_test_config jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS error_test_result jsonb;
