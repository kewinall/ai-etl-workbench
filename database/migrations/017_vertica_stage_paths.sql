INSERT INTO platform.system_setting(setting_key,setting_value) VALUES
 ('vertica_stage_paths','{"external_data_path":"/data/ai_agents_v2_external_20260820_v4","flex_data_path":"/data/ai_agents_v2_flex_20260820_v4","reject_path":"/data/ai_agents_v2_reject","exception_path":"/data/ai_agents_v2_exception"}'::jsonb)
ON CONFLICT(setting_key) DO NOTHING;
