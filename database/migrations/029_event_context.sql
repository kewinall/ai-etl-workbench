ALTER TABLE platform.task_run_event ADD COLUMN event_context jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE platform.task_run_event ADD CONSTRAINT task_run_event_context_object CHECK(jsonb_typeof(event_context)='object');
