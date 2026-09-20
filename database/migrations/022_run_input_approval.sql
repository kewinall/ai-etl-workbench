CREATE TABLE platform.task_run_approval (
  approval_id uuid PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES platform.task_run(run_id),
  operator_id uuid NOT NULL REFERENCES platform.operator_profile(operator_id),
  kind text NOT NULL CHECK(kind='INPUT_REVIEW'),
  decision text NOT NULL CHECK(decision IN ('APPROVE','REJECT')),
  input_checksum text NOT NULL,
  settings_checksum text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(run_id,kind)
);
CREATE FUNCTION platform.protect_run_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Approval records are immutable';
END;
$$;
CREATE TRIGGER run_approval_immutable BEFORE UPDATE ON platform.task_run_approval
 FOR EACH ROW EXECUTE FUNCTION platform.protect_run_approval();
