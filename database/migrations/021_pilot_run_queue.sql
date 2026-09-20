CREATE TABLE platform.task_run (
  run_id uuid PRIMARY KEY,
  task_id text NOT NULL REFERENCES platform.task(task_id),
  project_id uuid NOT NULL REFERENCES platform.project(project_id),
  request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 120),
  input_snapshot jsonb NOT NULL,
  input_checksum text NOT NULL,
  settings_snapshot jsonb NOT NULL,
  state text NOT NULL DEFAULT 'QUEUED' CHECK(state IN ('QUEUED','RUNNING','NEEDS_REVIEW','SUCCEEDED','FAILED','CANCELLED')),
  phase text NOT NULL DEFAULT 'PREFLIGHT',
  lease_token uuid,
  lease_until timestamptz,
  write_started boolean NOT NULL DEFAULT false,
  outcome_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(task_id,request_key),
  CHECK ((state='RUNNING') = (lease_token IS NOT NULL AND lease_until IS NOT NULL))
);
CREATE UNIQUE INDEX task_run_one_active ON platform.task_run(task_id)
 WHERE state IN ('QUEUED','RUNNING','NEEDS_REVIEW');
CREATE INDEX task_run_queue_order ON platform.task_run(created_at,run_id) WHERE state='QUEUED';
CREATE TABLE platform.task_run_event (
  event_id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES platform.task_run(run_id),
  event_type text NOT NULL,
  phase text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX task_run_event_order ON platform.task_run_event(run_id,event_id);
CREATE FUNCTION platform.protect_task_run_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.run_id IS DISTINCT FROM OLD.run_id OR NEW.task_id IS DISTINCT FROM OLD.task_id
 OR NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.request_key IS DISTINCT FROM OLD.request_key
 OR NEW.input_snapshot IS DISTINCT FROM OLD.input_snapshot OR NEW.input_checksum IS DISTINCT FROM OLD.input_checksum
 OR NEW.settings_snapshot IS DISTINCT FROM OLD.settings_snapshot OR NEW.created_at IS DISTINCT FROM OLD.created_at
 OR (OLD.write_started AND NOT NEW.write_started) THEN
   RAISE EXCEPTION 'Run identity and snapshots are immutable';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER task_run_snapshot_immutable BEFORE UPDATE ON platform.task_run
 FOR EACH ROW EXECUTE FUNCTION platform.protect_task_run_snapshot();
