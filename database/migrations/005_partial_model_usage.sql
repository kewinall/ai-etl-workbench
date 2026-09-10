ALTER TABLE platform.model_usage DROP CONSTRAINT IF EXISTS model_usage_usage_type_check;
ALTER TABLE platform.model_usage
  ADD CONSTRAINT model_usage_usage_type_check
  CHECK (usage_type IN ('EXACT', 'PARTIAL', 'ESTIMATED', 'UNAVAILABLE'));
