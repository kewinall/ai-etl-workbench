BEGIN;
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS source_config jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS target_config jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS model_provider text NOT NULL DEFAULT 'codex_cli';
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS progress integer NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100);
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS rows_written integer NOT NULL DEFAULT 0 CHECK(rows_written BETWEEN 0 AND 10);
ALTER TABLE platform.task ADD COLUMN IF NOT EXISTS last_error jsonb;
CREATE TABLE IF NOT EXISTS platform.task_node_run(
 node_run_id uuid PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
 node_key text NOT NULL, node_label text NOT NULL, sequence_no integer NOT NULL,
 status text NOT NULL, started_at timestamptz, ended_at timestamptz, duration_ms bigint,
 detail jsonb NOT NULL DEFAULT '{}'::jsonb, UNIQUE(task_id,node_key)
);
CREATE TABLE IF NOT EXISTS platform.task_event(
 event_id bigserial PRIMARY KEY, task_id text NOT NULL REFERENCES platform.task(task_id) ON DELETE CASCADE,
 level text NOT NULL, node_key text, message text NOT NULL, detail jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS task_event_task_time_idx ON platform.task_event(task_id,created_at);
COMMIT;
